#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import socket
import select
from collections import defaultdict
import logging
import os
import errno
import eventloop
import cmd
import random
import common
import encrypt
import json
import fcntl
import stat


BUF_SIZE = 64 * 1024

MSG_FASTOPEN = 0x20000000

STAGE_INIT = 0
STAGE_NEGO = 1
STAGE_CONNECTING = 2
STAGE_STREAM = 3
STAGE_DESTROYED = 4


# for each handler, we have 2 stream directions:
#    upstream:    from client to server direction
#                 read local and write to remote
#    downstream:  from server to client direction
#                 read remote and write to local

STREAM_UP = 0
STREAM_DOWN = 1

# for each stream, it's waiting for reading, or writing, or both
WAIT_STATUS_INIT = 0
WAIT_STATUS_READING = 1
WAIT_STATUS_WRITING = 2
WAIT_STATUS_READWRITING = WAIT_STATUS_READING | WAIT_STATUS_WRITING

class TCPRelayHandler(object):
    def __init__(self, server, fd_to_handlers, loop, local_sock, config, is_local):
        self._server = server
        self._fd_to_handlers = fd_to_handlers
        self._loop = loop
        self._remote_sock = dict()
        self._local_sock = local_sock
        self._config = config

        #works as MDQlocal or MDQserver
        self._is_local = is_local
        self._fastopen_connected = False
        self._stage = dict()
        self._stage[self._local_sock.fileno()] = STAGE_INIT
        self._local_encryptor = encrypt.Encryptor(config['password'], config['method'])
        self._encryptor = defaultdict(int)
        self._upstream_status = dict()
        self._downstream_status = dict()
        self._data_to_write_to_local = []
        #self._data_to_write_to_remote = []
        self._data_to_write_to_remote = defaultdict(list)
        self._log_out_handler = defaultdict(list)
        self._data_to_exec = []
        self._client_address = local_sock.getpeername()[:2]
        if 'forbidden_ip' in config:
            self._forbidden_iplist = config['forbidden_ip']
        else:
            self._forbidden_iplist = None
        if 'allow_host' in config:
            self._allow_host = config['allow_host']
        else:
            self._allow_host = '127.0.0.1'
        if is_local:
            self._chosen_server = self._get_server_list()
        if 'log_out' in config:
            self._log_out = config['log_out']
        if 'programname' in config:
            self._programname = config['programname']

        fd_to_handlers[local_sock.fileno()] = self
        local_sock.setblocking(False)
        local_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        loop.add(local_sock, eventloop.POLL_IN | eventloop.POLL_ERR, self._server)

    def _get_a_server(self):
        server = self._config['server']
        server_port = self._config['server_port']
        if type(server_port) == list:
            server_port = random.choice(server_port)
        if type(server) == list:
            server = random.choice(server)
        logging.debug('chosen server: %s:%d', server, server_port)
        return server, server_port

    def _get_server_list(self):
        server_list = []
        server = self._config['server_list']
        server_port = self._config['server_port']
        if type(server) == list:
            server_list = list(map(lambda x: (x, server_port), server))
        else:
            server_list = [(server, server_port)]
        logging.debug('chosen server list: %s', server_list)
        return server_list

    def _get_log_out_handler(self, sockfd, ip):
        log_out_file = "%s/%s_%s.log" % (self._config['local_out_dir'].rstrip('/'), self._programname, common.to_str(ip))
        try:
            fd = os.open(log_out_file, os.O_RDWR | os.O_APPEND | os.O_CREAT, stat.S_IRUSR | stat.S_IWUSR)
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            assert flags != -1
            flags |= fcntl.FD_CLOEXEC
            r = fcntl.fcntl(fd, fcntl.F_SETFD, flags)
            assert r != -1

            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 0, 0, os.SEEK_SET)
            except IOError as e:
                logging.log(logging.ERROR, e)
                return -1

            self._log_out_handler[sockfd] = fd

            return fd
        except OSError as e:
            error_no = eventloop.errno_from_exception(e)
            if error_no == errno.ENOENT:
                #mkdir
                pass
            else:
                logging.log(logging.ERROR, e)
                return -1


    def  _get_remote_sock(self, fd):
        if fd in self._remote_sock:
            sock = self._remote_sock[fd]
            return sock

    def _capability_nego(self, data, sock):
        data = data.decode()
        version = ord(data[0])
        nmethod = ord(data[1])
        methods = list(data[2:])
        logging.log(logging.DEBUG, "version:%d, nmethod:%d, methods:%s, server:%s", version, nmethod, methods, self._chosen_server)
        self._write_to_sock(b'\x06\x00', sock)
        self._stage[sock.fileno()] = STAGE_CONNECTING

        return True

    def _update_stream(self, stream, status, fd):
        # update a stream to a new waiting status

        # check if status is changed
        # only update if dirty
        logging.debug('upstream_status: stream:%s status:%s fd:%s, downstream_status:%s, upstream_status:%s', stream, status, fd, self._downstream_status.get(fd, "NA"), self._upstream_status.get(fd, "NA"))

        dirty = False
        if stream == STREAM_DOWN:
            if fd not in self._downstream_status or self._downstream_status[fd] != status:
                self._downstream_status[fd] = status
                dirty = True
        elif stream == STREAM_UP:
            if fd not in self._upstream_status or self._upstream_status[fd] != status:
                self._upstream_status[fd] = status
                dirty = True

        if dirty:
            if self._local_sock:
                event = eventloop.POLL_ERR
                if self._downstream_status.setdefault(fd, WAIT_STATUS_INIT) & WAIT_STATUS_WRITING:
                    event |= eventloop.POLL_OUT
                if self._upstream_status.setdefault(fd, WAIT_STATUS_READING) & WAIT_STATUS_READING:
                    event |= eventloop.POLL_IN
                self._loop.modify(self._local_sock, event)
            if self._get_remote_sock(fd):
                event = eventloop.POLL_ERR
                if self._downstream_status.setdefault(fd, WAIT_STATUS_INIT) & WAIT_STATUS_READING:
                    event |= eventloop.POLL_IN
                if self._upstream_status.setdefault(fd, WAIT_STATUS_READING) & WAIT_STATUS_WRITING:
                    event |= eventloop.POLL_OUT
                self._loop.modify(self._get_remote_sock(fd), event)

    def _write_to_sock(self, data, sock):
        fd = sock.fileno()
        if not data or not sock:
            return False

        uncomplete = False

        s = 0

        try:
            l = len(data)
            s = sock.send(common.to_bytes(data))
            if s < l:
                data = data[s:]
                uncomplete = True
        except (OSError, IOError) as e:
            error_no = eventloop.errno_from_exception(e)
            if error_no in (errno.EAGAIN, errno.EINPROGRESS, errno.EWOULDBLOCK):
                uncomplete = True
            else:
                #destroy sock
                logging.debug("_write_to_sock:%s", e)
                self.destroy(sock)
                return False
        
        if uncomplete:
            if sock == self._local_sock:
                self._data_to_write_to_local.append(data)
                self._update_stream(STREAM_DOWN, WAIT_STATUS_WRITING, fd)
            elif self._get_remote_sock(fd):
                self._data_to_write_to_remote[fd].append(data)
                self._update_stream(STREAM_UP, WAIT_STATUS_WRITING, fd)
            else:
                logging.error('write_all_to_sock:unknown socket')
        else:
            if sock == self._local_sock:
                self._update_stream(STREAM_DOWN, WAIT_STATUS_READING, fd)
            elif self._get_remote_sock(fd):
                self._update_stream(STREAM_UP, WAIT_STATUS_READING, fd)
            else:
                logging.error('write_all_to_sock:unknown socket')

        return s

    def _handle_stage_connecting(self, data):
        if self._is_local and not self._fastopen_connected and self._config['fast_open']:
            try:
                self._fastopen_connected = True
                for chosen_server in self._chosen_server:
                    remote_sock = self._create_remote_socket(chosen_server[0], chosen_server[1])
                    fd = remote_sock.fileno()
                    lfd = self._local_sock.fileno()
                    if not self._encryptor:
                        self._encryptor[fd] = encrypt.Encryptor(self._config['password'], self._config['method'])
                    data = self._encryptor[fd].encrypt(data)
                    self._data_to_write_to_remote[fd].append(data)
                    self._loop.add(remote_sock, eventloop.POLL_ERR, self._server)
                    data = b''.join(self._data_to_write_to_remote[fd])
                    l = len(data)
                    s = remote_sock.sendto(data, MSG_FASTOPEN, chosen_server)
                    if s < l:
                        data = data[s:]
                        self._data_to_write_to_remote[fd] = [data]
                    else:
                        self._data_to_write_to_remote[fd] = []
                    #self._stage = STAGE_STREAM
                    self._stage[fd] = STAGE_STREAM
                    self._stage[lfd] = STAGE_STREAM
                    self._update_stream(STREAM_UP, WAIT_STATUS_READWRITING, lfd)
                    self._update_stream(STREAM_DOWN, WAIT_STATUS_READING, fd)
                    if self._log_out:
                        self._get_log_out_handler(fd, chosen_server[0])
            except (OSError, IOError) as e:
                if eventloop.errno_from_exception(e) == errno.EINPROGRESS:
                    # in this case data is not sent at all
                    pass
                elif eventloop.errno_from_exception(e) == errno.ENOTCONN:
                    logging.error('fast open not supported on this OS')
                    self._config['fast_open'] = False
                    self.destroy(self._local_sock)
                else:
                    logging.error('%s', e)
                    self.destroy(self._local_sock)
        else:
            # else do connect
            for chosen_server in self._chosen_server:
                remote_sock = self._create_remote_socket(chosen_server[0], chosen_server[1])
                fd = remote_sock.fileno()
                lfd = self._local_sock.fileno()
                if not self._encryptor[fd]:
                    self._encryptor[fd] = encrypt.Encryptor(self._config['password'], self._config['method'])
                send_data = self._encryptor[fd].encrypt(data)
                self._data_to_write_to_remote[fd].append(send_data)
                logging.info('connecting %s:%d from %s:%d' % (chosen_server[0], chosen_server[1], self._client_address[0], self._client_address[1]))
                try:
                    remote_sock.connect(chosen_server)
                except (OSError, IOError) as e:
                    logging.error('create_remote_socket connect exception:%s  %s   %s', chosen_server, e, remote_sock)
                    self._loop.add(remote_sock, eventloop.POLL_ERR | eventloop.POLL_OUT, self._server)
                    #self._stage = STAGE_STREAM
                    self._stage[fd] = STAGE_STREAM
                    self._stage[lfd] = STAGE_STREAM
                    self._update_stream(STREAM_UP, WAIT_STATUS_READWRITING, fd)
                    self._update_stream(STREAM_DOWN, WAIT_STATUS_READING, fd)
                    if self._log_out:
                        self._get_log_out_handler(fd, chosen_server[0])

    def _on_local_read(self, sock):
        fd = sock.fileno()
        data = None
        try:
            data = sock.recv(BUF_SIZE)
        except (OSError, IOError) as e:
            error_no = eventloop.errno_from_exception(e)
            if error_no in (errno.EAGAIN, errno.EINPROGRESS, errno.EWOULDBLOCK):
                logging.debug("except:_on_local_read:%s", e)
                print(e)
                return
                
        if not data:
            #destroy sock
            logging.debug("_on_local_read:no data")
            self.destroy(sock)
            return

        logging.log(logging.INFO, ">>>>>>>>>>>>>>>>>>>>>>>client data: %s", data)

        if self._is_local:
            if self._stage.setdefault(fd, STAGE_INIT) in [STAGE_INIT,STAGE_NEGO]:
                self._capability_nego(data, sock)
                return
            elif self._stage[fd] == STAGE_STREAM:
                for _fd in self._remote_sock:
                    send_data = self._encryptor[_fd].encrypt(data)
                    if self._data_to_write_to_remote[_fd]:
                        self._data_to_write_to_remote[_fd].append(send_data)
                        send_data = b''.join(self._data_to_write_to_remote[_fd])
                        self._data_to_write_to_remote[_fd] = []
                    logging.log(logging.DEBUG, "#################: data:%s sock:%s  remote:%s", send_data, sock, self._remote_sock[_fd])
                    self._write_to_sock(send_data, self._remote_sock[_fd])
                return
            elif self._stage[fd] == STAGE_CONNECTING:
                self._handle_stage_connecting(data)
        else:
            #exec C cmd
            data = self._local_encryptor.decrypt(data)
            if not data:
                return

            data = common.to_str(data)

            self._data_to_exec.append(data)
            cmd_line = "".join(self._data_to_exec)
            logging.log(logging.INFO, ">>>>>>>>>>>>>>>>>>>>>>>EXEC DATA: %s", self._data_to_exec)
            if cmd_line[-4:] == "\r\n\r\n":
                resp = cmd.execCommandLine(common.to_str(cmd_line[:-4]), pipe = "||")
                self._data_to_exec = []
                send = self._local_encryptor.encrypt(common.to_bytes(resp))
                self._write_to_sock(send, sock)

    def _on_remote_read(self, sock):
        # handle all remote read events
        data = None
        try:
            data = self._get_remote_sock(sock.fileno()).recv(BUF_SIZE)

        except (OSError, IOError) as e:
            if eventloop.errno_from_exception(e) in \
                    (errno.ETIMEDOUT, errno.EAGAIN, errno.EWOULDBLOCK):
                logging.debug("_on_remote_read:%s", e)
                return
        if not data:
            logging.debug("_on_remote_read:no data")
            self.destroy(sock)
            return

        if self._is_local:
            data = self._encryptor[sock.fileno()].decrypt(data)
        else:
            data = self._local_encryptor.encrypt(data)

        try:
            logging.debug("==========_on_remote_read:%s", data)
            s = self._write_to_sock(data, self._local_sock)
            if self._log_out and s:
                sent = data[:s]
                o_fd = self._log_out_handler[sock.fileno()]
                logging.debug("_on_remote_read222:%s  %s", o_fd, sent)
                os.write(o_fd, sent)
        except IOError as e:
            logging.error("_on_remote_read:%s", e)
        except Exception as e:
            logging.debug("_on_remote_read:%s", e)
            # TODO use logging when debug completed
            self.destroy(sock)

    def _on_local_write(self, sock):
        if self._data_to_write_to_local:
            data = b''.join(self._data_to_write_to_local)
            self._data_to_write_to_local = []
            self._write_to_sock(data, sock)
        else:
            logging.debug("_on_local_write: WAIT_STATUS_READING")
            self._update_stream(STREAM_DOWN, WAIT_STATUS_READING, sock.fileno())

    def _on_remote_write(self, sock):
        fd = sock.fileno()
        if self._data_to_write_to_remote[fd]:
            data = b''.join(self._data_to_write_to_remote[fd])
            self._data_to_write_to_remote[fd] = []
            self._write_to_sock(data, sock)
        else:
            logging.debug("_on_remote_write: WAIT_STATUS_READING")
            self._update_stream(STREAM_UP, WAIT_STATUS_READING, sock.fileno())

    def _create_remote_socket(self, ip, port):
        addrs = socket.getaddrinfo(ip, port, 0, socket.SOCK_STREAM,
                                   socket.SOL_TCP)
        if len(addrs) == 0:
            raise Exception("getaddrinfo failed for %s:%d" % (ip, port))
        af, socktype, proto, canonname, sa = addrs[0]
        if self._forbidden_iplist:
            if common.to_str(sa[0]) in self._forbidden_iplist:
                raise Exception('IP %s is in forbidden list, reject' %
                                common.to_str(sa[0]))
        if self._allow_host:
            if common.to_str(sa[0]) in self._allow_host:
                raise Exception('IP %s is in allow host list, reject' % common.to_str(sa[0]))

        remote_sock = socket.socket(af, socktype, proto)
        fd = remote_sock.fileno()
        self._remote_sock[fd] = remote_sock
        self._fd_to_handlers[fd] = self
        remote_sock.setblocking(False)
        remote_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        return remote_sock

    def handle_event(self, sock, event):
        if sock == self._local_sock:
            if event & (eventloop.POLL_IN | eventloop.POLL_HUP):
                self._on_local_read(sock)
            if event & eventloop.POLL_OUT:
                self._on_local_write(sock)
        elif self._get_remote_sock(sock.fileno()):
            if event & eventloop.POLL_ERR:
                self.destroy(sock)
                return
            if event & (eventloop.POLL_IN | eventloop.POLL_HUP):
                self._on_remote_read(sock)
            if event & eventloop.POLL_OUT:
                self._on_remote_write(sock)
        else:
            logging.warn('unknown socket')

    def destroy(self, sock):
        # destroy the handler and release any resources
        # promises:
        # 1. destroy won't make another destroy() call inside
        # 2. destroy releases resources so it prevents future call to destroy
        # 3. destroy won't raise any exceptions
        # if any of the promises are broken, it indicates a bug has been
        # introduced! mostly likely memory leaks, etc
        fd = sock.fileno()
        if self._stage[fd] == STAGE_DESTROYED:
            # this couldn't happen
            logging.debug('already destroyed')
            return
        self._stage[fd] = STAGE_DESTROYED

        logging.debug('destroy')

        if fd in self._remote_sock:
            logging.debug('destroying remote:fd %s', fd)
            self._loop.remove(self._get_remote_sock(fd))
            del self._fd_to_handlers[fd]
            self._remote_sock[fd].close()
            del self._remote_sock[fd]

        if self._local_sock.fileno() == fd:
            logging.debug('destroying local')
            for fd in list(self._remote_sock.keys()):
                self._loop.remove(self._remote_sock[fd])
                del self._fd_to_handlers[fd]
                self._remote_sock[fd].close()
                del self._remote_sock[fd]

            self._loop.remove(self._local_sock)
            del self._fd_to_handlers[self._local_sock.fileno()]
            self._local_sock.close()
            self._local_sock = None

