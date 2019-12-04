#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import socket
import time
import eventloop

def select_client():
    server_addrs = ('127.0.0.1', 1084)
    ip = '127.0.0.1'
    port = 1084
    addrs = socket.getaddrinfo(ip, port, 0, socket.SOCK_STREAM,
                                   socket.SOL_TCP)
    af, socktype, proto, canonname, sa = addrs[0]
    print(addrs)
    print(af, socktype, proto, canonname, sa)
    remote_sock = socket.socket(af, socktype, proto)
    remote_sock.setblocking(False)
    remote_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
    try:
        remote_sock.connect(sa)
    except Exception as e:
        error_no = eventloop.errno_from_exception(e)
        print(error_no,e)

    #time.sleep(5)
    nego = u'\x06\x00\x01'
    remote_sock.send(nego)
    msg = remote_sock.recv(1024)
    print(ord(msg[0]))
    print(ord(msg[1]))

    msg = b"Hello:I'm client!"
    msg = b"ls -l"
    msg = b"tree"
    remote_sock.send(msg)
    remote_sock.send(msg)
    
    #client.send(b'\n\n')
    msg = remote_sock.recv(1024)
    print("msg:%s", msg)
    print(msg)
    remote_sock.close()
                
if __name__ == '__main__':
    select_client()
