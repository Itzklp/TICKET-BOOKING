import grpc
import logging
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from proto import raft_pb2, raft_pb2_grpc
from raft.raft import RaftNode 

logger = logging.getLogger("raft_service")

class RaftServicer(raft_pb2_grpc.RaftServicer):
    """
    gRPC implementation for the Raft protocol.
    Delegates RPC calls (AppendEntries and RequestVote) to the core RaftNode logic.
    """
    def __init__(self, raft_node: RaftNode):
        self.raft_node = raft_node

    async def AppendEntries(self, request, context):
        """Leader -> follower: replicate log entries / heartbeat."""
        return await self.raft_node.handle_append_entries(request)

    async def RequestVote(self, request, context):
        """Candidate -> peer: request votes during election."""
        return await self.raft_node.handle_request_vote(request)