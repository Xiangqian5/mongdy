#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import socket
import select
from collections import defaultdict
import logging
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from tcprelay import TCPRelay
from eventloop import EventLoop
import shell
import daemon

def main():
    shell.check_python()

    config = shell.get_config(False)

    daemon.daemon_exec(config)

    if config['port_password']:
        if config['password']:
            logging.warn('warning: port_password should not be used with '
                         'server_port and password. server_port and password '
                         'will be ignored')
    else:
        config['port_password'] = {}
        server_port = config['server_port']
        if type(server_port) == list:
            for a_server_port in server_port:
                config['port_password'][a_server_port] = config['password']
        else:
            config['port_password'][str(server_port)] = config['password']

    #config = {"server": "127.0.0.1", "server_port": 1084, "fast_open": False}
    tcp_server = TCPRelay(config, False)
    loop = EventLoop()
    tcp_server.add_to_loop(loop)

    loop.run()


if __name__ == "__main__":
    main()
