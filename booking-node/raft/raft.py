import asyncio
import logging
from typing import List, Optional

from raft.log import Log, LogEntry
from raft.state_machine import StateMachine

logger = logging.getLogger("raft")


class RaftNode:
    """Simplified Raft node skeleton for demonstration and simulation purposes.

    This class simulates a Raft node with basic functionality:
      - Maintains Raft state variables
      - Applies committed log entries to a state machine
      - Allows local command proposals (no real replication yet)
      - Provides placeholders for leader election and heartbeats
    """

    def __init__(self, node_id: str, peers: list, config: dict = None):
        self.node_id = node_id
        self.peers = peers
        self.config = config or {}

        # -----------------------------------------------------------------
        # Persistent state
        # -----------------------------------------------------------------
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log = Log()

        # -----------------------------------------------------------------
        # Volatile state
        # -----------------------------------------------------------------
        self.commit_index = 0
        self.last_applied = 0

        # -----------------------------------------------------------------
        # Leader state (only used if elected)
        # -----------------------------------------------------------------
        self.next_index = {}
        self.match_index = {}

        # -----------------------------------------------------------------
        # State machine (application-level logic)
        # -----------------------------------------------------------------
        self.state_machine = StateMachine()

        # -----------------------------------------------------------------
        # Role management
        # -----------------------------------------------------------------
        self.role = "follower"
        self.leader_id: Optional[str] = None

        # -----------------------------------------------------------------
        # Internal runtime control
        # -----------------------------------------------------------------
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ---------------------------------------------------------------------
    # Lifecycle Management
    # ---------------------------------------------------------------------
    async def start(self):
        """Start Raft background loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Raft node %s started with peers=%s",
                    self.node_id, self.peers)

    async def stop(self):
        """Stop Raft node gracefully."""
        self._running = False
        if self._task:
            await self._task

    # ---------------------------------------------------------------------
    # Internal Loop
    # ---------------------------------------------------------------------
    async def _run_loop(self):
        while self._running:
            # Apply any new committed entries
            await self._apply_committed()

            # TODO: Add leader election, heartbeats, replication logic here
            await asyncio.sleep(0.1)

    async def _apply_committed(self):
        """Apply committed log entries to the state machine."""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log.get(self.last_applied)
            if entry:
                logger.debug("Applying log entry %s", entry)
                self.state_machine.apply(entry.command)

    # ---------------------------------------------------------------------
    # API: Command Proposal
    # ---------------------------------------------------------------------
    async def propose(self, command: bytes) -> int:
        entry = LogEntry(
            index=self.log.last_index + 1,
            term=self.current_term,
            command=command,
        )
        self.log.append(entry)

        self.commit_index = entry.index
        logger.info("Proposed command appended at index %d", entry.index)
        return entry.index

    # ---------------------------------------------------------------------
    # API: Append Entries RPC (Stub)
    # ---------------------------------------------------------------------
    async def append_entries(self, entries: List["LogEntry"],
                             leader_term: int):
        """Append log entries sent by the leader (simplified stub)."""
        for e in entries:
            self.log.append(e)
        return True

    # ---------------------------------------------------------------------
    # Query API
    # ---------------------------------------------------------------------
    def get_seat_state(self, show_id: str, seat_id: int):
        """Query seat state from the replicated state machine."""
        return self.state_machine.query(seat_id)
