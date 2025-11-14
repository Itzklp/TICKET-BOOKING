#!/usr/bin/env python3
"""
Stress Test for Distributed Ticket Booking System
Tests concurrent booking of the same seat by multiple users.
Expected: Exactly 1 success, all others fail gracefully.
"""

import grpc
import asyncio
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict


sys.path.append(os.path.dirname(__file__))

from proto import booking_pb2, booking_pb2_grpc
from proto import auth_pb2, auth_pb2_grpc

# Test Configuration
NUM_CONCURRENT_USERS = 30
TARGET_SEAT_ID = 1
SHOW_ID = "stress_test_show"
TOTAL_SEATS = 10
PRICE_CENTS = 100

# Admin credentials
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

# Booking nodes
BOOKING_NODES = [
    "127.0.0.1:50051",
    "127.0.0.1:50052", 
    "127.0.0.1:50053"
]


def get_admin_token():
    """Login as admin and get session token."""
    print(" Logging in as admin...")
    auth_channel = grpc.insecure_channel("127.0.0.1:8000")
    auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
    
    login_req = auth_pb2.LoginRequest(email=ADMIN_EMAIL, password=ADMIN_PASSWORD)
    login_resp = auth_stub.Login(login_req)
    
    if not login_resp.success:
        raise Exception(f"Admin login failed: {login_resp.message}")
    
    print(f" Admin logged in successfully (User ID: {login_resp.session.user_id[:8]}...)")
    return login_resp.session.token


def setup_test_show(admin_token):
    """Create a test show with admin privileges."""
    print(f"\n Setting up test show '{SHOW_ID}' with {TOTAL_SEATS} seats at ${PRICE_CENTS/100:.2f}...")
    
    # Try each node until we find the leader
    for node_addr in BOOKING_NODES:
        try:
            channel = grpc.insecure_channel(node_addr)
            stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            request = booking_pb2.AddShowRequest(
                user_id=admin_token,
                show_id=SHOW_ID,
                total_seats=TOTAL_SEATS,
                price_cents=PRICE_CENTS
            )
            
            response = stub.AddShow(request, timeout=5)
            
            if response.success:
                print(f" Show created successfully via {node_addr}")
                print(f"   Message: {response.message}")
                return True
            else:
                if "not the Raft leader" in response.message:
                    print(f" {node_addr} is not leader, trying next node...")
                    continue
                else:
                    print(f" Show creation failed: {response.message}")
                    return False
                    
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                print(f" {node_addr} is not leader, trying next node...")
                continue
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                print(f"  {node_addr} is unavailable, trying next node...")
                continue
            else:
                print(f" Error connecting to {node_addr}: {e.details()}")
                continue
                
    print(" Failed to create show on any node")
    return False


def create_test_user(user_num):
    """Register and login a test user."""
    email = f"user{user_num}@test.com"
    password = f"pass{user_num}"
    
    auth_channel = grpc.insecure_channel("127.0.0.1:8000")
    auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
    
    # Register
    reg_req = auth_pb2.RegisterRequest(email=email, password=password)
    reg_resp = auth_stub.Register(reg_req)
    
    # Login
    login_req = auth_pb2.LoginRequest(email=email, password=password)
    login_resp = auth_stub.Login(login_req)
    
    if login_resp.success:
        return login_resp.session.token
    else:
        raise Exception(f"Failed to create user {user_num}")


def attempt_booking(user_num, session_token):
    """
    Single user attempts to book the target seat.
    Returns: (user_num, success, message, node_used)
    """
    card_number = f"{1000 + user_num}"  # Valid card number
    
    # Try booking on each node until success or all fail
    for node_addr in BOOKING_NODES:
        try:
            channel = grpc.insecure_channel(node_addr)
            stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            request = booking_pb2.BookRequest(
                user_id=session_token,
                seat_id=TARGET_SEAT_ID,
                show_id=SHOW_ID,
                payment_token=card_number
            )
            
            response = stub.BookSeat(request, timeout=10)
            
            if response.success:
                return (user_num, True, response.message, node_addr)
            else:
                # If it's not a leader error, this is the final answer
                if "not the Raft leader" not in response.message:
                    return (user_num, False, response.message, node_addr)
                # Otherwise try next node
                    
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                continue  # Try next node
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                continue  # Try next node
            else:
                return (user_num, False, f"RPC Error: {e.details()}", node_addr)
    
    return (user_num, False, "All nodes failed or unavailable", "none")


