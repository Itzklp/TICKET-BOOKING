"""
Chatbot Service gRPC Server
Simple AI-like responder for booking questions.
"""

import logging
from concurrent import futures
import grpc
import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import proto.chatbot_pb2 as chatbot_pb2
import proto.chatbot_pb2_grpc as chatbot_pb2_grpc

logger = logging.getLogger("chatbot")
logging.basicConfig(level=logging.INFO)


class ChatbotService(chatbot_pb2_grpc.ChatbotServicer):
    def Ask(self, request, context):
        user_msg = request.text.lower()
        logger.info("Chatbot received message: %s", user_msg)

        if "seat" in user_msg:
            reply = "You can book your seats using the booking service!"
            intent = "seat_inquiry"
            suggestions = [
                chatbot_pb2.Suggestion(title="Book a seat", payload="book_seat"),
                chatbot_pb2.Suggestion(title="Check availability", payload="check_availability")
            ]
        elif "pay" in user_msg:
            reply = "Payments are handled automatically during booking."
            intent = "payment_info"
            suggestions = []
        else:
            reply = "I'm here to help you with bookings or payments!"
            intent = "greeting"
            suggestions = []

        return chatbot_pb2.AskResponse(
            reply_text=reply,
            intent=intent,
            suggestions=suggestions
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    chatbot_pb2_grpc.add_ChatbotServicer_to_server(ChatbotService(), server)
    server.add_insecure_port("[::]:7000")
    logger.info("Chatbot service running on port 7000...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()