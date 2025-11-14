"""
Enhanced Client CLI for Distributed Ticket Booking System
Features: Show listings, improved booking flow, booking history, and more
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
user_bookings = []  # Track user's bookings in this session
ADMIN_ID = "00000000-0000-0000-0000-000000000000"

# Configuration for Booking Peers
BOOKING_PEERS = [
    "127.0.0.1:50051",
    "127.0.0.1:50052",
    "127.0.0.1:50053",
]
CURRENT_BOOKING_TARGET = BOOKING_PEERS[0]

# Known shows cache (populated by list_all_shows)
available_shows = {}


def print_banner():
    """Display welcome banner"""
    print("\n" + "="*70)
    print("    DISTRIBUTED TICKET BOOKING SYSTEM")
    print("    Powered by Raft Consensus & Microservices")
    print("="*70 + "\n")


def print_section_header(title):
    """Print a formatted section header"""
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}\n")


def register_user(stub):
    """Register a new user account"""
    print_section_header("USER REGISTRATION")
    email = input("Enter email for registration: ")
    password = input("Enter password: ")
    request = auth_pb2.RegisterRequest(email=email, password=password)
    response = stub.Register(request)
    
    if response.success:
        print(f"\n✓ SUCCESS: {response.message}\n")
    else:
        print(f"\n✗ ERROR: {response.message}\n")


def login_user(stub):
    """Login existing user"""
    global session_token, cli_user_id
    print_section_header("USER LOGIN")
    email = input("Enter email: ")
    password = input("Enter password: ")
    request = auth_pb2.LoginRequest(email=email, password=password)
    response = stub.Login(request)
    
    if response.success:
        session_token = response.session.token
        cli_user_id = response.session.user_id
        is_admin = (cli_user_id == ADMIN_ID)
        role = "ADMIN" if is_admin else "USER"
        print(f"\n✓ Login Successful!")
        print(f"   Role: {role}")
        print(f"   User ID: {cli_user_id}")
        print(f"   Session Token: {session_token[:16]}...")
    else:
        session_token = None
        cli_user_id = None
        print(f"\n✗ Login Failed: {response.message}")
    print()


def list_all_shows(stub):
    """List all available shows using the ListShows RPC"""
    global available_shows, CURRENT_BOOKING_TARGET
    print_section_header("AVAILABLE SHOWS")
    
    available_shows = {}
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]
    
    for peer_addr in peers_to_try:
        try:
            if peer_addr != CURRENT_BOOKING_TARGET:
                CURRENT_BOOKING_TARGET = peer_addr
                channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            print(f"[INFO] Fetching shows from {CURRENT_BOOKING_TARGET}...")
            
            # Use the new ListShows RPC
            request = booking_pb2.ListShowsRequest()
            response = stub.ListShows(request, timeout=5.0)
            
            if not response.shows:
                print("\n✗ No shows found. Admin needs to add shows using option 9.\n")
                print("TIP: Default admin login is admin@gmail.com / admin123\n")
                return False
            
            # Populate available_shows cache
            for show in response.shows:
                available_shows[show.show_id] = {
                    'price_cents': show.price_cents,
                    'total_seats': show.total_seats,
                    'available_count': show.available_seats,
                    'booked_count': show.booked_seats
                }
            
            # Display shows with detailed information
            print(f"\n{'Show ID':<20} {'Price':<12} {'Seats':<15} {'Available':<12} {'Status'}")
            print("─" * 75)
            
            for show in response.shows:
                price_display = f"${show.price_cents/100:.2f}"
                seats_display = f"{show.total_seats} total"
                available_display = f"{show.available_seats}/{show.total_seats}"
                availability_pct = (show.available_seats / show.total_seats * 100) if show.total_seats > 0 else 0
                
                if availability_pct > 50:
                    status = "✓ Available"
                elif availability_pct > 20:
                    status = "⚠ Limited"
                elif availability_pct > 0:
                    status = "⚠ Almost Full"
                else:
                    status = "✗ Sold Out"
                
                print(f"{show.show_id:<20} {price_display:<12} {seats_display:<15} {available_display:<12} {status}")
            
            print(f"\n[INFO] Found {len(response.shows)} show(s)\n")
            return True
            
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print(f"[ERROR] Node {peer_addr} unavailable, trying next...")
                continue
            elif e.code() == grpc.StatusCode.UNIMPLEMENTED:
                # Fallback to old method if ListShows is not implemented
                print(f"[WARNING] ListShows not implemented on {peer_addr}, using fallback method...")
                return list_all_shows_fallback(stub)
            else:
                print(f"[ERROR] RPC error: {e.details()}")
                continue
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            continue
    
    print("\n✗ Could not connect to any booking node.\n")
    return False


def list_all_shows_fallback(stub):
    """Fallback method: Scan for shows by trying common show IDs"""
    global available_shows, CURRENT_BOOKING_TARGET
    
    print("[INFO] Using fallback discovery method...")
    
    # Comprehensive list of potential show IDs
    potential_shows = [
        "concert_2025", "dj_2025", "default_show", "show_2025",
        "rock_concert", "jazz_night", "comedy_show", "pop_concert",
        "classical_music", "metal_concert", "indie_show", "edm_festival",
        "sports_event", "theater_show", "opera_night", "ballet_show",
        "festival_2025", "charity_concert", "special_event",
        "summer_concert", "winter_show", "holiday_special"
    ]
    
    available_shows = {}
    
    for show_id in potential_shows:
        try:
            request = booking_pb2.ListSeatsRequest(
                show_id=show_id,
                page_size=10,
                page_token=0
            )
            response = stub.ListSeats(request, timeout=1.0)
            
            if response.seats and len(response.seats) > 0:
                seat = response.seats[0]
                
                # Count total and available seats
                total_seats = len(response.seats)
                page_token = response.next_page_token
                
                while page_token != 0:
                    try:
                        next_req = booking_pb2.ListSeatsRequest(
                            show_id=show_id,
                            page_size=50,
                            page_token=page_token
                        )
                        next_resp = stub.ListSeats(next_req, timeout=1.0)
                        total_seats += len(next_resp.seats)
                        page_token = next_resp.next_page_token
                    except:
                        break
                
                available_shows[show_id] = {
                    'price_cents': seat.price_cents,
                    'total_seats': total_seats,
                    'available_count': 0,
                    'booked_count': 0
                }
                print(f"   ✓ Found: {show_id}")
        except:
            continue
    
    if not available_shows:
        print("\n✗ No shows found.\n")
        return False
    
    print(f"\n{'Show ID':<20} {'Price':<12} {'Total Seats':<12} {'Status'}")
    print("─" * 60)
    for show_id, info in available_shows.items():
        price_display = f"${info['price_cents']/100:.2f}"
        print(f"{show_id:<20} {price_display:<12} {info['total_seats']:<12} Available")
    print()
    return True


def view_show_details(stub):
    """View detailed information about a specific show"""
    global CURRENT_BOOKING_TARGET
    
    if not available_shows:
        print("\n[INFO] Loading available shows first...")
        if not list_all_shows(stub):
            return
    
    print_section_header("VIEW SHOW DETAILS")
    show_id = input("Enter show ID: ")
    
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]
    
    for peer_addr in peers_to_try:
        try:
            if peer_addr != CURRENT_BOOKING_TARGET:
                CURRENT_BOOKING_TARGET = peer_addr
                channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            # Fetch all seats for the show
            all_seats = []
            current_page_token = 0
            
            while True:
                request = booking_pb2.ListSeatsRequest(
                    show_id=show_id,
                    page_size=50,
                    page_token=current_page_token
                )
                response = stub.ListSeats(request)
                
                if not response.seats and not all_seats:
                    print(f"\n✗ Show '{show_id}' not found.\n")
                    return
                
                all_seats.extend(response.seats)
                if response.next_page_token == 0:
                    break
                current_page_token = response.next_page_token
            
            # Calculate statistics
            total_seats = len(all_seats)
            booked_seats = sum(1 for s in all_seats if s.reserved)
            available_seats = total_seats - booked_seats
            price = all_seats[0].price_cents if all_seats else 0
            
            # Display show information
            print(f"\n{'='*60}")
            print(f"  SHOW: {show_id}")
            print(f"{'='*60}")
            print(f"  Price per seat:     ${price/100:.2f}")
            print(f"  Total seats:        {total_seats}")
            print(f"  Available seats:    {available_seats} ({available_seats/total_seats*100:.1f}%)")
            print(f"  Booked seats:       {booked_seats} ({booked_seats/total_seats*100:.1f}%)")
            print(f"{'='*60}\n")
            
            # Display seat matrix
            print("SEAT MAP (✓ = Available | ✗ = Booked)")
            print("─" * 60)
            
            all_seats.sort(key=lambda s: s.seat_id)
            seats_per_row = 10
            
            for i in range(0, len(all_seats), seats_per_row):
                row_seats = all_seats[i:i+seats_per_row]
                row_str = ""
                for seat in row_seats:
                    status = "✗" if seat.reserved else "✓"
                    row_str += f" [{seat.seat_id:>3}{status}] "
                print(row_str)
            print()
            return
            
        except grpc.RpcError:
            continue
    
    print("\n✗ Could not connect to any booking node.\n")


def book_seat(stub):
    """Book a seat with improved flow"""
    global session_token, cli_user_id, CURRENT_BOOKING_TARGET, user_bookings
    
    if not session_token:
        print("\n✗ ERROR: You must log in first to book a seat.\n")
        return
    
    # List available shows first
    if not available_shows:
        print("\n[INFO] Loading available shows...")
        if not list_all_shows(stub):
            return
    
    print_section_header("BOOK A SEAT")
    
    # Show selection
    print("Available Shows:")
    for idx, (show_id, info) in enumerate(available_shows.items(), 1):
        print(f"  {idx}. {show_id} - ${info['price_cents']/100:.2f}")
    
    try:
        choice = int(input("\nSelect show number: "))
        show_id = list(available_shows.keys())[choice - 1]
    except (ValueError, IndexError):
        print("\n✗ Invalid selection.\n")
        return
    
    # Seat selection
    seat_id = int(input("Enter seat ID to book: "))
    
    # Payment information
    print(f"\nPrice: ${available_shows[show_id]['price_cents']/100:.2f}")
    card_number = input("Enter Credit Card Number (Use 9999 to simulate failure): ")
    
    # Booking process with retries
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]
    
    for peer_addr in peers_to_try:
        try:
            if peer_addr != CURRENT_BOOKING_TARGET:
                print(f"[RETRY] Redirecting to {peer_addr}")
                CURRENT_BOOKING_TARGET = peer_addr
                channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            print(f"[ATTEMPT] Booking via {CURRENT_BOOKING_TARGET}...")
            
            request = booking_pb2.BookRequest(
                user_id=session_token,
                seat_id=seat_id,
                show_id=show_id,
                payment_token=card_number
            )
            
            response = stub.BookSeat(request)
            
            if response.success:
                print(f"\n{'='*60}")
                print("  ✓ BOOKING CONFIRMED!")
                print(f"{'='*60}")
                print(f"  Show:         {show_id}")
                print(f"  Seat:         {seat_id}")
                print(f"  Booking ID:   {response.booking_id}")
                print(f"  Node:         {CURRENT_BOOKING_TARGET}")
                print(f"{'='*60}\n")
                
                # Track booking
                user_bookings.append({
                    'show_id': show_id,
                    'seat_id': seat_id,
                    'booking_id': response.booking_id
                })
                return
            else:
                if "not the Raft leader" in response.message:
                    continue
                print(f"\n✗ Booking Failed: {response.message}\n")
                return
                
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                continue
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                print(f"[ERROR] Node {peer_addr} unavailable")
                continue
            else:
                print(f"\n✗ Error: {e.details()}\n")
                return
    
    print("\n✗ CRITICAL: Could not complete booking on any node.\n")


def view_my_bookings():
    """Display user's booking history"""
    print_section_header("MY BOOKINGS")
    
    if not user_bookings:
        print("You have no bookings in this session.\n")
        return
    
    print(f"{'Show ID':<20} {'Seat':<10} {'Booking ID':<40}")
    print("─" * 70)
    for booking in user_bookings:
        print(f"{booking['show_id']:<20} {booking['seat_id']:<10} {booking['booking_id']:<40}")
    print()