def run_stress_test():
    """Main stress test execution."""
    print("\n" + "="*70)
    print(" STRESS TEST: Concurrent Booking Race Condition")
    print("="*70)
    
    # Phase 1: Setup
    print("\n Phase 1: Test Setup")
    print("-" * 70)
    
    admin_token = get_admin_token()
    
    if not setup_test_show(admin_token):
        print("\n Test setup failed. Exiting.")
        return
    
    print(f"\n Creating {NUM_CONCURRENT_USERS} test users...")
    user_tokens = []
    for i in range(NUM_CONCURRENT_USERS):
        try:
            token = create_test_user(i)
            user_tokens.append(token)
            if (i + 1) % 10 == 0:
                print(f"   Created {i + 1}/{NUM_CONCURRENT_USERS} users...")
        except Exception as e:
            print(f"  Failed to create user {i}: {e}")
    
    print(f" Successfully created {len(user_tokens)} users")
    
    # Phase 2: Concurrent Booking
    print("\n Phase 2: Concurrent Booking Attack")
    print("-" * 70)
    print(f" Target: Seat {TARGET_SEAT_ID} in show '{SHOW_ID}'")
    print(f" Launching {len(user_tokens)} concurrent booking requests...\n")
    
    # Use ThreadPoolExecutor for true concurrency
    results = []
    with ThreadPoolExecutor(max_workers=NUM_CONCURRENT_USERS) as executor:
        futures = [
            executor.submit(attempt_booking, i, token) 
            for i, token in enumerate(user_tokens)
        ]
        
        for future in futures:
            results.append(future.result())
    
    # Phase 3: Analysis
    print("\n Phase 3: Results Analysis")
    print("-" * 70)
    
    successes = [r for r in results if r[1]]
    failures = [r for r in results if not r[1]]
    
    print(f"\n Summary:")
    print(f"   Total Attempts:  {len(results)}")
    print(f"    Successes:    {len(successes)}")
    print(f"    Failures:     {len(failures)}")
    
    # Show detailed results
    if successes:
        print(f"\n Successful Bookings:")
        for user_num, _, message, node in successes:
            print(f"   User {user_num}: {message} (via {node})")
    
    # Categorize failures
    failure_reasons = defaultdict(list)
    for user_num, _, message, node in failures:
        # Extract key failure reason
        if "already reserved" in message.lower():
            reason = "Seat already booked"
        elif "payment" in message.lower():
            reason = "Payment failure"
        elif "invalid" in message.lower() or "out of range" in message.lower():
            reason = "Invalid seat"
        else:
            reason = message[:50]  # First 50 chars
        failure_reasons[reason].append(user_num)
    
    if failure_reasons:
        print(f"\n Failure Breakdown:")
        for reason, users in failure_reasons.items():
            print(f"   '{reason}': {len(users)} users")
            if len(users) <= 5:
                print(f"      Users: {users}")
    
    # Phase 4: Verdict
    print("\n" + "="*70)
    print(" TEST VERDICT")
    print("="*70)
    
    if len(successes) == 1 and len(failures) == len(results) - 1:
        print(" PASS: Exactly 1 booking succeeded, all others failed gracefully")
        print(" Raft consensus successfully prevented double-booking!")
        return True
    elif len(successes) == 0:
        print("  WARNING: No bookings succeeded (possible system issue)")
        return False
    elif len(successes) > 1:
        print(f" FAIL: {len(successes)} bookings succeeded (DOUBLE BOOKING DETECTED!)")
        print("💥 Raft consensus failed to prevent race condition!")
        return False
    else:
        print("  INCONCLUSIVE: Unexpected result pattern")
        return False


if __name__ == "__main__":
    try:
        success = run_stress_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)