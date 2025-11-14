
import logging
import sys
import os
import json
import grpc

# Ensure the project root (e.g., "D:/Ticket Booking") is in Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from booking.seat_manager import SeatManager

from proto import booking_pb2, booking_pb2_grpc
from proto import auth_pb2, auth_pb2_grpc
from proto import payment_pb2, payment_pb2_grpc 

logger = logging.getLogger("booking_service")


ADMIN_ID = "00000000-0000-0000-0000-000000000000" 

class BookingServiceServicer(booking_pb2_grpc.BookingServiceServicer):
    def __init__(self, raft_node=None):
        # Initialize Seat Manager
        self.seat_manager = SeatManager(raft_node)
        
        # Load config to get Auth/Payment Service addresses
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "booking-node", "config.json")
        
        with open(config_path, "r") as f:
            cfg = json.load(f)

        # Initialize Auth Stub
        auth_cfg = cfg["services"]["auth_service"]
        auth_addr = f'{auth_cfg["host"]}:{auth_cfg["port"]}'
        self.auth_channel = grpc.insecure_channel(auth_addr)
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(self.auth_channel)
        logger.info("Connected Auth Service stub for validation at %s", auth_addr)
        
        # Initialize Payment Stub 
        payment_cfg = cfg["services"]["payment_service"]
        payment_addr = f'{payment_cfg["host"]}:{payment_cfg["port"]}'
        self.payment_channel = grpc.insecure_channel(payment_addr)
        self.payment_stub = payment_pb2_grpc.PaymentServiceStub(self.payment_channel)
        logger.info("Connected Payment Service stub at %s", payment_addr)
        
        
    # --- ADMIN RPC HANDLER ---
    async def AddShow(self, request, context):
        """Admin RPC to add a new show and set its seat capacity/price."""
        
        session_token = request.user_id 
        
        #  Validate Session Token and check for Admin user
        try:
            validation_req = auth_pb2.ValidateSessionRequest(token=session_token)
            validation_resp = self.auth_stub.ValidateSession(validation_req) 
        except Exception as e:
            logger.error("Auth service call failed: %s", e)
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            return booking_pb2.AddShowResponse(success=False, message="Authentication service unavailable.")

        if not validation_resp.valid or validation_resp.user_id != ADMIN_ID:
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
            context.set_details("Only the admin user can perform this operation.")
            return booking_pb2.AddShowResponse(success=False, message="Permission denied. Admin access required.")
        
        #  Proceed with add_show
        try:
            success = await self.seat_manager.add_show(
                request.show_id, request.total_seats, request.price_cents
            )
            if success:
                 return booking_pb2.AddShowResponse(success=True, message=f"Show {request.show_id} added/updated successfully.")
            else:
                 context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                 context.set_details("Raft node is not the leader or proposal failed.")
                 return booking_pb2.AddShowResponse(success=False, message="Show update failed (not leader or proposal failed).")

        except PermissionError:
             context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
             context.set_details("Booking node is not the Raft leader.")
             return booking_pb2.AddShowResponse(success=False, message="Show update failed: Current node is not the Raft leader.")
        except Exception as e:
             logger.error("Admin show proposal failed: %s", e)
             return booking_pb2.AddShowResponse(success=False, message="Internal error during show update.")
        
    async def ListShows(self, request, context):
        """List all available shows with their details."""
        try:

            all_shows = self.seat_manager.get_all_shows_info()

            if not all_shows:
                return booking_pb2.ListShowsResponse(shows=[])
        
            show_list = []
            for show_id, show_data in all_shows.items():
                total_seats = show_data.get('total_seats', 0)
                price_cents = show_data.get('price_cents', 0)
                seats_dict = show_data.get('seats', {})


                booked_count = sum(1 for seat_data in seats_dict.values() 
                             if seat_data.get('reserved', False))
                available_count = total_seats - booked_count
            
                show_info = booking_pb2.ShowInfo(
                    show_id=show_id,
                    total_seats=total_seats,
                    price_cents=price_cents,
                    available_seats=available_count,
                    booked_seats=booked_count
                )
                show_list.append(show_info)
        
            return booking_pb2.ListShowsResponse(shows=show_list)
        
        except Exception as e:
            logger.error("Error listing shows: %s", e)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal error while listing shows.")
            return booking_pb2.ListShowsResponse(shows=[])

    # --- BOOKING LOGIC ---
    async def BookSeat(self, request, context):
        #  Auth Validation 
        session_token = request.user_id 
        seat_id = request.seat_id
        show_id = request.show_id
        card_number = request.payment_token 

        try:
            validation_req = auth_pb2.ValidateSessionRequest(token=session_token)
            validation_resp = self.auth_stub.ValidateSession(validation_req) 
        except Exception as e:
            logger.error("Auth service call failed: %s", e)
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Authentication service unavailable.")
            return booking_pb2.BookResponse(success=False, message="Authentication service unavailable.", booking_id="", seat=None)

        if not validation_resp.valid:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid or expired session token.")
            return booking_pb2.BookResponse(success=False, message="Authentication failed. Please log in.", booking_id="", seat=None)

        authenticated_user_id = validation_resp.user_id
        
        #  Price Lookup
        price_cents = self.seat_manager.get_show_price(show_id)
        if price_cents is None:
             return booking_pb2.BookResponse(
                success=False,
                message=f"Booking failed: Show ID '{show_id}' not found or price not set.",
                booking_id="",
                seat=None
            )

        #  Call Payment Service
        try:
            payment_req = payment_pb2.PaymentRequest(
                user_id=authenticated_user_id,
                payment_method_id="demo-card", 
                currency="USD", 
                amount_cents=price_cents,
                card_number=card_number 
            )
            payment_resp = self.payment_stub.ProcessPayment(payment_req)
        except Exception as e:
            logger.error("Payment service call failed: %s", e)
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Payment service unavailable.")
            return booking_pb2.BookResponse(
                success=False,
                message="Payment service unavailable.",
                booking_id="",
                seat=None
            )

        if not payment_resp.success or payment_resp.status != "COMPLETED":
            context.set_code(grpc.StatusCode.ABORTED)
            context.set_details("Payment failed.")
            return booking_pb2.BookResponse(
                success=False,
                message=f"Payment failed: {payment_resp.message}",
                booking_id="",
                seat=None
            )
            
        transaction_id = payment_resp.transaction_id
        
        #  Proceed with booking (only if payment succeeded)
        try:
            seat = await self.seat_manager.book_seat(show_id, seat_id, authenticated_user_id, transaction_id) 
        except PermissionError:
             context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
             context.set_details("Booking node is not the Raft leader.")
             return booking_pb2.BookResponse(
                success=False,
                message="Booking failed: Current node is not the Raft leader.",
                booking_id="",
                seat=None
            )
        except Exception as e:
             logger.error("Booking failed during proposal: %s", e)
             context.set_code(grpc.StatusCode.INTERNAL)
             context.set_details("Internal error during booking proposal.")
             return booking_pb2.BookResponse(
                success=False,
                message="Booking failed due to internal error. (Payment was successful but needs refund).",
                booking_id="",
                seat=None
            )
        
        if seat:
            return booking_pb2.BookResponse(
                success=True,
                message=f"Seat booked successfully (Txn ID: {transaction_id})",
                booking_id=seat.booking_id,
                seat=booking_pb2.Seat(
                    seat_id=seat.seat_id,
                    show_id=seat.show_id,
                    reserved=seat.reserved,
                    reserved_by=seat.reserved_by,
                    reserved_at=seat.reserved_at,
                    booking_id=seat.booking_id,
                    price_cents=seat.price_cents,
                )
            )
        else:

            return booking_pb2.BookResponse(
                success=False,
                message="Booking failed: Seat is already reserved or seat ID is invalid/out of range.",
                booking_id="",
                seat=None
            )
            
    # --- QUERY LOGIC ---
    async def QuerySeat(self, request, context):
        seat = await self.seat_manager.query_seat(request.show_id, request.seat_id)
        if seat:
            return booking_pb2.QueryResponse(
                available=not seat.reserved,
                seat=booking_pb2.Seat(
                    seat_id=seat.seat_id,
                    show_id=seat.show_id,
                    reserved=seat.reserved,
                    reserved_by=seat.reserved_by,
                    reserved_at=seat.reserved_at,
                    booking_id=seat.booking_id,
                    price_cents=seat.price_cents,
                )
            )
        else:
            return booking_pb2.QueryResponse(
                available=False,
                seat=None
            )

    # --- LIST LOGIC ---
    async def ListSeats(self, request, context):
        seats, next_token = await self.seat_manager.list_seats(
            request.show_id, request.page_size, request.page_token
        )
        return booking_pb2.ListSeatsResponse(
            seats=[
                booking_pb2.Seat(
                    seat_id=s.seat_id,
                    show_id=s.show_id,
                    reserved=s.reserved,
                    reserved_by=s.reserved_by,
                    reserved_at=s.reserved_at,
                    booking_id=s.booking_id,
                    price_cents=s.price_cents,
                ) for s in seats
            ],
            next_page_token=next_token
        )