import time
import json 
import asyncio 
import logging # <-- ADDED: Define logger

logger = logging.getLogger("seat_manager") # <-- ADDED: Define logger

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

    async def book_seat(self, seat_id: int, user_id: str) -> 'Seat | None':
        """
        Proposes a seat reservation command to the Raft consensus group.
        Waits for the command to be committed and applied to the state machine.
        """
        if self.raft_node and self.raft_node.is_leader():
            # 1. Check current state from the Raft State Machine
            seat_record = self.raft_node.get_seat_state("default_show", seat_id)
            if seat_record.get("reserved"):
                return None # Already reserved

            # 2. Create command
            command = json.dumps({
                "type": "reserve",
                "seat_id": seat_id,
                "user_id": user_id
            }).encode()
            
            try:
                # 3. Propose through Raft and wait for commit
                await self.raft_node.propose(command)
                
                # 4. Check if reservation succeeded in the state machine
                final_state = self.raft_node.get_seat_state("default_show", seat_id)
                
                if final_state.get("reserved") and final_state.get("user_id") == user_id:
                    # Successfully booked via Raft. 
                    return await self.query_seat(seat_id) # <-- AWAIT is correct here
                else:
                    return None
                    
            except (PermissionError, TimeoutError, Exception) as e:
                logger.warning("Raft proposal failed: %s", e)
                return None
        elif self.raft_node and not self.raft_node.is_leader():
            # Not leader, fail immediately (client should retry with leader)
            raise PermissionError("Not the current Raft leader.")
        
        # Fallback for non-Raft/single-node scenario (Directly modifies state)
        seat = self.seats.get(seat_id)
        if seat and not seat.reserved:
            seat.reserved = True
            seat.reserved_by = user_id
            seat.reserved_at = int(time.time() * 1000)
            seat.booking_id = self.next_booking_id
            self.next_booking_id += 1
            return await self.query_seat(seat_id) # <-- AWAIT is essential here
            
        return None

    async def query_seat(self, seat_id: int) -> 'Seat | None': # <-- Must be ASYNC DEF
        """Query seat state, prioritizing Raft state machine if available."""
        seat = self.seats.get(seat_id)
        if self.raft_node and seat:
            state_record = self.raft_node.get_seat_state("default_show", seat_id)
            
            # Update the local Seat object with the latest committed state
            seat.reserved = state_record.get("reserved", False)
            seat.reserved_by = state_record.get("user_id", "")
            # Note: booking_id/reserved_at are not fully managed by simple state machine
            return seat
            
        return seat

    async def list_seats(self, show_id: str, page_size=50, page_token=0): # <-- Must be ASYNC DEF
        # Asynchronously query the current state for all seats
        seats_for_show = [s for s in self.seats.values() if s.show_id == show_id]
        
        # Use asyncio.gather to concurrently query the state of all relevant seats
        query_tasks = [self.query_seat(s.seat_id) for s in seats_for_show]
        seats_list = await asyncio.gather(*query_tasks)
        
        # Filter out any None results
        seats_list = [s for s in seats_list if s is not None]

        start = page_token
        end = min(start + page_size, len(seats_list))
        next_token = end if end < len(seats_list) else 0
        return seats_list[start:end], next_token