def add_show(stub):
    """Admin function to add a new show"""
    global session_token, cli_user_id, CURRENT_BOOKING_TARGET
    
    if cli_user_id != ADMIN_ID:
        print("\n✗ ERROR: Only admin users can add shows.\n")
        return
    
    if not session_token:
        print("\n✗ ERROR: You must log in as admin first.\n")
        return
    
    print_section_header("ADD NEW SHOW (Admin)")
    
    show_id = input("Enter Show ID (e.g., concert_2025): ")
    total_seats = int(input("Enter Total Seats: "))
    price_dollars = float(input("Enter Price in dollars (e.g., 10.50): "))
    price_cents = int(price_dollars * 100)
    
    peers_to_try = [CURRENT_BOOKING_TARGET] + [p for p in BOOKING_PEERS if p != CURRENT_BOOKING_TARGET]
    
    for peer_addr in peers_to_try:
        try:
            if peer_addr != CURRENT_BOOKING_TARGET:
                print(f"[RETRY] Redirecting to {peer_addr}")
                CURRENT_BOOKING_TARGET = peer_addr
                channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
                stub = booking_pb2_grpc.BookingServiceStub(channel)
            
            print(f"[ATTEMPT] Adding show via {CURRENT_BOOKING_TARGET}...")
            
            request = booking_pb2.AddShowRequest(
                user_id=session_token,
                show_id=show_id,
                total_seats=total_seats,
                price_cents=price_cents
            )
            
            response = stub.AddShow(request)
            
            if response.success:
                print(f"\n✓ SUCCESS: {response.message}")
                print(f"   Show ID: {show_id}")
                print(f"   Seats: {total_seats}")
                print(f"   Price: ${price_cents/100:.2f}")
                print(f"   Node: {CURRENT_BOOKING_TARGET}\n")
                
                # Update cache
                available_shows[show_id] = {
                    'price_cents': price_cents,
                    'total_seats': total_seats
                }
                return
            else:
                if "not the Raft leader" in response.message:
                    continue
                print(f"\n✗ Failed: {response.message}\n")
                return
                
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                continue
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                continue
            else:
                print(f"\n✗ Error: {e.details()}\n")
                return
    
    print("\n✗ Could not add show on any node.\n")


