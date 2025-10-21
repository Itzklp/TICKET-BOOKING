"""
State machine that applies Raft log commands to update seat state.

For simplicity, commands are encoded as JSON bytes in the following form:
{
    "type": "reserve" | "release",
    "seat_id": 12,
    "user_id": "u1"
}

In a production system, you'd use strongly typed proto messages
for commands instead of raw JSON.
"""

import json
import logging
from typing import Dict, Optional

logger = logging.getLogger("state_machine")


class StateMachine:
    """A simple in-memory state machine for managing seat reservations."""

    def __init__(self):
        # seat_id -> record (example: { "reserved": True, "user_id": "u1" })
        self.seats: Dict[int, Dict] = {}

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
        seat_id = int(obj.get("seat_id", -1))
        user_id = obj.get("user_id")

        if cmd_type == "reserve":
            self._reserve_seat(seat_id, user_id)
        elif cmd_type == "release":
            self._release_seat(seat_id)
        else:
            logger.warning("Unknown command type: %s", cmd_type)

    # ------------------------------------------------------------------
    # Command Handlers
    # ------------------------------------------------------------------
    def _reserve_seat(self, seat_id: int, user_id: Optional[str]) -> None:
        """Reserve a seat if not already reserved."""
        record = self.seats.get(seat_id, {"reserved": False, "user_id": None})
        if record.get("reserved"):
            logger.info("Seat %s already reserved", seat_id)
            return

        record.update({"reserved": True, "user_id": user_id})
        self.seats[seat_id] = record
        logger.info("Seat %s reserved by %s", seat_id, user_id)

    def _release_seat(self, seat_id: int) -> None:
        """Release a reserved seat."""
        record = self.seats.get(seat_id)
        if not record:
            logger.info("Seat %s not found; cannot release", seat_id)
            return

        record.update({"reserved": False, "user_id": None})
        self.seats[seat_id] = record
        logger.info("Seat %s released", seat_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def query(self, seat_id: int) -> Dict:
        """Query the current reservation state of a seat."""
        return self.seats.get(seat_id, {"reserved": False, "user_id": None})
