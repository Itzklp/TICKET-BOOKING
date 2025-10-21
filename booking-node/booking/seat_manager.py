import time


class Seat:
    def __init__(self, seat_id: int, show_id: str):
        self.seat_id = seat_id
        self.show_id = show_id
        self.reserved = False
        self.reserved_by = ""
        self.reserved_at = 0
        self.booking_id = 0


class SeatManager:
    def __init__(self, raft_node=None):
        # For simplicity, prepopulate 100 seats for show_id="default_show"
        self.seats = {i: Seat(i, "default_show") for i in range(1, 101)}
        self.raft_node = raft_node
        self.next_booking_id = 1

    def book_seat(self, seat_id: int, user_id: str) -> Seat | None:
        seat = self.seats.get(seat_id)
        if seat and not seat.reserved:
            seat.reserved = True
            seat.reserved_by = user_id
            seat.reserved_at = int(time.time() * 1000)
            seat.booking_id = self.next_booking_id
            self.next_booking_id += 1
            return seat
        return None

    def query_seat(self, seat_id: int) -> Seat | None:
        return self.seats.get(seat_id)

    def list_seats(self, show_id: str, page_size=50, page_token=0):
        seats_list = [s for s in self.seats.values() if s.show_id == show_id]
        start = page_token
        end = min(start + page_size, len(seats_list))
        next_token = end if end < len(seats_list) else 0
        return seats_list[start:end], next_token
