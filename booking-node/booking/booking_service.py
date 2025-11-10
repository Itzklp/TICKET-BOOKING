"""
gRPC Booking service implementation that wires SeatManager to RPC calls.
This file assumes you have generated gRPC protobuf code as booking_pb2
"""

import logging
import sys
import os
import json
import grpc

# Ensure the project root (e.g., "D:/Ticket Booking") is in Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# import booking_pb2
# import booking_pb2_grpc

from booking.seat_manager import SeatManager

from proto import booking_pb2, booking_pb2_grpc
from proto import auth_pb2, auth_pb2_grpc

logger = logging.getLogger("booking_service")


class BookingServiceServicer(booking_pb2_grpc.BookingServiceServicer):
    def __init__(self, raft_node=None):
        self.seat_manager = SeatManager(raft_node)
        
        # Load config to get Auth Service address
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                   "booking-node", "config.json")
        
        # This is a robust way to find the config file path from deep inside the project structure.
        # However, a simpler way, given your existing path logic, would be to resolve a path
        # from the project root if it were readily available. Since the original path structure 
        # is relative to main.py, let's use a simpler import/lookup assuming config.json is accessible.

        # Simplified config loading (assuming config is structured like the default one)
        # NOTE: This assumes you handle the path correctly. We'll use the default config path relative to the project root.
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "booking-node", "config.json")
        
        with open(config_path, "r") as f:
            cfg = json.load(f)

        auth_cfg = cfg["services"]["auth_service"]
        auth_addr = f'{auth_cfg["host"]}:{auth_cfg["port"]}'
        
        self.auth_channel = grpc.insecure_channel(auth_addr)
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(self.auth_channel)
        logger.info("Connected Auth Service stub for validation at %s", auth_addr)

    async def BookSeat(self, request, context):
        # 1. Use request.user_id field to pass the session_token
        session_token = request.user_id 
        seat_id = request.seat_id
        
        # 2. Validate Session Token via Auth Service
        try:
            validation_req = auth_pb2.ValidateSessionRequest(
                token=session_token
            )
            # Synchronous call to Auth Service is acceptable in this async context
            validation_resp = self.auth_stub.ValidateSession(validation_req) 
        except Exception as e:
            logger.error("Auth service call failed: %s", e)
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Authentication service unavailable.")
            return booking_pb2.BookResponse(
                success=False,
                message="Authentication service unavailable.",
                booking_id=0,
                seat=None
            )

        if not validation_resp.valid:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid or expired session token.")
            return booking_pb2.BookResponse(
                success=False,
                message="Authentication failed. Please log in.",
                booking_id=0,
                seat=None
            )

        # Use the authenticated user_id for the booking
        authenticated_user_id = validation_resp.user_id
        
        # 3. Proceed with booking using the authenticated user_id
        # Note: self.seat_manager.book_seat takes the user_id as the second
        seat = self.seat_manager.book_seat(seat_id, authenticated_user_id) 
        
        
        if seat:
            return booking_pb2.BookResponse(
                success=True,
                message="Seat booked successfully",
                booking_id=seat.booking_id,
                seat=booking_pb2.Seat(
                    # ... (fill Seat details) ...
                    reserved_by=authenticated_user_id,
                    # ...
                )
            )
        else:
            return booking_pb2.BookResponse(
                success=False,
                message="Seat already booked or invalid",
                booking_id=0,
                seat=None
            )
            
    async def QuerySeat(self, request, context):
        seat = self.seat_manager.query_seat(request.seat_id)
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
                )
            )
        else:
            return booking_pb2.QueryResponse(
                available=False,
                seat=None
            )

    async def ListSeats(self, request, context):
        seats, next_token = self.seat_manager.list_seats(
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
                    booking_id=s.booking_id
                ) for s in seats
            ],
            next_page_token=next_token
        )