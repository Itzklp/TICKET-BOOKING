"""
Client CLI for interacting with Booking, Payment, Chatbot, and Auth services.
Implements dynamic leader redirection for the distributed booking service.
"""

import grpc
import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import proto.booking_pb2 as booking_pb2
import proto.booking_pb2_grpc as booking_pb2_grpc
import proto.payment_pb2 as payment_pb2
import proto.payment_pb2_grpc as payment_pb2_grpc
import proto.chatbot_pb2 as chatbot_pb2
import proto.chatbot_pb2_grpc as chatbot_pb2_grpc
import proto.auth_pb2 as auth_pb2
import proto.auth_pb2_grpc as auth_pb2_grpc

# Global variables to store session state
session_token = None
cli_user_id = None

# --- Configuration for Booking Peers ---
BOOKING_PEERS = [
    "127.0.0.1:50051", # Node 1
    "127.0.0.1:50052", # Node 2
    "127.0.0.1:50053", # Node 3
]
# Start by trying the first peer in the list.
CURRENT_BOOKING_TARGET = BOOKING_PEERS[0]
# ---------------------------------------


def register_user(stub):
    email = input("Enter email for registration: ")
    password = input("Enter password: ")
    request = auth_pb2.RegisterRequest(email=email, password=password)
    response = stub.Register(request)
    print(f"\nRegistration Response: {response.message} (Success: {response.success})\n")


def login_user(stub):
    global session_token, cli_user_id
    email = input("Enter email: ")
    password = input("Enter password: ")
    request = auth_pb2.LoginRequest(email=email, password=password)
    response = stub.Login(request)
    if response.success:
        session_token = response.session.token
        cli_user_id = response.session.user_id
        print(f"\nLogin Successful! User ID: {cli_user_id}")
        print(f"Session Token: {session_token[:8]}... (Stored)")
    else:
        session_token = None
        cli_user_id = None
        print(f"\nLogin Failed: {response.message}")
    print("\n")


def book_seat(stub):
    global session_token, cli_user_id, CURRENT_BOOKING_TARGET
    if not session_token:
        print("\n[ERROR] You must log in first (Option 6) to book a seat.\n")
        return
    
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID: ")
    
    # --- Dynamic Retry Loop (Raft Leader Discovery) ---
    # We will try all known peers, starting from the current target
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]

    response = None
    success = False
    
    for peer_addr in peers_to_try:
        try:
            # 1. Update the current target connection if we're trying a new peer
            if peer_addr != CURRENT_BOOKING_TARGET:
                 print(f"[RETRY] Redirecting to next peer: {peer_addr}")
                 CURRENT_BOOKING_TARGET = peer_addr
                 # Re-create the stub for the new address
                 channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                 stub = booking_pb2_grpc.BookingServiceStub(channel)
                 
            print(f"[ATTEMPT] Trying booking via {CURRENT_BOOKING_TARGET}...")

            request = booking_pb2.BookRequest(
                user_id=session_token,
                seat_id=seat_id,
                show_id=show_id
            )
            
            response = stub.BookSeat(request)
            
            if response.success:
                success = True
                break
            
            # If successful is False, it means the seat was already booked (business logic failure)
            # This is not a Raft error, so we stop trying.
            if not response.success:
                break 

        except grpc.RpcError as e:
            # Check for the specific FAILED_PRECONDITION error (StatusCode.FAILED_PRECONDITION is 9)
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                # This is the expected 'Not Leader' error. Continue to next peer.
                print(f"[INFO] {peer_addr} is not the leader. Trying next peer...")
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                # Connection error (e.g., node is down). Continue to next peer.
                print(f"[ERROR] Node {peer_addr} is unavailable. Trying next peer...")
            else:
                # Handle other unrecoverable errors (e.g., INTERNAL)
                print(f"[ERROR] Unhandled RPC error connecting to {peer_addr}: {e.details()}")
                break 
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}")
            break


    # --- End Dynamic Retry Loop ---
    
    if success and response:
         print(
            (
                f"\nBooking Response: {response.message} "
                f"(Success: {response.success}) via {CURRENT_BOOKING_TARGET}\n"
            )
        )
    elif response:
        # Business logic failure (seat already booked or invalid)
        print(f"\nBooking Failed: {response.message}\n")
    else:
        # All peers failed to respond or unknown error
        print("\n[CRITICAL] Booking failed: Could not connect to any booking node or an unhandled error occurred.\n")


