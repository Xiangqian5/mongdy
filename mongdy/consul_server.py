import time
import grpc
import socket
import struct
import os, sys
from concurrent import futures
from collections import defaultdict

from consul_pb import consul_pb2, consul_pb2_grpc

from common import to_bytes, pack_addr

class ConsulServicer(consul_pb2_grpc.ConsulServicer):
    def __init__(self, config):
        self._ip_list = defaultdict(set)
        self._sock = self._get_porxy_sock()
        self._config = config

    def _get_porxy_sock(self):
        server_addrs = (self._config['local_address'], self._config['local_port'])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        try:
            sock.connect(server_addrs)
        except (OSError, IOError) as e:
            pass
        return sock

    def SayHello(self,request,ctx):
        max_len = str(len(request.helloworld))
        return consul_pb2.HelloReply(result = "Hello %s" % (request.helloworld))

    def Notify(self,request,ctx):
        ip = request.ip
        port = request.port
        pool = request.pool
        header = b'\x06\x00\x02'
        host = pack_addr(to_bytes(ip))
        port = struct.pack('>H', port)
        pool = to_bytes(pool)
        length = struct.pack('>H', len(pool))
        message = header + host + port + length + pool

        self._sock.send(message)
        return consul_pb2.NotifyReply(ret=1)

def consul(config):
    # 多线程服务器
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # 实例化 计算len的类
    servicer = ConsulServicer(config)
    # 注册本地服务,方法ConsulServicer只有这个是变的
    consul_pb2_grpc.add_ConsulServicer_to_server(servicer, server)
    # 监听端口
    server.add_insecure_port('[::]:50051')
    # 开始接收请求进行服务
    server.start()
    # 使用 ctrl+c 可以退出服务
    server.wait_for_termination()
    try:
        print("running...")
        time.sleep(10)
    except KeyboardInterrupt:
        print("stopping...")
        servicer._sock.close()
        server.stop(0)


if __name__ == '__main__':
    consul(None)
