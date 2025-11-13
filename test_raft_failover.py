#!/usr/bin/env python3
import grpc
import time
import subprocess
import signal
from proto import booking_pb2, booking_pb2_grpc

def test_leader_failover():
    print("Booking seat 1 on Node 1...")
    channel1 = grpc.insecure_channel("127.0.0.1:50051")
    stub1 = booking_pb2_grpc.BookingServiceStub(channel1)
    # Replace ... with real BookingRequest fields
    # response = stub1.BookSeat(booking_pb2.BookingRequest(...))
    # print(f"Booking on Node 1: {response.success}")

    print("Simulating leader failure (Node 1)...")
    # subprocess.run(["pkill", "-f", "config-node1.json"])

    print("Waiting for new leader election...")
    time.sleep(3)

    print("Booking seat 2 on Node 2 (should be new leader)...")
    # channel2 = grpc.insecure_channel("127.0.0.1:50052")
    # stub2 = booking_pb2_grpc.BookingServiceStub(channel2)
    # response = stub2.BookSeat(booking_pb2.BookingRequest(...))
    # print(f"Booking on Node 2: {response.success}")

if __name__ == "__main__":
    test_leader_failover()
