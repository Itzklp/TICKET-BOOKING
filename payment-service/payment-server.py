"""
Payment Service gRPC Server
Handles payment processing and transaction queries.
"""

import logging
from concurrent import futures
import grpc
import time
import uuid

import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import proto.payment_pb2 as payment_pb2
import proto.payment_pb2_grpc as payment_pb2_grpc

logger = logging.getLogger("payment")
logging.basicConfig(level=logging.INFO)


class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    def __init__(self):
        # In-memory transaction store
        self.transactions = {}

    def ProcessPayment(self, request, context):
        """Simulates payment processing."""
        logger.info("Processing payment for user %s, amount=%d %s",
                    request.user_id, request.amount_cents, request.currency)

        # Fake success with random transaction_id
        txn_id = str(uuid.uuid4())
        self.transactions[txn_id] = {
            "user_id": request.user_id,
            "amount_cents": request.amount_cents,
            "currency": request.currency,
            "status": "COMPLETED",
            "created_at": int(time.time())
        }

        return payment_pb2.PaymentResponse(
            success=True,
            transaction_id=txn_id,
            status="COMPLETED",
            message="Payment processed successfully."
        )

    def QueryTransaction(self, request, context):
        txn = self.transactions.get(request.transaction_id)
        if not txn:
            return payment_pb2.QueryTransactionResponse(
                transaction_id=request.transaction_id,
                status="NOT_FOUND"
            )

        return payment_pb2.QueryTransactionResponse(
            transaction_id=request.transaction_id,
            status=txn["status"],
            amount_cents=txn["amount_cents"],
            currency=txn["currency"],
            created_at=txn["created_at"]
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    payment_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentService(), server)
    server.add_insecure_port("[::]:6000")
    logger.info("Payment service running on port 6000...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