def ask_chatbot(chatbot_stub):
    """Interactive chatbot assistant"""
    print_section_header("BOOKING ASSISTANT")
    print("Type your question or 'back' to return to menu\n")
    
    while True:
        msg = input("You: ")
        if msg.lower() in ['back', 'exit', 'quit']:
            break
        
        response = chatbot_stub.Ask(
            chatbot_pb2.AskRequest(user_id="cli_user", text=msg)
        )
        
        print(f"\nAssistant: {response.reply_text}\n")
        
        if response.suggestions:
            print("Suggestions:")
            for s in response.suggestions:
                print(f"  • {s.title}")
            print()


def process_payment(payment_stub):
    """Standalone payment test"""
    print_section_header("STANDALONE PAYMENT TEST")
    
    user_id = input("Enter user ID: ")
    amount_dollars = float(input("Enter amount in dollars: "))
    amount_cents = int(amount_dollars * 100)
    currency = input("Currency (e.g., USD): ")
    card_number = input("Enter Credit Card Number (Use 9999 to fail): ")
    
    req = payment_pb2.PaymentRequest(
        user_id=user_id,
        payment_method_id="demo-card",
        currency=currency,
        amount_cents=amount_cents,
        card_number=card_number
    )
    resp = payment_stub.ProcessPayment(req)
    
    print(f"\n{'─'*50}")
    print(f"  Status: {resp.status}")
    print(f"  Success: {resp.success}")
    print(f"  Message: {resp.message}")
    print(f"  Transaction ID: {resp.transaction_id}")
    print(f"{'─'*50}\n")


