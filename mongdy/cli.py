#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import socket
import time
import common
import json
import errno
import select
import os, sys
import struct

def open_file(outfile):
    import fcntl
    import stat

    try:
        #fd = os.open(outfile, os.O_RDWR | os.O_CREAT, stat.S_IRUSR | stat.S_IWUSR)
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
    log_dir = common.to_bytes(log_dir)
    programe_name = common.to_bytes(programe_name)
    len_dir = struct.pack('>H', len(log_dir))
    len_name = struct.pack('>H', len(programe_name))
    return common_header + len_dir + log_dir + len_name + programe_name

def select_client():
    server_addrs = ('127.0.0.1', 1083)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.setblocking(False)
    try:
        client.connect(server_addrs)
    except Exception as e:
        pass
    
    log_dir = "logs"
    programe_name = "logname2"
    nego = get_header(log_dir, programe_name)
    client.send(nego)
    time.sleep(1)
    client.recv(1024)
    time.sleep(1)

    msg = b"ls -l || sort"
    msg = b"cat mongdy/tcprelay.py"
    msg = b'grep -rnw "4450164980508272" /data1/app/interface.video.recom.weibo.com/logs/openresty/vertical_video_recom_issue.log.20191216 || awk -F"\\t" \'{print $3}\''
    msg = b"cd /data1;pwd"
    client.send(msg)

    r_inputs = set()
    r_inputs.add(client)
    w_inputs = set()
    w_inputs.add(client)
    e_inputs = set()
    e_inputs.add(client)

    fd = open_file("output.log")
    while True:
        try:
            r_list, w_list, e_list = select.select(r_inputs, w_inputs, e_inputs, 1)
            for event in r_list:
                try:
                    data = event.recv(1024)
                except Exception as e:
                    print(e)
                if data:
                    os.write(fd, data)
                else:
                    print("远程断开连接")
                    r_inputs.clear()
                    client.close()
                    return
            if len(w_list) > 0:     # 产生了可写的事件，即连接完成
                print(w_list)
                w_inputs.clear()    # 当连接完成之后，清除掉完成连接的socket
            if len(e_list) > 0:     # 产生了错误的事件，即连接错误
                print(e_list)
                e_inputs.clear()    # 当连接有错误发生时，清除掉发生错误的socket

        except OSError as e:
            print(e)


    client.close()
                
if __name__ == '__main__':
    select_client()
