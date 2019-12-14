import grpc
from timer import *
import signal
import os
import sys
import subprocess
import stat
import shlex
import fcntl
import psutil
import socket
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'consul_pb'))

from consul_pb import consul_pb2, consul_pb2_grpc

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip

def get_srv_mongdy_port(config):
    pid = None
    port = config["server_port"]
    if port is None:
        try:
            pid_file = config["pid-file"]
            if os.path.exists(pid_file):
                fd = os.open(pid_file, os.O_RDONLY, stat.S_IRUSR | stat.S_IWUSR)
                flags = fcntl.fcntl(fd, fcntl.F_GETFD)
                assert flags != -1
                flags |= fcntl.FD_CLOEXEC
                r = fcntl.fcntl(fd, fcntl.F_SETFD, flags)
                assert r != -1

                pid = os.read(fd, 128).decode().rstrip('\n')
                if pid is not None:
                    p = psutil.Process(int(pid))
                    port = (p.connections()[0].laddr[1])

        except Exception as e:
            print(e)
    
    return int(port)

def notify(*args, **kwargs):
    port = get_srv_mongdy_port(kwargs["config"])
    if port is not None:
        with grpc.insecure_channel("%s:%s" % (kwargs["config"]["consul"], kwargs["config"]["consul_port"])) as channel:
            client = consul_pb2_grpc.ConsulStub(channel=channel)
            try:
                resp = client.Notify(consul_pb2.NotifyRequest(ip=kwargs["ip"], port=port, pool="openresty-ruf"))
            except Exception as e:
                pass

def consul_node(config):
    localip = get_host_ip()
    cycle_timer = CycleTimer(int(config.get("consul_interval", 60)), notify, [], {"ip":localip, "config":config})

    def handler_exit(signum, _):
        cycle_timer.cancel()
        if signum == signal.SIGTERM:
            sys.exit(0)
        sys.exit(1)


    signal.signal(signal.SIGQUIT , handler_exit)
    signal.signal(signal.SIGINT, handler_exit)
    signal.signal(signal.SIGTERM, handler_exit)
    signal.signal(signal.SIG_IGN, signal.SIGHUP)

    cycle_timer.start()

    while True:
        time.sleep(1000)

if __name__ == '__main__':
    main()
