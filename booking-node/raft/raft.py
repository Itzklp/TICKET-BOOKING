import asyncio
import logging
import random
import time
from typing import List, Optional, Dict
import grpc

from raft.log import Log, LogEntry
from raft.state_machine import StateMachine
from proto import raft_pb2, raft_pb2_grpc

logger = logging.getLogger("raft")

# Raft Timing Constants
HEARTBEAT_INTERVAL = 0.05  # 50 ms (Time in seconds)
ELECTION_TIMEOUT_MIN = 0.150  # 150 ms
ELECTION_TIMEOUT_MAX = 0.300  # 300 ms

class RaftNode:
    """Core Raft Node Implementation."""

    def __init__(self, node_id: str, peers: List[Dict], config: dict = None):
        self.node_id = node_id
        self.config = config or {}
        self.peers = peers
        self.majority = int((len(self.peers) + 1) / 2) + 1

        # gRPC Stubs for peer communication
        self.peer_stubs: Dict[str, raft_pb2_grpc.RaftStub] = {}
        self._setup_peer_stubs()

        # -----------------------------------------------------------------
        # Persistent state (on all servers)
        # -----------------------------------------------------------------
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log = Log()

        # -----------------------------------------------------------------
        # Volatile state (on all servers)
        # -----------------------------------------------------------------
        self.commit_index = 0
        self.last_applied = 0
        self.role = "follower"
        self.leader_id: Optional[str] = None

        # -----------------------------------------------------------------
        # Volatile state (leader only)
        # -----------------------------------------------------------------
        self.next_index: Dict[str, int] = {} 
        self.match_index: Dict[str, int] = {} 
        
        # -----------------------------------------------------------------
        # Application state
        # -----------------------------------------------------------------
        self.state_machine = StateMachine()

        # -----------------------------------------------------------------
        # Timers and Control
        # -----------------------------------------------------------------
        self._running = False
        self._run_task: Optional[asyncio.Task] = None
        self._election_timeout: float = self._get_new_election_timeout()
        self._last_heartbeat_sent: float = time.time()
        self._last_heartbeat_received: float = time.time()
        # {log_index: Future} - Futures are resolved upon *apply*
        self.proposals: Dict[int, asyncio.Future] = {} 

    def _setup_peer_stubs(self):
        """Initializes gRPC channels and stubs for all peers."""
        for peer in self.peers:
            addr = f'{peer["host"]}:{peer["port"]}'
            # Note: Using grpc.aio.insecure_channel for async gRPC
            channel = grpc.aio.insecure_channel(addr)
            self.peer_stubs[peer["node_id"]] = raft_pb2_grpc.RaftStub(channel)

    def _get_new_election_timeout(self) -> float:
        """Returns a randomized election timeout with jitter."""
        return random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)

    # --- Lifecycle Management (start/stop remain largely the same) ---
    async def start(self):
        self._running = True
        self._run_task = asyncio.create_task(self._run_loop())
        logger.info("Raft node %s started with peers: %s. Majority: %d",
                    self.node_id, [p['node_id'] for p in self.peers], self.majority)

    async def stop(self):
        self._running = False
        if self._run_task:
            await self._run_task
            
    # --- Main Raft Loop ---
    async def _run_loop(self):
        while self._running:
            await self._apply_committed()

            current_time = time.time()

            if self.role == "leader":
                # Leader sends heartbeats/log replication
                if current_time - self._last_heartbeat_sent >= HEARTBEAT_INTERVAL:
                    self._last_heartbeat_sent = current_time
                    await self._send_append_entries(is_heartbeat=True)

            elif self.role in ["follower", "candidate"]:
                # Follower/Candidate checks election timeout
                if current_time - self._last_heartbeat_received >= self._election_timeout:
                    await self._start_election()

            await asyncio.sleep(0.01) # Short sleep to yield control

    # --- State Transitions and Election ---

    async def _start_election(self):
        """Transition to Candidate and send RequestVote RPCs."""
        self.role = "candidate"
        self.current_term += 1
        self.voted_for = self.node_id
        self.leader_id = None
        
        self._last_heartbeat_received = time.time() # Reset election timer
        self._election_timeout = self._get_new_election_timeout() # New randomized timeout
        
        last_log_index = self.log.last_index
        last_log_term = self.log.get(last_log_index).term if last_log_index > 0 and self.log.get(last_log_index) else 0
        
        logger.info("Starting election for term %d. Last log: index=%d, term=%d", 
                    self.current_term, last_log_index, last_log_term)

        request = raft_pb2.RequestVoteRequest(
            term=self.current_term,
            candidate_id=self.node_id,
            last_log_index=last_log_index,
            last_log_term=last_log_term
        )
        
        votes_received = 1 # Candidate votes for self
        
        responses = await asyncio.gather(
            *[self._send_request_vote(peer_id, request) 
              for peer_id in self.peer_stubs.keys()],
            return_exceptions=True
        )

        for response in responses:
            if isinstance(response, raft_pb2.RequestVoteResponse):
                if response.term > self.current_term:
                    self._transition_to_follower(response.term, "Discovered higher term in RequestVote response")
                    return
                if response.vote_granted:
                    votes_received += 1
            # Error handling in _send_request_vote

        if self.role == "candidate" and votes_received >= self.majority:
            await self._transition_to_leader()
            return # Election won, exit
            
        # FIX: If election is lost, explicitly step down to Follower.
        # This ensures a clean state and reliance on the next election timeout.
        if self.role == "candidate" and votes_received < self.majority:
             self.role = "follower"
             self.leader_id = None
             # The timer was already reset at the start of _start_election.
             logger.info("Election lost in term %d (votes: %d). Stepping down to follower and waiting for next timeout.",
                         self.current_term, votes_received)
             # The function returns, and the _run_loop continues.


    async def _transition_to_leader(self):
        """Transition to Leader state and initialize volatile state."""
        self.role = "leader"
        self.leader_id = self.node_id
        
        last_index = self.log.last_index
        for peer_id in self.peer_stubs.keys():
            self.next_index[peer_id] = last_index + 1
            self.match_index[peer_id] = 0
            
        logger.info("Node %s is the LEADER for term %d!", self.node_id, self.current_term)
        await self._send_append_entries(is_heartbeat=True)

    def _transition_to_follower(self, new_term: int, reason: str):
        """Transition to Follower state."""
        if new_term > self.current_term:
            self.current_term = new_term
            self.voted_for = None
            
        self.role = "follower"
        self._last_heartbeat_received = time.time() 
        self._election_timeout = self._get_new_election_timeout()
        logger.info("Transitioned to FOLLOWER for term %d. Reason: %s", self.current_term, reason)


    # --- RPC Helpers (Network Communication) ---
    async def _send_request_vote(self, peer_id: str, request: raft_pb2.RequestVoteRequest) -> Optional[raft_pb2.RequestVoteResponse]:
        """Send a RequestVote RPC to a single peer."""
        # Fix: Use a dedicated, slightly longer RPC timeout to prevent premature network failure
        REQUEST_VOTE_RPC_TIMEOUT = ELECTION_TIMEOUT_MIN / 2 
        try:
            stub = self.peer_stubs[peer_id]
            # Use REQUEST_VOTE_RPC_TIMEOUT for the RPC call
            response = await stub.RequestVote(request, timeout=REQUEST_VOTE_RPC_TIMEOUT) 
            return response
        except grpc.aio.AioRpcError:
            # RPC failed (e.g., peer unavailable, timeout)
            return None

    async def _send_append_entries(self, is_heartbeat: bool = False, peer_id: Optional[str] = None) -> None:
        """Send AppendEntries RPCs to all or a specific follower."""
        
        peer_ids = [peer_id] if peer_id else self.peer_stubs.keys()
        
        for p_id in peer_ids:
            next_idx = self.next_index.get(p_id, 1)
            
            entries_to_send = []
            if not is_heartbeat:
                # Send log entries starting from next_idx
                for entry in self.log.entries_from(next_idx):
                    entries_to_send.append(
                        raft_pb2.LogEntry(
                            index=entry.index,
                            term=entry.term,
                            command=entry.command.decode() # Command is JSON string in proto
                        )
                    )
            
            prev_log_index = next_idx - 1
            prev_log_entry = self.log.get(prev_log_index)
            prev_log_term = prev_log_entry.term if prev_log_entry else 0

            request = raft_pb2.AppendEntriesRequest(
                term=self.current_term,
                leader_id=self.node_id,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries_to_send,
                leader_commit=self.commit_index
            )
            
            # Non-blocking call to peer to handle response asynchronously
            asyncio.create_task(self._call_append_entries(p_id, request))

    async def _call_append_entries(self, peer_id: str, request: raft_pb2.AppendEntriesRequest):
        """Actual gRPC call for AppendEntries and response handling."""
        try:
            stub = self.peer_stubs[peer_id]
            response = await stub.AppendEntries(request, timeout=HEARTBEAT_INTERVAL)
            
            if response.term > self.current_term:
                self._transition_to_follower(response.term, f"Discovered higher term {response.term} in AppendEntries response")
                return

            if self.role != "leader": return

            if response.success:
                # Successful replication, update matchIndex and nextIndex
                new_match_index = request.prev_log_index + len(request.entries)
                self.match_index[peer_id] = new_match_index
                self.next_index[peer_id] = new_match_index + 1
                
                if request.entries:
                    self._check_for_commit()
                
            else:
                # Log inconsistency, decrement nextIndex and retry
                self.next_index[peer_id] = max(1, self.next_index[peer_id] - 1)
                await self._send_append_entries(peer_id=peer_id)
                
        except grpc.aio.AioRpcError:
            pass # Retry happens in next heartbeat
        except Exception as e:
            logger.error("Error during AppendEntries response handling for %s: %s", peer_id, e)

    def _check_for_commit(self):
        """Check if any log entry can be committed."""
        if self.role != "leader": return

        max_log_index = self.log.last_index
        for N in range(self.commit_index + 1, max_log_index + 1):
            # Count replicas that have replicated log entry N (including leader)
            replicated_count = 1 
            for match_index in self.match_index.values():
                if match_index >= N:
                    replicated_count += 1
            
            if replicated_count >= self.majority:
                entry = self.log.get(N)
                if entry and entry.term == self.current_term:
                    self.commit_index = N
                    logger.info("Log index %d committed for term %d.", N, self.current_term)
                    
                    # --- BUGFIX 1: REMOVED ---
                    # The future is now resolved in _apply_committed
                    # to prevent the race condition.
                    #
                    # if N in self.proposals:
                    #     self.proposals[N].set_result(True)
                    #     del self.proposals[N]
                else:
                    break # Cannot commit log from previous term
            else:
                break # No majority for N
        

    # --- RPC Handlers for RaftServicer ---
    async def handle_request_vote(self, request: raft_pb2.RequestVoteRequest) -> raft_pb2.RequestVoteResponse:
        
        if request.term < self.current_term:
            return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)
        if request.term > self.current_term:
            self._transition_to_follower(request.term, "Received RequestVote with higher term")

        can_vote = (self.voted_for is None or self.voted_for == request.candidate_id)
        last_log_index = self.log.last_index
        last_log_term = self.log.get(last_log_index).term if last_log_index > 0 and self.log.get(last_log_index) else 0
        log_up_to_date = (
            request.last_log_term > last_log_term or
            (request.last_log_term == last_log_term and request.last_log_index >= last_log_index)
        )

        vote_granted = False
        if can_vote and log_up_to_date:
            self.voted_for = request.candidate_id
            self._last_heartbeat_received = time.time()
            vote_granted = True
            logger.info("Voted for %s in term %d", request.candidate_id, self.current_term)
        
        return raft_pb2.RequestVoteResponse(
            term=self.current_term,
            vote_granted=vote_granted,
            message="Vote granted" if vote_granted else "Log not up-to-date or already voted"
        )


    async def handle_append_entries(self, request: raft_pb2.AppendEntriesRequest) -> raft_pb2.AppendEntriesResponse:
        
        if request.term < self.current_term:
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
            
        if request.term > self.current_term:
            self._transition_to_follower(request.term, "Received AppendEntries with higher term")
            
        self._last_heartbeat_received = time.time()
        self.leader_id = request.leader_id
        self.role = "follower"

        if request.prev_log_index > 0:
            prev_entry = self.log.get(request.prev_log_index)
            if not prev_entry or prev_entry.term != request.prev_log_term:
                return raft_pb2.AppendEntriesResponse(
                    term=self.current_term, success=False, match_index=self.log.last_index
                )

        if not request.entries:
            if request.leader_commit > self.commit_index:
                self.commit_index = min(request.leader_commit, self.log.last_index)
            return raft_pb2.AppendEntriesResponse(
                term=self.current_term, success=True, match_index=self.log.last_index
            )

        last_appended_index = request.prev_log_index
        for entry_req in request.entries:
            existing_entry = self.log.get(entry_req.index)
            if existing_entry and existing_entry.term != entry_req.term:
                # Log conflict
                return raft_pb2.AppendEntriesResponse(
                    term=self.current_term, success=False, match_index=self.log.last_index
                )
            if not existing_entry:
                new_entry = LogEntry(
                    index=entry_req.index, term=entry_req.term, command=entry_req.command.encode()
                )
                self.log.append(new_entry)
                last_appended_index = new_entry.index
            else:
                last_appended_index = existing_entry.index
        
        if request.leader_commit > self.commit_index:
            self.commit_index = min(request.leader_commit, last_appended_index)
        
        return raft_pb2.AppendEntriesResponse(
            term=self.current_term, success=True, match_index=last_appended_index
        )
        

    # --- Internal Application & Commit ---
    async def _apply_committed(self):
        """Apply committed log entries to the state machine."""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log.get(self.last_applied)
            if entry:
                logger.debug("Applying log entry %s", entry)
                self.state_machine.apply(entry.command)

                # --- BUGFIX 2: MOVED HERE ---
                # Resolve the proposal Future *after* the command
                # has been applied to the state machine.
                if self.last_applied in self.proposals:
                    self.proposals[self.last_applied].set_result(True)
                    del self.proposals[self.last_applied]
            else:
                logger.error("Commit index %d references a missing log entry!", self.last_applied)


    # --- API: Command Proposal (Client-facing) ---
    async def propose(self, command: bytes) -> int:
        """Proposes a command and waits for it to be *applied*."""
        if self.role != "leader":
            raise PermissionError("Only the leader can propose commands.")
            
        entry = LogEntry(
            index=self.log.last_index + 1,
            term=self.current_term,
            command=command,
        )
        
        # 1. Leader appends to local log
        self.log.append(entry)
        
        # Setup Future to wait for *apply*
        future = asyncio.Future()
        self.proposals[entry.index] = future
        
        logger.info("Proposed command appended locally at index %d. Starting replication.", entry.index)
        
        # 2. Send AppendEntries to all followers
        await self._send_append_entries()
        
        # 3. Wait for apply confirmation (from _apply_committed)
        try:
            # Set a timeout for replication. If it fails, the leader may have stepped down.
            await asyncio.wait_for(future, timeout=2.0) 
            return entry.index
                
        except asyncio.TimeoutError:
            logger.warning("Proposal at index %d timed out waiting for apply.", entry.index)
            if entry.index in self.proposals:
                del self.proposals[entry.index]
            raise TimeoutError("Raft proposal timed out.")
        except Exception as e:
            if entry.index in self.proposals:
                del self.proposals[entry.index]
            raise e

    # --- Query API (Modified) ---
    def get_seat_state(self, show_id: str, seat_id: int):
        return self.state_machine.query(show_id, seat_id)

    def is_leader(self) -> bool:
        return self.role == "leader"