def query_seat(stub):
    """
    Dynamically attempts to query seat status across all peers.
    A read operation should work on any available follower/leader node.
    """
    global CURRENT_BOOKING_TARGET
    
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID: ")
    
    # We will try all known peers, starting from the current target
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]

    response = None
    success = False
    
    for peer_addr in peers_to_try:
        try:
            # 1. Update the current target connection if necessary
            if peer_addr != CURRENT_BOOKING_TARGET:
                 print(f"[RETRY] Redirecting query to next peer: {peer_addr}")
                 CURRENT_BOOKING_TARGET = peer_addr
                 # Re-create the stub for the new address
                 channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                 stub = booking_pb2_grpc.BookingServiceStub(channel)
                 
            print(f"[ATTEMPT] Trying query via {CURRENT_BOOKING_TARGET}...")

            request = booking_pb2.QueryRequest(show_id=show_id, seat_id=seat_id)
            
            # Read operation: simply tries to get a response
            response = stub.QuerySeat(request)
            success = True
            break 
            
        except grpc.RpcError as e:
            # Handle connection errors (UNAVAILABLE)
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print(f"[ERROR] Node {peer_addr} is unavailable. Trying next peer...")
                continue
            else:
                # Handle other unrecoverable errors 
                print(f"[ERROR] Unhandled RPC error connecting to {peer_addr}: {e.details()}")
                break
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}")
            break

    # --- End Dynamic Retry Loop ---
    
    if success and response:
        print(f"Seat {seat_id} available: {response.available} via {CURRENT_BOOKING_TARGET}")
    elif response:
        # Should not happen for query if successful=True
        print(f"Query Failed: Received response, but unable to parse.")
    else:
        print("\n[CRITICAL] Query failed: Could not connect to any booking node or an unhandled error occurred.\n")


def ask_chatbot(chatbot_stub):
    msg = input("You: ")
    response = chatbot_stub.Ask(
        chatbot_pb2.AskRequest(user_id="cli_user", text=msg)
    )
    print(f"Bot: {response.reply_text}")
    if response.suggestions:
        print("Suggestions:")
        for s in response.suggestions:
            print(f" - {s.title}")


def process_payment(payment_stub):
    user_id = input("Enter user ID: ")
    amount = int(input("Enter amount (in cents): "))
    currency = input("Currency (e.g., USD): ")

    req = payment_pb2.PaymentRequest(
        user_id=user_id,
        payment_method_id="demo-card",
        currency=currency,
        amount_cents=amount
    )
    resp = payment_stub.ProcessPayment(req)
    print(f"Payment Status: {resp.status} (ID: {resp.transaction_id})")
    

def main():
    global CURRENT_BOOKING_TARGET
    
    # Connect to services
    # We initialize the booking_stub only once against the initial target
    booking_channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
    booking_stub = booking_pb2_grpc.BookingServiceStub(booking_channel)

    payment_channel = grpc.insecure_channel("127.0.0.1:6000")
    payment_stub = payment_pb2_grpc.PaymentServiceStub(payment_channel)

    chatbot_channel = grpc.insecure_channel("127.0.0.1:7000")
    chatbot_stub = chatbot_pb2_grpc.ChatbotStub(chatbot_channel)
    
    auth_channel = grpc.insecure_channel("127.0.0.1:8000") 
    auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)   

    while True:
        status_line = f"Logged in as: {cli_user_id[:8]}..." if cli_user_id else "Not Logged In"
        
        print(f"\n=== Distributed Ticket Booking CLI ({status_line} - Target: {CURRENT_BOOKING_TARGET}) ===")
        print("1. Book a Seat")
        print("2. Query Seat")
        print("3. Process Payment")
        print("4. Chat with Chatbot")
        print("5. Register User (Auth)") 
        print("6. Login User (Auth)")    
        print("7. Exit")                 

        choice = input("Select option: ")

        if choice == "1":
            # The book_seat function handles dynamic stub switching internally
            book_seat(booking_stub)
        elif choice == "2":
            # The query_seat function handles dynamic stub switching internally
            query_seat(booking_stub)
        elif choice == "3":
            process_payment(payment_stub)
        elif choice == "4":
            ask_chatbot(chatbot_stub)
        elif choice == "5":
            register_user(auth_stub) 
        elif choice == "6":
            login_user(auth_stub)    
        elif choice == "7":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()