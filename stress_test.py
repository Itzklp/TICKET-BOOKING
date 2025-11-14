#!/usr/bin/env python3
import grpc
import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

sys.path.append(os.path.dirname(__file__))

from proto import booking_pb2, booking_pb2_grpc
from proto import auth_pb2, auth_pb2_grpc

AUTH_ADDR = "127.0.0.1:8000"
BOOKING_NODES = ["127.0.0.1:50051", "127.0.0.1:50052", "127.0.0.1:50053"]
TEST_SHOW = "stress_test"

class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.success = 0
        self.failed = 0
        self.errors = 0
        self.times = []
    
    def add_success(self, t):
        with self.lock:
            self.success += 1
            self.times.append(t)
    
    def add_failure(self, t):
        with self.lock:
            self.failed += 1
            self.times.append(t)
    
    def add_error(self):
        with self.lock:
            self.errors += 1
    
    def summary(self):
        with self.lock:
            total = self.success + self.failed + self.errors
            avg = sum(self.times) / len(self.times) if self.times else 0
            return {
                'total': total,
                'success': self.success,
                'failed': self.failed,
                'errors': self.errors,
                'avg_time': avg
            }

def print_header(msg):
    print("\n" + "="*60)
    print(f"  {msg}")
    print("="*60)

def setup():
    """Setup test environment."""
    print_header("Setup")
    
    # CRITICAL FIX: Wait for services
    print("Waiting for services to be ready...")
    time.sleep(5)
    
    # Admin login
    auth_stub = auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_ADDR))
    admin = auth_pb2.LoginRequest(email="admin@gmail.com", password="admin123")
    admin_resp = auth_stub.Login(admin)
    admin_token = admin_resp.session.token
    print("✓ Admin logged in")
    
    # CRITICAL FIX: Find leader and create show properly
    print(f"Creating show '{TEST_SHOW}'...")
    for node_addr in BOOKING_NODES:
        try:
            stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(node_addr))
            show_req = booking_pb2.AddShowRequest(
                user_id=admin_token,
                show_id=TEST_SHOW,
                total_seats=20,
                price_cents=100
            )
            
            resp = stub.AddShow(show_req, timeout=5)
            if resp.success:
                print(f"✓ Show created on leader: {TEST_SHOW} (20 seats)")
                
                # VERIFY show was created
                time.sleep(1)
                query_req = booking_pb2.QueryRequest(show_id=TEST_SHOW, seat_id=1)
                query_resp = stub.QuerySeat(query_req, timeout=3)
                if query_resp.seat:
                    print(f"✓ Verified: Show has seats")
                    return admin_token
                else:
                    print("⚠️  Warning: Show created but seats not visible")
                return admin_token
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                continue  # Try next node
            else:
                print(f"  Node error: {e.details()}")
        except Exception as e:
            print(f"  Error: {str(e)}")
    
    print("ERROR: Could not create show on any node!")
    sys.exit(1)

def create_user(uid):
    """Create test user."""
    try:
        stub = auth_pb2_grpc.AuthServiceStub(grpc.insecure_channel(AUTH_ADDR))
        email = f"stress_{uid}@test.com"
        
        # Register
        stub.Register(auth_pb2.RegisterRequest(email=email, password="test123"))
        
        # Login
        login = auth_pb2.LoginRequest(email=email, password="test123")
        resp = stub.Login(login)
        return resp.session.token
    except:
        return None

def book_seat(uid, seat, token, stats):
    """Attempt booking."""
    start = time.time()
    
    try:
        node = random.choice(BOOKING_NODES)
        stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(node))
        
        req = booking_pb2.BookRequest(
            user_id=token,
            seat_id=seat,
            show_id=TEST_SHOW,
            payment_token="1234567890123456"
        )
        
        resp = stub.BookSeat(req, timeout=10)
        duration = time.time() - start
        
        if resp.success:
            stats.add_success(duration)
            return f"User {uid}: ✓ Seat {seat}"
        else:
            stats.add_failure(duration)
            return f"User {uid}: ✗ Seat {seat}"
    except:
        stats.add_error()
        return f"User {uid}: ERROR"

