import grpc
import consul_pb2, consul_pb2_grpc

_HOST = '127.0.0.1'
_PORT = '19999'


def main():
    with grpc.insecure_channel('localhost:50051') as channel:
        client = consul_pb2_grpc.ConsulStub(channel=channel)
        response = client.SayHello(consul_pb2.HelloRequest(helloworld="123456"))
    print("received: " + response.result)

if __name__ == '__main__':
    main()
