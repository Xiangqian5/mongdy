#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import socket
import time
import json
import errno
import select
import os, sys
import struct
import signal

def to_bytes(s):
    if bytes != str:
        if type(s) == str:
            return s.encode('utf-8')
    return s

def to_str(s):
    if bytes != str:
        if type(s) == bytes:
            return s.decode('utf-8')
    return s

def open_file(outfile):
    import fcntl
    import stat

    try:
        fd = os.open(outfile, os.O_RDWR | os.O_APPEND | os.O_CREAT, stat.S_IRUSR | stat.S_IWUSR)
    except OSError as e:
        print(e)
        return -1

    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    assert flags != -1
    flags |= fcntl.FD_CLOEXEC
    r = fcntl.fcntl(fd, fcntl.F_SETFD, flags)
    assert r != -1

    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 0, 0, os.SEEK_SET)
    except IOError:
        return -1

    return fd

def get_header(log_dir, programe_name):
    common_header = b'\x06\x00\x01'
    log_dir = to_bytes(log_dir)
    programe_name = to_bytes(programe_name)
    len_dir = struct.pack('>H', len(log_dir))
    len_name = struct.pack('>H', len(programe_name))
    return common_header + len_dir + log_dir + len_name + programe_name

def _input(x):
    return input("input command:  ")

def _producer(x):
    while True:
        yield _input(x)

def select_sock():
    def handle_exit(signum, _):
        if signum == signal.SIGTERM:
            sys.exit(0)
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    server_addrs = ('127.0.0.1', 1083)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    try:
        sock.connect(server_addrs)
    except Exception as e:
        pass

    #terminal log
    fd = open_file("output.log")
    
    #local proxy log config:logdir logname
    log_dir = "log/"
    programe_name = "logname2"
    nego = get_header(log_dir, programe_name)

    sock.send(nego)
    geniter = _producer(None)
    r_inputs = set()
    r_inputs.add(sock)

    while True:
        try:
            r_list, w_list, e_list = select.select(r_inputs, {}, {}, 1)
            if len(r_list) > 0:
                for event in r_list:
                    try:
                        data = event.recv(1024)
                    except Exception as e:
                        print(e)
                    if data:
                        if data != b'\x06\x00':
                            os.write(fd, data)
                            print(data)
                    else:
                        print("远程断开连接")
                        r_inputs.clear()
                        sock.close()
                        return
            else:
                msg = to_bytes(next(geniter))
                sock.send(msg)

        except OSError as e:
            print(e)


    sock.close()
                
if __name__ == '__main__':
    select_sock()
