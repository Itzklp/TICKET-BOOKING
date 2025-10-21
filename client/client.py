"""
Client CLI for interacting with Booking, Payment, and Chatbot services.
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


def book_seat(stub):
    user_id = input("Enter user ID: ")
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID: ")

    request = booking_pb2.BookRequest(
        user_id=user_id,
        seat_id=seat_id,
        show_id=show_id
    )
    response = stub.BookSeat(request)
    print(f"\nBooking Response: {response.message} (Success: {response.success})\n")


def query_seat(stub):
    seat_id = int(input("Enter seat ID: "))
    show_id = input("Enter show ID: ")
    request = booking_pb2.QueryRequest(show_id=show_id, seat_id=seat_id)
    response = stub.QuerySeat(request)
    print(f"Seat {seat_id} available: {response.available}")


def ask_chatbot(chatbot_stub):
    msg = input("You: ")
    response = chatbot_stub.Ask(chatbot_pb2.AskRequest(user_id="cli_user", text=msg))
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
    # Connect to services
    booking_channel = grpc.insecure_channel("127.0.0.1:50051")
    booking_stub = booking_pb2_grpc.BookingServiceStub(booking_channel)

    payment_channel = grpc.insecure_channel("127.0.0.1:6000")
    payment_stub = payment_pb2_grpc.PaymentServiceStub(payment_channel)

    chatbot_channel = grpc.insecure_channel("127.0.0.1:7000")
    chatbot_stub = chatbot_pb2_grpc.ChatbotStub(chatbot_channel)

    while True:
        print("\n=== Distributed Ticket Booking CLI ===")
        print("1. Book a Seat")
        print("2. Query Seat")
        print("3. Process Payment")
        print("4. Chat with Chatbot")
        print("5. Exit")

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
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
