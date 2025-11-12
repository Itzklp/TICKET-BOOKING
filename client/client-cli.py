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
# Define the admin user ID for local checks, matching auth-server.py
ADMIN_ID = "00000000-0000-0000-0000-000000000000" 

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


def add_show(stub):
    """Admin RPC to add a new show, handling Raft leader redirection."""
    global session_token, cli_user_id, CURRENT_BOOKING_TARGET
    if cli_user_id != ADMIN_ID:
        print("\n[ERROR] Only the admin user can add shows. Please log in as admin.\n")
        return
        
    if not session_token:
        print("\n[ERROR] You must log in first (Option 7).\n")
        return
        
    show_id = input("Enter Show ID (e.g., concert_2025): ")
    total_seats = int(input("Enter Total Seats: "))
    price_cents = int(input("Enter Price (in cents, e.g., 1000): "))
    
    # --- Dynamic Retry Loop (Raft Leader Discovery) ---
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]

    response = None
    success = False
    
    for peer_addr in peers_to_try:
        try:
            # 1. Update the current target connection if we're trying a new peer
            if peer_addr != CURRENT_BOOKING_TARGET:
                 print(f"[RETRY] Redirecting to next peer: {peer_addr}")
                 CURRENT_BOOKING_TARGET = peer_addr
                 channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                 stub = booking_pb2_grpc.BookingServiceStub(channel)
                 
            print(f"[ATTEMPT] Trying AddShow via {CURRENT_BOOKING_TARGET}...")

            request = booking_pb2.AddShowRequest(
                user_id=session_token,
                show_id=show_id,
                total_seats=total_seats,
                price_cents=price_cents
            )
            
            response = stub.AddShow(request) 
            
            if response.success:
                success = True
                break
            
            # If not success, check if it's a known Raft error or a business error
            if not response.success and "not the Raft leader" in response.message:
                continue # Retry next peer
            if not response.success:
                break # Stop on definitive business logic failure

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                print(f"[INFO] {peer_addr} is not the leader. Trying next peer...")
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                print(f"[ERROR] Node {peer_addr} is unavailable. Trying next peer...")
            else:
                print(f"[ERROR] Unhandled RPC error connecting to {peer_addr}: {e.details()}")
                break 
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}")
            break

    
    if success and response:
         print(
            (
                f"\nAdd Show Response: {response.message} "
                f"(Success: {response.success}) via {CURRENT_BOOKING_TARGET}\n"
            )
        )
    elif response:
        print(f"\nAdd Show Failed: {response.message}\n")
    else:
        print("\n[CRITICAL] Add Show failed: Could not connect to any booking node or an unhandled error occurred.\n")


def book_seat(stub):
    global session_token, cli_user_id, CURRENT_BOOKING_TARGET
    if not session_token:
        print("\n[ERROR] You must log in first (Option 7) to book a seat.\n")
        return
    
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID (e.g., concert_2025): ") 
    # --- EXPLICIT PAYMENT INPUT ---
    card_number = input("Enter Credit Card Number (Use 9999 to simulate payment failure): ")

    # --- Dynamic Retry Loop (Raft Leader Discovery) ---
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
                show_id=show_id,
                payment_token=card_number # Sending card number via this field
            )
            
            response = stub.BookSeat(request)
            
            if response.success:
                success = True
                break
            
            # If not success, check if it's a known Raft error or a business error
            if not response.success and "not the Raft leader" in response.message:
                continue # Retry next peer
            if not response.success:
                break # Stop on definitive business logic failure (e.g., seat already booked, payment failed)

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                print(f"[INFO] {peer_addr} is not the leader. Trying next peer...")
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                print(f"[ERROR] Node {peer_addr} is unavailable. Trying next peer...")
            else:
                print(f"[ERROR] Unhandled RPC error connecting to {peer_addr}: {e.details()}")
                break 
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}")
            break
    
    # --- FIX: Explicitly print the detailed failure message ---
    if success and response:
         print(
            (
                f"\n--- BOOKING SUCCESS ---\nMessage: {response.message} "
                f"\nTarget Node: {CURRENT_BOOKING_TARGET}\n-----------------------\n"
            )
        )
    elif response:
        # Business logic failure (e.g., payment failed, seat booked, authentication)
        print(f"\n--- BOOKING FAILED ---\nReason: {response.message}\nTarget Node: {CURRENT_BOOKING_TARGET}\n----------------------\n")
    else:
        # Critical connection failure
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
        seat = response.seat
        # Fetch price from the seat object, which the server now returns
        price_info = f" (Price: {seat.price_cents/100:.2f} USD)" if seat and seat.price_cents else ""
        print(f"Seat {seat_id} available: {response.available}{price_info} via {CURRENT_BOOKING_TARGET}")
    elif response:
        print(f"Query Failed: Received response, but unable to parse or seat not found.")
    else:
        print("\n[CRITICAL] Query failed: Could not connect to any booking node or an unhandled error occurred.\n")


