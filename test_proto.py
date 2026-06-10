from google.protobuf import descriptor_pb2
import subprocess
import os

subprocess.run(["protoc", "--include_imports", "--descriptor_set_out=test_desc.pb", "--proto_path=data_logs/protos", "data_logs/protos/main_data.proto"])

with open("test_desc.pb", "rb") as f:
    fds = descriptor_pb2.FileDescriptorSet()
    fds.ParseFromString(f.read())
    for file in fds.file:
        print(f"File: {file.name}")
        for msg in file.message_type:
            print(f"  Message: {msg.name}")
            for field in msg.field:
                print(f"    Field: {field.name} (Tag: {field.number}, Type: {field.type})")