class TCPRelay(object):
    def __init__(self, config, is_local):
        self._config = config
        self._is_local = is_local
        self._eventloop = None
        self._closed = False
        self._fd_to_handlers = {}

        if is_local:
            listen_addr = config["local_address"]
            listen_port = config["local_port"]
        else:
            listen_addr = config["server"]
            listen_port = config["server_port"]
        self._listen_port = listen_port

        addrs = socket.getaddrinfo(listen_addr, listen_port, 0, socket.SOCK_STREAM, socket.SOL_TCP)
        if len(addrs) == 0:
            raise Exception("can't get addrinfo for %s:%d" % (listen_addr, listen_port))

        af, socktype, proto, canonname, sa = addrs[0]
        server_socket = socket.socket(af, socktype, proto)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(sa)
        server_socket.setblocking(False)
        if config['fast_open']:
            try:
                server_socket.setsockopt(socket.SOL_TCP, 23, 5)
            except socket.error:
                logging.error('warning: fast open is not available')
                self._config['fast_open'] = False
        server_socket.listen(1024)
        self._server_socket = server_socket
        logging.log(logging.DEBUG, 'TCPRelay init:server_addr:%s, server_port:%d', listen_addr, listen_port)
            
    def add_to_loop(self, loop):
        if self._eventloop:
            raise Exception('already add to loop')
        if self._closed:
            raise Exception('already closed')
        self._eventloop = loop
        self._eventloop.add(self._server_socket, eventloop.POLL_IN, self)

    def handle_event(self, sock, fd, event):
        if sock:
            logging.log(logging.DEBUG, 'sockfd:%d, event:%d', fd, event)
        if sock == self._server_socket:
            if event & eventloop.POLL_ERR:
                # TODO
                raise Exception('server_socket error')
            try:
                logging.log(logging.DEBUG, 'accept')
                conn = self._server_socket.accept()
                TCPRelayHandler(self, self._fd_to_handlers, self._eventloop, conn[0], self._config, self._is_local)
                #Handler
            except (OSError, IOError) as e:
                error_no = eventloop.errno_from_exception(e)
                if error_no in (errno.EAGAIN, errno.EINPROGRESS, errno.EWOULDBLOCK):
                    return
                else:
                    logging.error('tcprelay handle_event %s', e)
        else:
            if sock:
                handler = self._fd_to_handlers.get(fd, None)
                if handler:
                    handler.handle_event(sock, event)
            else:
                logging.debug('poll removed fd')
    def close(self, next_tick=False):
        logging.debug('Tcp close')
        self._closed = True
        if not next_tick:
            if self._eventloop:
                self._eventloop.remove(self._server_socket)
            self._server_socket.close()
        for handler in list(self._fd_to_handlers.values()):
            handler.destroy()
