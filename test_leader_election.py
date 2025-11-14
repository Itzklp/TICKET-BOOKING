#!/usr/bin/env python3
import grpc
import time
import subprocess
import sys
import os

sys.path.append(os.path.dirname(__file__))

from proto import booking_pb2, booking_pb2_grpc
from proto import auth_pb2, auth_pb2_grpc

BOOKING_NODES = [
    ("127.0.0.1:50051", "node1"),
    ("127.0.0.1:50052", "node2"),
    ("127.0.0.1:50053", "node3"),
]
AUTH_ADDR = "127.0.0.1:8000"
TEST_SHOW = "election_test"

def print_header(msg):
    print("\n" + "="*60)
    print(f"  {msg}")
    print("="*60)

def get_admin_token():
    """Login as admin."""
    print("Logging in as admin...")
    time.sleep(2)  # Give auth service time to be ready
    
    stub = auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_ADDR))
    login_req = auth_pb2.LoginRequest(email="admin@gmail.com", password="admin123")
    login_resp = stub.Login(login_req)
    
    if not login_resp.success:
        print(f"ERROR: Admin login failed")
        sys.exit(1)
    
    print(f"✓ Admin logged in")
    return login_resp.session.token

def check_role(addr, node_id, token):
    """Check if node is leader with better error handling."""
    try:
        stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(addr))
        req = booking_pb2.AddShowRequest(
            user_id=token,
            show_id=TEST_SHOW,
            total_seats=5,
            price_cents=50
        )
        # CRITICAL FIX: Increase timeout significantly
        resp = stub.AddShow(req, timeout=5)
        return 'leader' if resp.success else 'follower'
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            return 'follower'
        elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            return 'timeout'
        return 'unavailable'
    except Exception as e:
        print(f"    Error checking {node_id}: {str(e)}")
        return 'unavailable'

def get_cluster_state(token, max_retries=3):
    """Get state with retries."""
    for attempt in range(max_retries):
        states = {}
        for addr, node_id in BOOKING_NODES:
            states[node_id] = check_role(addr, node_id, token)
        
        # Check if we have a clear leader
        leader_count = list(states.values()).count('leader')
        timeout_count = list(states.values()).count('timeout')
        
        if leader_count == 1:
            return states
        
        if timeout_count > 0:
            print(f"  Attempt {attempt + 1}/{max_retries}: Cluster not ready, retrying...")
            time.sleep(2)
        else:
            return states
    
    return states

def print_state(states):
    """Print cluster state."""
    for node, role in states.items():
        if role == 'leader':
            icon = "👑"
        elif role == 'follower':
            icon = "📦"
        elif role == 'timeout':
            icon = "⏱️"
        else:
            icon = "💀"
        print(f"  {icon} {node}: {role.upper()}")

def kill_node(node_id):
    """Kill a node."""
    print(f"💀 Killing {node_id}...")
    subprocess.run(["pkill", "-f", f"config-{node_id}.json"], check=False)
    time.sleep(1)

def main():
    print("\n" + "█"*60)
    print("█  RAFT LEADER ELECTION TEST")
    print("█"*60)
    
    # CRITICAL FIX: Wait for cluster to stabilize
    print("\n⏳ Waiting for cluster to stabilize (5 seconds)...")
    time.sleep(5)
    
    token = get_admin_token()
    
    # Test 1: Single leader
    print_header("Test 1: Single Leader Verification")
    states = get_cluster_state(token)
    print_state(states)
    
    leader_count = list(states.values()).count('leader')
    
    if leader_count != 1:
        print(f"\n❌ FAIL: Expected 1 leader, found {leader_count}")
        return 1
    
    print("\n✓ PASS: Exactly one leader")
    leader = [k for k, v in states.items() if v == 'leader'][0]
    
    # Test 2: Election after failure
    print_header("Test 2: Leader Election After Failure")
    print(f"Current leader: {leader}")
    kill_node(leader)
    
    print("\n⏳ Waiting for election (3 seconds)...")
    time.sleep(3)
    
    for i in range(1, 6):
        states = get_cluster_state(token)
        print(f"\nAfter {i * 2}s:")
        print_state(states)
        
        current_leaders = list(states.values()).count('leader')
        if current_leaders == 1:
            new_leader = [k for k, v in states.items() if v == 'leader'][0]
            if new_leader != leader:
                print(f"\n✓ PASS: New leader elected: {new_leader}")
                print(f"  Election time: ~{i * 2}s")
                return 0
        time.sleep(2)
    
    print("\n❌ FAIL: No new leader elected within 10 seconds")
    return 1

if __name__ == "__main__":
    sys.exit(main())