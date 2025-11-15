#!/usr/bin/env python3
import grpc
import time
import subprocess
import sys
import os

# Set CREATE_NO_WINDOW flag for Windows processes to prevent console windows from flashing
# This is a constant for Windows only, so we define it conditionally.
CREATE_NO_WINDOW = 0
if sys.platform == 'win32':
    try:
        CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
    except AttributeError:
        pass


sys.path.append(os.path.dirname(__file__))

# Assuming proto definitions are available
try:
    from proto import booking_pb2, booking_pb2_grpc
    from proto import auth_pb2, auth_pb2_grpc
except ImportError:
    print("Warning: Proto files not found. Ensure 'proto' directory is in the path.")
    # Define placeholder stubs to allow the script to be edited/viewed even without protos
    class MockStub:
        def __init__(self, *args): pass
        def __getattr__(self, name): return lambda *args, **kwargs: None
    booking_pb2_grpc = type('booking_pb2_grpc', (object,), {'BookingServiceStub': MockStub})
    auth_pb2_grpc = type('auth_pb2_grpc', (object,), {'AuthServiceStub': MockStub})
    class MockPB2:
        class LoginRequest: pass
        class RegisterRequest: pass
        class AddShowRequest: pass
        class BookRequest: pass
        class QueryRequest: pass
    booking_pb2 = auth_pb2 = MockPB2

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
    
    # Wait for Auth service to be ready
    time.sleep(1)
    
    try:
        login_resp = auth_stub.Login(login_req, timeout=5)
        return login_resp.session.token
    except grpc.RpcError as e:
        print(f"ERROR: Could not connect to Auth service at {AUTH_ADDR}. Ensure it is running.")
        print(f"  Details: {e}")
        sys.exit(1)

def register_and_login():
    """Register and login test user."""
    print_header("Authentication Setup")
    time.sleep(2)
    
    auth_stub = auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_ADDR))
    
    # Register (ignore error if already registered)
    try:
        reg_req = auth_pb2.RegisterRequest(email="test@failover.com", password="test123")
        auth_stub.Register(reg_req, timeout=3)
    except:
        pass
    
    # Login
    login_req = auth_pb2.LoginRequest(email="test@failover.com", password="test123")
    login_resp = auth_stub.Login(login_req, timeout=3)
    
    if not login_resp.success:
        print(f"ERROR: Login failed")
        sys.exit(1)
    
    print(f" Test user logged in: {login_resp.session.user_id[:8]}...")
    return login_resp.session.token

def find_leader(admin_token, max_retries=5):
    """Find the current Raft leader."""
    print_header("Finding Current Leader")
    
    for attempt in range(max_retries):
        for addr, node_id in BOOKING_NODES:
            try:
                stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(addr))
                
                # Use a request that only the leader can execute
                req = booking_pb2.AddShowRequest(
                    user_id=admin_token,  
                    show_id=TEST_SHOW,
                    total_seats=10,
                    price_cents=100
                )
                
                resp = stub.AddShow(req, timeout=5)
                
                if resp.success:
                    print(f" Leader: {node_id} ({addr})")
                    return addr, node_id
                    
            except grpc.RpcError as e:
                # FAILED_PRECONDITION is often returned by followers in Raft implementation
                if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                    print(f"  {node_id}: Follower")
                elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    print(f"  {node_id}: Timeout")
                elif e.code() == grpc.StatusCode.UNAVAILABLE:
                    print(f"  {node_id}: UNAVAILABLE (Possibly dead)")
                else:
                    print(f"  {node_id}: RPC Error - {e.code().name}")
            except Exception as e:
                print(f"  {node_id}: Generic Error - {str(e)}")
        
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
            else:
                print(f"  {node_id}: Seat not found.")
        except:
            print(f"  {node_id}: UNAVAILABLE")
    
    if len(states) > 0 and len(set(s[1] for s in states)) == 1:
        print(f"\n Consistent across {len(states)} nodes!")
        return True
    else:
        print(f"\n Inconsistent!")
        return False

def kill_node(node_id):
    """Kill a node based on OS."""
    print(f"\n Killing {node_id}...")
    
    config_file = f"config-{node_id}.json"
    
    if sys.platform.startswith('linux') or sys.platform == 'darwin':
        # Linux and macOS use pkill -f to find by command line
        print(f"  Using pkill -f for {sys.platform}")
        # -f matches against the full command line
        subprocess.run(["pkill", "-f", config_file], check=False)
        
    elif sys.platform == 'win32':
        # Windows requires different process termination logic using WMIC
        print("  Attempting to terminate process via WMIC on Windows...")
        
        # WMIC command to find processes whose command line contains the config file
        # and issue the terminate call.
        try:
            wmic_command = [
                "wmic", "process", 
                "where", f"commandline like '%%{config_file}%%'", 
                "call", "terminate"
            ]
            
            # Use CREATE_NO_WINDOW to hide the console window
            result = subprocess.run(
                wmic_command, 
                capture_output=True, 
                text=True, 
                check=False, # WMIC may return non-zero even if successful
                creationflags=CREATE_NO_WINDOW
            )
            
            # WMIC often prints "No Instance(s) Available." if nothing is found
            if result.returncode != 0 and "No Instance(s) Available." not in result.stdout:
                 print(f"  WMIC termination may have failed. Exit code: {result.returncode}")
                 print(f"  STDOUT: {result.stdout.strip()}")
            else:
                 print(f"  Process matching '{config_file}' terminated (or not found).")

        except Exception as e:
            print(f"  Critical error during Windows process termination: {e}")
            
    else:
        print(f"  Warning: Unsupported operating system: {sys.platform}. Cannot reliably kill process.")

    time.sleep(1)


def main():
    print("\n" + ""*60)
    print("  RAFT LEADER FAILOVER TEST (Cross-Platform)")
    print(""*60)
    
    # Wait for cluster
    print("\n Waiting for cluster to stabilize (5 seconds)...")
    time.sleep(5)
    
    # Get admin token for leader detection
    admin_token = get_admin_token()
    print(" Admin token obtained")
    
    # Login test user for bookings
    user_token = register_and_login()
    
    # Find leader (using admin token)
    leader_addr, leader_id = find_leader(admin_token)
    
    # Book seat 1 on leader (using user token)
    print_header("Booking Seat 1 on Leader")
    resp = book_seat(leader_addr, 1, user_token)
    if resp and resp.success:
        print(f" Seat 1 booked!")
    else:
        msg = resp.message if resp else "No response"
        print(f" Booking failed: {msg}")
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
        print("ERROR: Same leader! New election did not occur or failed.")
        sys.exit(1)
    
    print(f"\n New leader: {new_id}")
    
    # Book seat 2 (using user token)
    print_header("Booking Seat 2 on New Leader")
    resp = book_seat(new_addr, 2, user_token)
    if resp and resp.success:
        print(f" Seat 2 booked!")
    else:
        msg = resp.message if resp else "No response"
        print(f" Booking failed: {msg}")
        sys.exit(1)
    
    # Final verification
    time.sleep(1)
    print_header("Final Verification")
    c1 = verify_consistency(1)
    c2 = verify_consistency(2)
    
    if c1 and c2:
        print("\n SUCCESS: Failover worked and state is consistent!")
        return 0
    else:
        print("\n FAILURE: State inconsistency or second booking failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())