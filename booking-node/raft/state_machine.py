"""
State machine that applies Raft log commands to update seat state.
...
"""

import json
import logging
from typing import Dict, Optional
import os 
import time 

logger = logging.getLogger("state_machine")

# --- PERSISTENCE CONFIG ---
# Data will be saved in booking-node/data/state_machine_data.json
PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state_machine_data.json")

class StateMachine:
    """A simple in-memory state machine for managing seat reservations."""

    def __init__(self):
        # show_id -> { "total_seats": 100, "price_cents": 1500, "seats": { seat_id -> reservation record } }
        self.shows: Dict[str, Dict] = {}
        self._load_state()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_state(self):
        """Load state from local persistence file."""
        if os.path.exists(PERSISTENCE_FILE):
            try:
                with open(PERSISTENCE_FILE, "r") as f:
                    content = f.read()
                    if content:
                        self.shows = json.loads(content)
                logger.info("Loaded state machine data from %s", PERSISTENCE_FILE)
            except Exception as e:
                logger.error("Error loading state machine data: %s", e)
        # Initialize default show structure if not loaded
        if not self.shows:
             logger.warning("State machine initialized with empty state. Admin user must add a show.")

    def _save_state(self):
        """Save state to local persistence file."""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(PERSISTENCE_FILE), exist_ok=True)
            with open(PERSISTENCE_FILE, "w") as f:
                json.dump(self.shows, f, indent=2)
        except Exception as e:
            logger.error("Error saving state machine data: %s", e)


    # ------------------------------------------------------------------
    # Command Application
    # ------------------------------------------------------------------
    def apply(self, command_bytes: bytes) -> None:
        """Apply a Raft log command to update seat state."""
        try:
            obj = json.loads(command_bytes.decode())
        except Exception as e:
            logger.exception("Invalid command: %s", e)
            return

        cmd_type = obj.get("type")
        show_id = obj.get("show_id")
        seat_id = int(obj.get("seat_id", -1))
        
        if cmd_type == "reserve":
            user_id = obj.get("user_id")
            booking_id = obj.get("booking_id") 
            self._reserve_seat(show_id, seat_id, user_id, booking_id)
        
        elif cmd_type == "add_show":
            total_seats = obj.get("total_seats")
            price_cents = obj.get("price_cents")
            self._add_show(show_id, total_seats, price_cents)
        
        elif cmd_type == "release":
            self._release_seat(show_id, seat_id)
        else:
            logger.warning("Unknown command type: %s", cmd_type)
            
        self._save_state()


    # ------------------------------------------------------------------
    # Command Handlers
    # ------------------------------------------------------------------
    
    def _add_show(self, show_id: str, total_seats: int, price_cents: int) -> None:
        """Add or update a show and its total seats/price."""
        if not show_id or not total_seats or price_cents is None:
             logger.error("Cannot add show: missing show_id, total_seats, or price_cents")
             return

        if show_id not in self.shows:
            self.shows[show_id] = {
                "total_seats": total_seats,
                "price_cents": price_cents,
                "seats": {} # seat_id -> reservation record
            }
            logger.info("New show '%s' added with %d seats and price %d cents.", show_id, total_seats, price_cents)
        else:
            self.shows[show_id]["total_seats"] = total_seats
            self.shows[show_id]["price_cents"] = price_cents
            logger.info("Show '%s' updated: %d seats, price %d cents.", show_id, total_seats, price_cents)
        
    
    def _get_seat_record(self, show_id: str, seat_id: int) -> Dict:
        """Helper to safely get a seat record."""
        show = self.shows.get(show_id)
        if not show:
            return {"reserved": True, "user_id": None, "exists": False} 
            
        # Check if seat is within total_seats range (still used for Querying logic)
        if seat_id <= 0 or seat_id > show["total_seats"]:
             return {"reserved": True, "user_id": None, "exists": False} # Out of range for this show

        record = show["seats"].get(seat_id)

        if record:
            return {**record, "exists": True}

        # Exists but not yet reserved
        return {"reserved": False, "user_id": None, "exists": True}

    def _reserve_seat(self, show_id: str, seat_id: int, user_id: Optional[str], booking_id: str) -> None:
        """Reserve a seat if not already reserved (Raft Commit Logic)."""
        
        show = self.shows.get(show_id)
        if not show:
            logger.warning("Attempted reservation for non-existent show %s.", show_id)
            return

        # --- FIX: Strict Range Check to prevent invalid state mutation ---
        if seat_id <= 0 or seat_id > show["total_seats"]:
             logger.warning("Raft applied command rejected: Out-of-range seat %s in show %s.", seat_id, show_id)
             return # Fails silently, preventing state mutation
        # -----------------------------------------------------------

        record = show["seats"].get(seat_id)
        
        # If already reserved (committed booking from Raft)
        if record and record.get("reserved"):
            logger.info("Seat %s in show %s already reserved (Raft applied)", seat_id, show_id)
            return

        # If passed checks, update the state
        
        new_record = {
            "reserved": True, 
            "user_id": user_id,
            "booking_id": booking_id, 
            "reserved_at": int(time.time() * 1000) 
        }

        # Save the new record directly to the seats dictionary
        show["seats"][seat_id] = new_record
        
        logger.info("Seat %s in show %s reserved by %s (Txn ID: %s)", seat_id, show_id, user_id, booking_id)

    def _release_seat(self, show_id: str, seat_id: int) -> None:
        """Release a reserved seat."""
        show = self.shows.get(show_id)
        if not show:
            logger.warning("Show %s not found; cannot release seat %s", show_id, seat_id)
            return

        record = show["seats"].get(seat_id)
        if not record:
            logger.info("Seat %s not found in state; cannot release", seat_id)
            return

        # Update the state
        record.update({"reserved": False, "user_id": None, "booking_id": "", "reserved_at": 0})
        logger.info("Seat %s in show %s released", seat_id, show_id)


    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def query(self, show_id: str, seat_id: int) -> Dict:
        """Query the current reservation state of a seat, including show metadata."""
        show = self.shows.get(show_id)
        if not show:
            return {"reserved": True, "user_id": None, "exists": False}
            
        seat_record = self._get_seat_record(show_id, seat_id)
        
        return {
            "show_id": show_id,
            "price_cents": show.get("price_cents", 0),
            **seat_record
        }
        
    def get_show_data(self, show_id: str) -> Optional[Dict]:
        """Get show metadata (total_seats, price_cents)."""
        return self.shows.get(show_id)

    def get_all_shows_seats(self) -> Dict:
        """Get the full shows dictionary for listing/initialization."""
        return self.shows