"""
Client CLI for interacting with Booking, Payment, Chatbot, and **Auth** services.
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
import proto.auth_pb2 as auth_pb2         # <--- ADD IMPORT
import proto.auth_pb2_grpc as auth_pb2_grpc # <--- ADD IMPORT

# Global variables to store session state
session_token = None
cli_user_id = None


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
    global session_token, cli_user_id
    if not session_token:
        print("\n[ERROR] You must log in first (Option 5) to book a seat.\n")
        return
    
    # We no longer prompt for user_id, as it's provided by the session token
    # The 'user_id' field in BookRequest is repurposed to carry the session_token
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID: ")

    request = booking_pb2.BookRequest(
        user_id=session_token, # <--- SEND THE SESSION TOKEN HERE
        seat_id=seat_id,
        show_id=show_id
    )
    response = stub.BookSeat(request)
    print(
        (
            f"\nBooking Response: {response.message} "
            f"(Success: {response.success})\n"
        )
    )

def query_seat(stub):
    # This function was missing and caused the NameError
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID: ")
    request = booking_pb2.QueryRequest(show_id=show_id, seat_id=seat_id)
    response = stub.QuerySeat(request)
    print(f"Seat {seat_id} available: {response.available}")


def ask_chatbot(chatbot_stub):
    # This function was missing
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
    # This function was missing
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
    
# ... (query_seat, ask_chatbot, process_payment functions remain largely the same, 
# you might want to update them to send the session_token/user_id for context/logging)

def main():
    # Connect to services
    booking_channel = grpc.insecure_channel("127.0.0.1:50051")
    booking_stub = booking_pb2_grpc.BookingServiceStub(booking_channel)

    payment_channel = grpc.insecure_channel("127.0.0.1:6000")
    payment_stub = payment_pb2_grpc.PaymentServiceStub(payment_channel)

    chatbot_channel = grpc.insecure_channel("127.0.0.1:7000")
    chatbot_stub = chatbot_pb2_grpc.ChatbotStub(chatbot_channel)
    
    auth_channel = grpc.insecure_channel("127.0.0.1:8000") # <--- ADD AUTH CHANNEL
    auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)   # <--- ADD AUTH STUB

    while True:
        status_line = f"Logged in as: {cli_user_id[:8]}..." if cli_user_id else "Not Logged In"
        
        print(f"\n=== Distributed Ticket Booking CLI ({status_line}) ===")
        print("1. Book a Seat")
        print("2. Query Seat")
        print("3. Process Payment")
        print("4. Chat with Chatbot")
        print("5. Register User (Auth)") # <--- NEW OPTION
        print("6. Login User (Auth)")    # <--- NEW OPTION
        print("7. Exit")                 # <--- UPDATED EXIT

        choice = input("Select option: ")

        if choice == "1":
            book_seat(booking_stub)
        elif choice == "2":
            query_seat(booking_stub)
        elif choice == "3":
            process_payment(payment_stub)
        elif choice == "4":
            ask_chatbot(chatbot_stub)
        elif choice == "5":
            register_user(auth_stub) # <--- CALL NEW FUNCTION
        elif choice == "6":
            login_user(auth_stub)    # <--- CALL NEW FUNCTION
        elif choice == "7":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()