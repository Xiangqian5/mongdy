#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import, division, print_function, with_statement

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'consul_pb'))

import socket
import select
from collections import defaultdict
import logging
import daemon
import shell
import multiprocessing
from consul_server import consul
from tcprelay import TCPRelay
from eventloop import EventLoop

def main():
    shell.check_python()

    config = shell.get_config(True)

    daemon.daemon_exec(config)

    try:
        tcp_server = TCPRelay(config, True)
        loop = EventLoop()
        tcp_server.add_to_loop(loop)

        p = multiprocessing.Process(target = consul, args=(config,))
        p.daemon = True
        p.start()

        loop.run()
    except Exception as e:
        #shell.print_exception(e)
        import traceback
        traceback.print_exc()
        #logging.log(logging.ERROR, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