def test_race_condition(n=30):
    """Test concurrent booking of same seat."""
    print_header(f"Test 1: Race Condition ({n} users, 1 seat)")
    
    stats = Stats()
    
    print(f"Creating {n} users...")
    tokens = []
    for i in range(n):
        token = create_user(f"race_{i}")
        if token:
            tokens.append((i, token))
    
    print(f"✓ Created {len(tokens)} users")
    print(f"\nAll booking seat 1...")
    
    with ThreadPoolExecutor(max_workers=n) as executor:
        futures = [executor.submit(book_seat, uid, 1, token, stats) 
                   for uid, token in tokens]
        
        for future in as_completed(futures):
            print(f"  {future.result()}")
    
    s = stats.summary()
    print(f"\nResults:")
    print(f"  Success: {s['success']} (expected: 1)")
    print(f"  Failed: {s['failed']} (expected: {n-1})")
    print(f"  Errors: {s['errors']}")
    print(f"  Avg time: {s['avg_time']:.3f}s")
    
    if s['success'] == 1 and s['errors'] == 0:
        print("\n✓ PASS")
        return True
    elif s['success'] == 0:
        print("\n❌ FAIL: No bookings succeeded (show may not exist)")
        return False
    else:
        print("\n❌ FAIL")
        return False

def test_load(n=50, seats=20):
    """Test system under load."""
    print_header(f"Test 2: Load Test ({n} users, {seats} seats)")
    
    stats = Stats()
    
    print(f"Creating {n} users...")
    tokens = []
    for i in range(n):
        token = create_user(f"load_{i}")
        if token:
            tokens.append((i, token))
    
    print(f"✓ Created {len(tokens)} users")
    print(f"\nStarting load test...")
    
    start = time.time()
    assignments = [(uid, token, (uid % seats) + 1) for uid, token in tokens]
    
    with ThreadPoolExecutor(max_workers=n) as executor:
        futures = [executor.submit(book_seat, uid, seat, token, stats)
                   for uid, token, seat in assignments]
        
        for future in as_completed(futures):
            future.result()
    
    total_time = time.time() - start
    s = stats.summary()
    
    print(f"\nResults:")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Throughput: {s['total']/total_time:.2f} req/s")
    print(f"  Success: {s['success']}")
    print(f"  Failed: {s['failed']}")
    print(f"  Errors: {s['errors']}")
    print(f"  Avg time: {s['avg_time']:.3f}s")
    
    error_rate = s['errors'] / s['total'] if s['total'] > 0 else 1
    
    if error_rate < 0.1:
        print(f"\n✓ PASS (error rate: {error_rate*100:.1f}%)")
        return True
    else:
        print(f"\n❌ FAIL (high error rate: {error_rate*100:.1f}%)")
        return False

def verify_integrity():
    """Verify no double booking."""
    print_header("Test 3: Integrity Verification")
    
    try:
        stub = booking_pb2_grpc.BookingServiceStub(grpc.insecure_channel(BOOKING_NODES[0]))
        req = booking_pb2.ListSeatsRequest(show_id=TEST_SHOW, page_size=100, page_token=0)
        resp = stub.ListSeats(req, timeout=5)
        
        booked = [s for s in resp.seats if s.reserved]
        available = [s for s in resp.seats if not s.reserved]
        
        print(f"  Total: {len(resp.seats)}")
        print(f"  Booked: {len(booked)}")
        print(f"  Available: {len(available)}")
        
        if len(resp.seats) == 0:
            print(f"\n⚠️  WARNING: Show has no seats (creation failed)")
            return False
        
        booking_ids = [s.booking_id for s in booked]
        unique = len(set(booking_ids))
        
        if unique == len(booked):
            print(f"\n✓ PASS: All {len(booked)} bookings unique")
            return True
        else:
            print(f"\n❌ FAIL: Duplicates detected")
            return False
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def main():
    print("\n" + "█"*60)
    print("█  STRESS TEST SUITE")
    print("█"*60)
    
    setup()
    
    test1 = test_race_condition(30)
    time.sleep(2)
    
    test2 = test_load(50, 20)
    time.sleep(2)
    
    test3 = verify_integrity()
    
    print_header("SUMMARY")
    print(f"Test 1 (Race): {'✓ PASS' if test1 else '❌ FAIL'}")
    print(f"Test 2 (Load): {'✓ PASS' if test2 else '❌ FAIL'}")
    print(f"Test 3 (Integrity): {'✓ PASS' if test3 else '❌ FAIL'}")
    
    if test1 and test2 and test3:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())