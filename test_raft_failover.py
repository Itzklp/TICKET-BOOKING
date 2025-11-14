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
TEST_SHOW = "failover_test"

def print_header(msg):
    print("\n" + "="*60)
    print(f"  {msg}")
    print("="*60)

def get_admin_token():
    """Get admin token for leader detection."""
    auth_stub = auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_ADDR))
    login_req = auth_pb2.LoginRequest(email="admin@gmail.com", password="admin123")
    login_resp = auth_stub.Login(login_req)
    return login_resp.session.token

def register_and_login():
    """Register and login test user."""
    print_header("Authentication Setup")
    time.sleep(2)
    
    auth_stub = auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_ADDR))
    
    # Register
    try:
        reg_req = auth_pb2.RegisterRequest(email="test@failover.com", password="test123")
        auth_stub.Register(reg_req)
    except:
        pass
    
    # Login
    login_req = auth_pb2.LoginRequest(email="test@failover.com", password="test123")
    login_resp = auth_stub.Login(login_req)
    
    if not login_resp.success:
        print(f"ERROR: Login failed")
        sys.exit(1)
    
    print(f"✓ Test user logged in: {login_resp.session.user_id[:8]}...")
    return login_resp.session.token

def find_leader(admin_token, max_retries=5):
    """Find the current Raft leader."""
    print_header("Finding Current Leader")
    
    for attempt in range(max_retries):
        for addr, node_id in BOOKING_NODES:
            try:
                stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(addr))
                
                req = booking_pb2.AddShowRequest(
                    user_id=admin_token,  # Use admin token!
                    show_id=TEST_SHOW,
                    total_seats=10,
                    price_cents=100
                )
                
                resp = stub.AddShow(req, timeout=5)
                
                if resp.success:
                    print(f"✓ Leader: {node_id} ({addr})")
                    return addr, node_id
                    
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                    print(f"  {node_id}: Follower")
                elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    print(f"  {node_id}: Timeout")
            except Exception as e:
                print(f"  {node_id}: Error - {str(e)}")
        
        if attempt < max_retries - 1:
            print(f"\n  Retry {attempt + 1}/{max_retries - 1}: Waiting 2s...")
            time.sleep(2)
    
    print("ERROR: No leader found!")
    sys.exit(1)

def book_seat(addr, seat_id, session_token):
    """Book a seat."""
    try:
        stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(addr))
        
        req = booking_pb2.BookRequest(
            user_id=session_token,
            seat_id=seat_id,
            show_id=TEST_SHOW,
            payment_token="1234567890123456"
        )
        
        return stub.BookSeat(req, timeout=10)
    except Exception as e:
        print(f"  Booking error: {str(e)}")
        return None

def verify_consistency(seat_id):
    """Verify all nodes have same state."""
    print_header(f"Verifying Consistency (Seat {seat_id})")
    
    states = []
    for addr, node_id in BOOKING_NODES:
        try:
            stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(addr))
            req = booking_pb2.QueryRequest(show_id=TEST_SHOW, seat_id=seat_id)
            resp = stub.QuerySeat(req, timeout=3)
            
            if resp.seat:
                status = "RESERVED" if resp.seat.reserved else "AVAILABLE"
                states.append((node_id, resp.seat.reserved))
                print(f"  {node_id}: {status}")
        except:
            print(f"  {node_id}: UNAVAILABLE")
    
    if len(states) > 0 and len(set(s[1] for s in states)) == 1:
        print(f"\n✓ Consistent across {len(states)} nodes!")
        return True
    else:
        print(f"\n❌ Inconsistent!")
        return False

def kill_node(node_id):
    """Kill a node."""
    print(f"\n💀 Killing {node_id}...")
    subprocess.run(["pkill", "-f", f"config-{node_id}.json"], check=False)
    time.sleep(1)

def main():
    print("\n" + "█"*60)
    print("█  RAFT LEADER FAILOVER TEST")
    print("█"*60)
    
    # Wait for cluster
    print("\n⏳ Waiting for cluster to stabilize (5 seconds)...")
    time.sleep(5)
    
    # Get admin token for leader detection
    admin_token = get_admin_token()
    print("✓ Admin token obtained")
    
    # Login test user for bookings
    user_token = register_and_login()
    
    # Find leader (using admin token)
    leader_addr, leader_id = find_leader(admin_token)
    
    # Book seat 1 on leader (using user token)
    print_header("Booking Seat 1 on Leader")
    resp = book_seat(leader_addr, 1, user_token)
    if resp and resp.success:
        print(f"✓ Seat 1 booked!")
    else:
        msg = resp.message if resp else "No response"
        print(f"❌ Booking failed: {msg}")
        sys.exit(1)
    
    # Verify
    time.sleep(1)
    verify_consistency(1)
    
    # Kill leader
    print_header("Simulating Leader Failure")
    kill_node(leader_id)
    
    print("\n⏳ Waiting for election (5 seconds)...")
    time.sleep(5)
    
    # Find new leader (using admin token)
    new_addr, new_id = find_leader(admin_token)
    
    if new_id == leader_id:
        print("ERROR: Same leader!")
        sys.exit(1)
    
    print(f"\n✓ New leader: {new_id}")
    
    # Book seat 2 (using user token)
    print_header("Booking Seat 2 on New Leader")
    resp = book_seat(new_addr, 2, user_token)
    if resp and resp.success:
        print(f"✓ Seat 2 booked!")
    else:
        msg = resp.message if resp else "No response"
        print(f"❌ Booking failed: {msg}")
        sys.exit(1)
    
    # Final verification
    time.sleep(1)
    print_header("Final Verification")
    c1 = verify_consistency(1)
    c2 = verify_consistency(2)
    
    if c1 and c2:
        print("\n✓ SUCCESS: Failover worked!")
        return 0
    else:
        print("\n❌ FAILURE")
        return 1

if __name__ == "__main__":
    sys.exit(main())