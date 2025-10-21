#!/usr/bin/env python3
"""
Entry point for a Booking Node.

This script starts:
  - A gRPC server exposing the BookingService
  - A minimal Raft node loop for distributed consensus

You can extend this with real Raft networking, persistence, and replication.
"""

import argparse
import asyncio
import logging
import json
import os
import sys
import grpc

# Ensure the project root (e.g., "D:/Ticket Booking") is in Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import generated protobuf stubs and core service classes
# Ensure the protobuf gRPC stubs are generated (e.g. with:
# and are available on the PYTHONPATH)
from proto import booking_pb2_grpc

from booking.booking_service import BookingServiceServicer
from raft.raft import RaftNode


# -------------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("booking-node")

# Default configuration path
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


# -------------------------------------------------------------------------
# Async gRPC Server with Raft Node
# -------------------------------------------------------------------------
async def serve(config_path: str):
    """Start the gRPC Booking node and Raft consensus instance."""
    # Load configuration file
    with open(config_path, "r") as f:
        cfg = json.load(f)

    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 50051)
    raft_cfg = cfg.get("raft", {})

    # Initialize Raft node (networking and persistence are minimal stubs)
    raft_node = RaftNode(
        node_id=cfg.get("node_id", "node-1"),
        peers=cfg.get("peers", []),
        config=raft_cfg
    )
    await raft_node.start()

    # Initialize Booking gRPC service
    server = grpc.aio.server()
    booking_servicer = BookingServiceServicer(raft_node)

    # Register BookingService with gRPC server
    booking_pb2_grpc.add_BookingServiceServicer_to_server(
        booking_servicer, server)

    # Bind server to host:port
    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    logger.info("Starting gRPC server on %s", listen_addr)

    # Start server
    await server.start()
    logger.info("Booking node started successfully")

    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        logger.info("Shutting down server gracefully...")
        await server.stop(5)
        await raft_node.stop()


# -------------------------------------------------------------------------
# Main Entrypoint
# -------------------------------------------------------------------------
def main():
    """CLI entrypoint for booking node."""
    parser = argparse.ArgumentParser(description="Distributed Booking Node")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to booking-node/config.json",
    )
    args = parser.parse_args()

    asyncio.run(serve(args.config))


if __name__ == "__main__":
    main()
