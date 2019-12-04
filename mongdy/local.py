#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import socket
import select
from collections import defaultdict
import logging
import os
from tcprelay import TCPRelay
from eventloop import EventLoop

def main():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(lineno)-4d %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    config = {"local_addr": "127.0.0.1", "local_port": 1083, "server":"127.0.0.1", "server_port": 1084, "fast_open": False}
    tcp_server = TCPRelay(config, True)
    loop = EventLoop()
    tcp_server.add_to_loop(loop)

    loop.run()


if __name__ == "__main__":
    main()
