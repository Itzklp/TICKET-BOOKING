"""
Payment Service gRPC Server
Handles payment processing and transaction queries with local persistence.
"""

import logging
from concurrent import futures
import grpc
import time
import uuid
import json 
import os

import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import proto.payment_pb2 as payment_pb2
import proto.payment_pb2_grpc as payment_pb2_grpc

logger = logging.getLogger("payment")
logging.basicConfig(level=logging.INFO)

# --- PERSISTENCE CONFIG ---
PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), "payment_data.json")


def _load_data():
    """Load transaction data from local file."""
    if os.path.exists(PERSISTENCE_FILE):
        try:
            with open(PERSISTENCE_FILE, "r") as f:
                data = json.load(f)
                logger.info("Loaded %d transactions from %s", len(data), PERSISTENCE_FILE)
                return data
        except Exception as e:
            logger.error("Error loading payment data: %s", e)
    return {}

def _save_data(transactions):
    """Save transaction data to local file."""
    try:
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(transactions, f, indent=2)
        logger.debug("Saved payment data to %s", PERSISTENCE_FILE)
    except Exception as e:
        logger.error("Error saving payment data: %s", e)


class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    def __init__(self):
        # In-memory transaction store (loaded from file)
        self.transactions = _load_data() 

    def ProcessPayment(self, request, context):
        """Simulates payment processing with card number validation."""
        
        txn_id = str(uuid.uuid4())
        
        # Mock Validation: Fails if card number is '9999'
        if request.card_number == "9999":
            status = "FAILED"
            message = "Payment failed: Invalid card number (mock failure on 9999)."
            success = False
            logger.warning("Payment FAILED for user %s (Card: %s)", request.user_id, request.card_number)
        else:
            status = "COMPLETED"
            message = "Payment processed successfully."
            success = True
            logger.info("Payment success for user %s, amount=%d %s (Card: %s)",
                        request.user_id, request.amount_cents, request.currency, request.card_number)

        # Store transaction details in memory and persist
        transaction_record = {
            "user_id": request.user_id,
            "amount_cents": request.amount_cents,
            "currency": request.currency,
            "status": status,
            "created_at": int(time.time()),
            "card_number_masked": f"XXXX-XXXX-XXXX-{request.card_number[-4:]}" # Mask for safety
        }
        self.transactions[txn_id] = transaction_record
        _save_data(self.transactions) # <-- Persist data

        return payment_pb2.PaymentResponse(
            success=success,
            transaction_id=txn_id,
            status=status,
            message=message
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