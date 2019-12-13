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

from consul_pb import consul_pb2, consul_pb2_grpc

_HOST = '127.0.0.1'
_PORT = '50051'

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip

def get_srv_mongdy_port():
    pid_file = "/var/log/mongdy.pid"
    pid = None
    port = None
    try:
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

        return int(port)
    except OSError as e:
        cmd = "ps -eo pid,cmd | grep -E \"mongdy/server\""
        cmd = "ps -eo pid,cmd"
        cmd1 = shlex.split(cmd)
        proc1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE)
        proc2 = subprocess.Popen(['grep', '-E', 'mongdy/server', '-E', 'mdserver'], stdin=proc1.stdout, stdout=subprocess.PIPE)
        proc3 = subprocess.Popen(['grep', '-v', 'grep'], stdin=proc2.stdout, stdout=subprocess.PIPE)
        proc1.wait()
        proc2.wait()
        proc3.wait()
        out = proc3.communicate()
        ret = out[0].decode()

        pid = ret.split('\n')[0].strip().split(' ')[0]

        if pid is not None:
            p = psutil.Process(int(pid))
            port (p.connections()[0].laddr[1])

        return int(port)

def notify(*args, **kwargs):
    port = get_srv_mongdy_port()
    if port is not None:
        with grpc.insecure_channel("%s:%s" % (_HOST, _PORT)) as channel:
            localip = get_host_ip()
            client = consul_pb2_grpc.ConsulStub(channel=channel)
            try:
                resp = client.Notify(consul_pb2.NotifyRequest(ip=kwargs["ip"], port=port, pool="openresty-ruf"))
            except Exception as e:
                if hasattr(e, 'errno'):
                    print("errno")
                elif e.args:
                    print(e.args[0])
                else:
                    print(e)

def main():
    localip = get_host_ip()
    cycle_timer = CycleTimer(5, notify, [], {"ip":localip})

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
