import time
import json 
import asyncio 
import logging
from typing import Dict, Optional, List, Tuple


from raft.raft import RaftNode 

logger = logging.getLogger("seat_manager") 


ADMIN_ID = "00000000-0000-0000-0000-000000000000" 

class Seat:

    def __init__(self, seat_id: int, show_id: str, reserved: bool = False, reserved_by: str = "", reserved_at: int = 0, booking_id: str = "0", price_cents: int = 0): # <-- Added price_cents
        self.seat_id = seat_id
        self.show_id = show_id
        self.reserved = reserved
        self.reserved_by = reserved_by
        self.reserved_at = reserved_at
        self.booking_id = booking_id
        self.price_cents = price_cents


class SeatManager:
    def __init__(self, raft_node: RaftNode = None):
        self.raft_node = raft_node
        # The true source of state is now Raft's state machine. 
        self.shows = {}
        if self.raft_node:

             self.shows = self.raft_node.state_machine.get_all_shows_seats() 
        
        self.next_booking_id = 1 
        
        if not self.shows:
             logger.warning("No shows found in state machine. Admin user must add a show.")
             
    # --- NEW ADMIN METHOD ---
    async def add_show(self, show_id: str, total_seats: int, price_cents: int) -> bool:
        """Proposes a command to add/update a show in the Raft State Machine."""
        if not show_id or not total_seats or price_cents is None:
             logger.error("Missing parameters for adding show.")
             return False

        if self.raft_node and self.raft_node.is_leader():
            command = json.dumps({
                "type": "add_show",
                "show_id": show_id,
                "total_seats": total_seats,
                "price_cents": price_cents
            }).encode()
            
            try:
                await self.raft_node.propose(command)
                self.shows = self.raft_node.state_machine.get_all_shows_seats() # Update local cache
                return True
            except (PermissionError, TimeoutError, Exception) as e:
                logger.warning("Raft proposal for add_show failed: %s", e)
                return False
        elif self.raft_node and not self.raft_node.is_leader():
            raise PermissionError("Not the current Raft leader.")
        
        return False


    async def book_seat(self, show_id: str, seat_id: int, user_id: str, transaction_id: str) -> Optional[Seat]:
        
        if self.raft_node and self.raft_node.is_leader():
            # Check current state from the Raft State Machine
            seat_record = self.raft_node.get_seat_state(show_id, seat_id)
            
            if not seat_record.get("exists"):
                 logger.warning("Attempted booking for non-existent seat %s in show %s.", seat_id, show_id)
                 return None
            
            if seat_record.get("reserved"):
                return None 

            #  Create command 
            command = json.dumps({
                "type": "reserve",
                "show_id": show_id, 
                "seat_id": seat_id,
                "user_id": user_id,
                "booking_id": transaction_id 
            }).encode()
            
            try:
                #  Propose through Raft and wait for commit
                await self.raft_node.propose(command)
                
                #  Check if reservation succeeded in the state machine
                final_state = self.raft_node.get_seat_state(show_id, seat_id)
                
                if final_state.get("reserved") and final_state.get("user_id") == user_id:

                    return await self.query_seat(show_id, seat_id) 
                else:
                    return None
                    
            except (PermissionError, TimeoutError, Exception) as e:
                logger.warning("Raft proposal failed: %s", e)
                return None
        elif self.raft_node and not self.raft_node.is_leader():

            raise PermissionError("Not the current Raft leader.")
        
        return None

    async def query_seat(self, show_id: str, seat_id: int) -> Optional[Seat]:
        """Query seat state, prioritizing Raft state machine if available."""
        if self.raft_node:
            state_record = self.raft_node.get_seat_state(show_id, seat_id)
            
            if not state_record.get("exists"):
                 return None 
                 
            seat = Seat(
                seat_id=seat_id,
                show_id=show_id,
                reserved=state_record.get("reserved", False),
                reserved_by=state_record.get("user_id", ""),
                reserved_at=state_record.get("reserved_at", 0),
                booking_id=state_record.get("booking_id", "0"),
                price_cents=state_record.get("price_cents", 0)
            )
            return seat
            
        return None

    async def list_seats(self, show_id: str, page_size=50, page_token=0) -> Tuple[List[Seat], int]:
        """List seats for a specific show, fetching state from the Raft State Machine."""
        if not self.raft_node:
            return [], 0
            
        show_data = self.raft_node.state_machine.get_show_data(show_id)
        if not show_data:
            return [], 0

        total_seats = show_data["total_seats"]

        all_seat_ids = list(range(1, total_seats + 1))
        
        start = page_token
        end = min(start + page_size, len(all_seat_ids))
        next_token = end if end < len(all_seat_ids) else 0

        seats_to_query = all_seat_ids[start:end]
        

        query_tasks = [self.query_seat(show_id, seat_id) for seat_id in seats_to_query]
        seats_list = await asyncio.gather(*query_tasks)
        
        seats_list = [s for s in seats_list if s is not None]

        return seats_list, next_token
        
    def get_show_price(self, show_id: str) -> Optional[int]: 
        """Gets the price of a show from the Raft State Machine."""
        if self.raft_node:
            show_data = self.raft_node.state_machine.get_show_data(show_id)
            return show_data.get("price_cents") if show_data else None
        return None
    

    
    def get_all_shows_info(self) -> Dict:
        """Get information about all shows from the Raft State Machine."""
        if self.raft_node:
            return self.raft_node.state_machine.get_all_shows_seats()
        return {}