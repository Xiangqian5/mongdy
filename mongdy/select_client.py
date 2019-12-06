#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import socket
import time
import common

def recv(sock):
    msg = sock.recv(1024000)
    print(msg.decode())

def select_client():
    server_addrs = ('127.0.0.1', 1083)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(server_addrs)
    
    nego = b'\x06\x00\x01'
    print(common.to_str(nego))
    client.send(nego)
    msg = client.recv(1024)
    #print(ord(msg[0]))
    #print(ord(msg[1]))

    msg = b"Hello:I'm client!"
    msg = b"tree"
    msg = b"pwd"
    msg = b"ls -l || sort\r\n\r\n"

    client.send(msg)
    time.sleep(0.1)

    client.send(msg)
    time.sleep(0.1)

    client.send(msg)
    time.sleep(0.1)

    #msg = b'cat tcprelay.py || grep import'
    #msg = b'cat tcprelay.py'
    client.send(msg)
    time.sleep(0.1)

    recv(client)

    #time.sleep(1)
    client.close()
                
if __name__ == '__main__':
    select_client()
