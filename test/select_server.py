#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import socket
import select

def select_server():
    listen_addr = '127.0.0.1'
    listen_port = 1083
    addrs = socket.getaddrinfo(listen_addr, listen_port, 0, socket.SOCK_STREAM, socket.SOL_TCP)
    af, socktype, proto, canonname, sockaddr = addrs[0]
    
    server = socket.socket(af, socktype, proto)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(sockaddr)
    server.setblocking(False)
    server.listen(1024)

    r_list = [server,]
    w_list = []
    x_list = []
    num    = 0
    stopping = False

    while not stopping:
        num += 1
        print("num:", num)
        rlist, wlist, xlist = select.select(r_list, w_list, x_list, 10)
        print("r_list:", r_list)
        print("rlist:", rlist)

        for sock in rlist:
            if sock == server:
                conn, addr = sock.accept()
                r_list.append(conn)
            else:
                msg = sock.recv(1024)
                print('2.msg:', msg)
                if not msg:
                    r_list.remove(sock)
        
    server.close()
                
if __name__ == '__main__':
    select_server()