def main():
    global CURRENT_BOOKING_TARGET
    
    # Connect to services
    booking_channel = grpc.insecure_channel(CURRENT_BOOKING_TARGET)
    booking_stub = booking_pb2_grpc.BookingServiceStub(booking_channel)
    
    payment_channel = grpc.insecure_channel("127.0.0.1:6000")
    payment_stub = payment_pb2_grpc.PaymentServiceStub(payment_channel)
    
    chatbot_channel = grpc.insecure_channel("127.0.0.1:9000")
    chatbot_stub = chatbot_pb2_grpc.ChatbotStub(chatbot_channel)
    
    auth_channel = grpc.insecure_channel("127.0.0.1:8000")
    auth_stub = auth_pb2_grpc.AuthServiceStub(auth_channel)
    
    print_banner()
    
    while True:
        status = f"Logged in as: {cli_user_id[:12]}..." if cli_user_id else "Not Logged In"
        role = " [ADMIN]" if cli_user_id == ADMIN_ID else ""
        
        print(f"\n{'═'*70}")
        print(f"  Status: {status}{role}")
        print(f"  Target Node: {CURRENT_BOOKING_TARGET}")
        print(f"{'═'*70}")
        print("\n[SHOWS & BOOKING]")
        print("  1. List All Shows")
        print("  2. View Show Details")
        print("  3. Book a Seat")
        print("  4. My Bookings")
        
        print("\n[ACCOUNT]")
        print("  5. Register User")
        print("  6. Login User")
        
        print("\n[SERVICES]")
        print("  7. Booking Assistant (Chatbot)")
        print("  8. Payment Test")
        
        if cli_user_id == ADMIN_ID:
            print("\n[ADMIN]")
            print("  9. Add/Update Show")
        
        print("\n  0. Exit")
        print()
        
        choice = input("Select option: ")
        
        if choice == "1":
            list_all_shows(booking_stub)
        elif choice == "2":
            view_show_details(booking_stub)
        elif choice == "3":
            book_seat(booking_stub)
        elif choice == "4":
            view_my_bookings()
        elif choice == "5":
            register_user(auth_stub)
        elif choice == "6":
            login_user(auth_stub)
        elif choice == "7":
            ask_chatbot(chatbot_stub)
        elif choice == "8":
            process_payment(payment_stub)
        elif choice == "9" and cli_user_id == ADMIN_ID:
            add_show(booking_stub)
        elif choice == "0":
            print("\nThank you for using the Distributed Ticket Booking System!\n")
            break
        else:
            print("\n✗ Invalid choice. Please try again.\n")


if __name__ == "__main__":
    main()