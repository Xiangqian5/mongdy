#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import socket
import select

def epoll_server():
    listen_addr = '127.0.0.1'
    listen_port = 1083
    addrs = socket.getaddrinfo(listen_addr, listen_port, 0, socket.SOCK_STREAM, socket.SOL_TCP)
    af, socktype, proto, canonname, sockaddr = addrs[0]
    
    server = socket.socket(af, socktype, proto)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(sockaddr)
    server.setblocking(False)
    server.listen(1024)

    epoll_obj = select.epoll()
    epoll_obj.register(server.fileno(), select.EPOLLIN)

    events = []
    conns  = []
    stopping = False
    while not stopping:
        try:
            events = epoll_obj.poll(10)
        except (OSError, IOError) as e:
            print("poll:", e)
            continue

        for fd, event in events:
            if fd == server.fileno():
                conn, addr = server.accept()
                epoll_obj.register(conn.fileno(), select.EPOLLIN | select.EPOLLOUT)
                conns[conn.fileno()] = conn
            else:
                try:
                    msg = sock.recv(1024)
                    print('msg:', msg)
                except BrokenPipeError :
                    epoll_obj.unregister(fd)
                    conns[fd].close()
                    del conns[fd]
        
    server.close()
                
if __name__ == '__main__':
    epoll_server()
