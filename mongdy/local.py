#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

import socket
import select
from collections import defaultdict
import logging
import daemon
import shell
from tcprelay import TCPRelay
from eventloop import EventLoop

def main():
    shell.check_python()

    config = shell.get_config(True)

    daemon.daemon_exec(config)

    try:
        #config = {"local_addr": "127.0.0.1", "local_port": 1083, "server":"127.0.0.1", "server_port": 1084, "fast_open": False}
        tcp_server = TCPRelay(config, True)
        loop = EventLoop()
        tcp_server.add_to_loop(loop)

        loop.run()
    except Exception as e:
        #shell.print_exception(e)
        import traceback
        traceback.print_exc()
        #logging.log(logging.ERROR, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
