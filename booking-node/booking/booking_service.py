"""
gRPC Booking service implementation that wires SeatManager to RPC calls.
This file assumes you have generated gRPC protobuf code as booking_pb2
"""

import logging
import sys
import os

# Ensure the project root (e.g., "D:/Ticket Booking") is in Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# import booking_pb2
# import booking_pb2_grpc

from booking.seat_manager import SeatManager

from proto import booking_pb2, booking_pb2_grpc

logger = logging.getLogger("booking_service")


class BookingServiceServicer(booking_pb2_grpc.BookingServiceServicer):
    def __init__(self, raft_node=None):
        self.seat_manager = SeatManager(raft_node)

    async def BookSeat(self, request, context):
        seat = self.seat_manager.book_seat(request.seat_id, request.user_id)
        if seat:
            return booking_pb2.BookResponse(
                success=True,
                message="Seat booked successfully",
                booking_id=seat.booking_id,
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