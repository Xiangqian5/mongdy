import time
import grpc
from concurrent import futures

#from consul_pb import consul_pb2, consul_pb2_grpc
import consul_pb2, consul_pb2_grpc

class ConsulServicer(consul_pb2_grpc.ConsulServicer):
    def SayHello(self,request,ctx):
        max_len = str(len(request.helloworld))
        return consul_pb2.HelloReply(result = "Hello %s" % (request.helloworld))

def main():
    # 多线程服务器
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # 实例化 计算len的类
    servicer = ConsulServicer()
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
        time.sleep(1000)
    except KeyboardInterrupt:
        print("stopping...")
        server.stop(0)


if __name__ == '__main__':
    main()