def list_all_seats(stub):
    """
    Fetches all seats for a show and displays them in a matrix.
    A read operation should work on any available follower/leader node.
    """
    global CURRENT_BOOKING_TARGET
    
    show_id = input("Enter show ID (e.g., dj_2025): ")
    
    # We will try all known peers, starting from the current target
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]

    all_seats = []
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
                 
            print(f"[ATTEMPT] Trying ListSeats via {CURRENT_BOOKING_TARGET}...")

            # 2. Handle pagination - loop until next_page_token is 0
            current_page_token = 0
            while True:
                request = booking_pb2.ListSeatsRequest(
                    show_id=show_id, 
                    page_size=50,  # Fetch in chunks of 50
                    page_token=current_page_token
                )
                
                response = stub.ListSeats(request)
                
                if not response.seats and not all_seats:
                    # Show might not exist or has 0 seats
                    print(f"\nNo seats found for show '{show_id}' via {CURRENT_BOOKING_TARGET}.\n")
                    return # Exit function
                
                all_seats.extend(response.seats)
                
                if response.next_page_token == 0:
                    break # All pages fetched
                current_page_token = response.next_page_token

            success = True
            break # Succeeded, exit peer retry loop
            
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
    
    if not success:
        print("\n[CRITICAL] ListSeats failed: Could not connect to any booking node.\n")
        return

    # --- Display Matrix ---
    if not all_seats:
        print(f"No seats configured for show '{show_id}'.")
        return

    print(f"\n--- Seat Matrix for Show: '{show_id}' (via {CURRENT_BOOKING_TARGET}) ---")
    print(" [ X ] = Booked    [ # ] = Available\n")
    
    # Sort seats by ID to ensure correct order
    all_seats.sort(key=lambda s: s.seat_id)
    
    # Assume 10 seats per row for display
    seats_per_row = 10
    row_str = ""
    for seat in all_seats:
        if seat.reserved:
            row_str += " [ X ] "
        else:
            # Pad seat number for alignment
            row_str += f" [{seat.seat_id:^3}] "
        
        if seat.seat_id % seats_per_row == 0:
            print(row_str)
            row_str = ""
    
    # Print any remaining seats in the last row
    if row_str:
        print(row_str)
    
    print("\n" + ("-" * (seats_per_row * 7)) + "\n")


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
    """Standalone test for payment, now prompts for inputs."""
    user_id = input("Enter user ID: ")
    amount = int(input("Enter amount (in cents): "))
    currency = input("Currency (e.g., USD): ")
    # --- NEW: Prompt for Card Number ---
    card_number = input("Enter Credit Card Number (Use 9999 to simulate payment failure): ")

    req = payment_pb2.PaymentRequest(
        user_id=user_id,
        payment_method_id="demo-card",
        currency=currency,
        amount_cents=amount,
        card_number=card_number # Use the input card number
    )
    resp = payment_stub.ProcessPayment(req)
    # --- FIX: Explicitly show payment status and message ---
    print(f"\n--- STANDALONE PAYMENT RESULT ---")
    print(f"Status: {resp.status} (Success: {resp.success})")
    print(f"Message: {resp.message}")
    print(f"Transaction ID: {resp.transaction_id}")
    print("---------------------------------\n")


def main():
    global CURRENT_BOOKING_TARGET
    
    # Connect to services - we use CURRENT_BOOKING_TARGET for the initial connection only
    booking_channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
    booking_stub = booking_pb2_grpc.BookingServiceStub(booking_channel)

    payment_channel = grpc.insecure_channel("127.0.0.1:6000")
    payment_stub = payment_pb2_grpc.PaymentServiceStub(payment_channel)

    chatbot_channel = grpc.insecure_channel("127.0.0.1:9000")
    chatbot_stub = chatbot_pb2_grpc.ChatbotStub(chatbot_channel)
    
    auth_channel = grpc.insecure_channel("127.0.0.1:8000") 
    auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)   

    while True:
        status_line = f"Logged in as: {cli_user_id[:8]}..." if cli_user_id else "Not Logged In"
        
        print(f"\n=== Distributed Ticket Booking CLI ({status_line} - Target: {CURRENT_BOOKING_TARGET}) ===")
        print("1. Book a Seat (Requires Login)")
        print("2. Query Single Seat")
        print("3. List All Seats (Seat Matrix)") # <-- NEW OPTION
        print("4. Process Payment (Standalone Test)")
        print("5. Chat with Chatbot")
        print("6. Register User (Auth)") 
        print("7. Login User (Auth)")    
        print("8. Admin: Add/Update Show (Requires Admin Login)") 
        print("9. Exit")                 # <-- UPDATED EXIT NUMBER

        choice = input("Select option: ")

        if choice == "1":
            book_seat(booking_stub)
        elif choice == "2":
            query_seat(booking_stub)
        elif choice == "3":
            list_all_seats(booking_stub) # <-- NEW HANDLER
        elif choice == "4":
            process_payment(payment_stub)
        elif choice == "5":
            ask_chatbot(chatbot_stub)
        elif choice == "6":
            register_user(auth_stub) 
        elif choice == "7":
            login_user(auth_stub)    
        elif choice == "8":
            add_show(booking_stub)
        elif choice == "9":               # <-- UPDATED EXIT NUMBER
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()