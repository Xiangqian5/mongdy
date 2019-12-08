#!/bin/bash

python -m grpc_tools.protoc -I./proto --python_out=consul --grpc_python_out=consul consul.proto
