"""
IMPROVED LLM-Powered Chatbot Service for Ticket Booking Domain
Uses template-based responses with LLM enhancement for better accuracy
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

logger = logging.getLogger("llm-chatbot")
logging.basicConfig(level=logging.INFO)


class TicketBookingAssistant:
    """
    Hybrid chatbot: Template-based responses with optional LLM enhancement.
    Prioritizes accuracy over creativity for FAQ responses.
    """
    
    def __init__(self):
        """Initialize the booking assistant with domain knowledge"""
        logger.info("Initializing Ticket Booking Assistant...")
        
        # Define comprehensive response templates
        self.response_templates = {
            "booking": {
                "keywords": ["book", "reserve", "buy", "purchase", "get ticket", "ticket booking"],
                "response": "To book a seat:\n1. Log in to your account (or register if new)\n2. Select 'Book a Seat' from the menu\n3. Enter the seat ID (1-100)\n4. Enter show ID (use 'default_show')\n5. Confirm your booking\n\nYour seat will be reserved immediately and you'll receive a booking confirmation!",
                "suggestions": [
                    {"title": "Register Account", "payload": "register"},
                    {"title": "Login", "payload": "login"},
                    {"title": "Book a Seat", "payload": "book_seat"}
                ]
            },
            "query_seat": {
                "keywords": ["check seat", "seat available", "query seat", "seat status", "is seat", "seat free"],
                "response": "To check if a seat is available:\n1. Select 'Query Seat' from the main menu\n2. Enter the seat number you want to check (1-100)\n3. Enter the show ID (use 'default_show')\n\nThe system will instantly tell you if the seat is available or already booked!",
                "suggestions": [
                    {"title": "Check Seat Now", "payload": "check_availability"},
                    {"title": "View All Seats", "payload": "list_seats"}
                ]
            },
            "cancellation": {
                "keywords": ["cancel", "refund", "return", "cancel booking", "get money back"],
                "response": "Cancellation Policy:\n• Full refund if cancelled within 24 hours of booking\n• 50% refund if cancelled 24-48 hours before the show\n• No refund if cancelled less than 24 hours before show\n\nTo cancel: Contact our support team with your booking ID.",
                "suggestions": [
                    {"title": "View My Bookings", "payload": "my_bookings"},
                    {"title": "Contact Support", "payload": "support"}
                ]
            },
            "payment": {
                "keywords": ["pay", "payment", "cost", "price", "how much", "pay for"],
                "response": "Payment Process:\n1. After selecting your seat, you'll see the total amount\n2. Select 'Process Payment' from the menu\n3. Enter your user ID and payment amount (in cents)\n4. Choose your currency (e.g., USD, INR)\n5. Confirm payment\n\nAll transactions are secure and encrypted. You'll receive a transaction ID for your records.",
                "suggestions": [
                    {"title": "Payment Methods", "payload": "payment_methods"},
                    {"title": "Payment Security", "payload": "security_info"}
                ]
            },
            "account": {
                "keywords": ["account", "login", "register", "sign up", "sign in", "password", "create account"],
                "response": "Account Management:\n\nTo Register:\n1. Select 'Register User' from menu\n2. Enter a valid email address\n3. Create a secure password\n4. You'll receive confirmation\n\nTo Login:\n1. Select 'Login User' from menu\n2. Enter your email and password\n3. You'll receive a session token\n\nYou must be logged in to book seats!",
                "suggestions": [
                    {"title": "Register Now", "payload": "register"},
                    {"title": "Login", "payload": "login"}
                ]
            },
            "seats_available": {
                "keywords": ["what seats", "which seats", "seats available", "available seats", "how many seats"],
                "response": "We have 100 seats available for the 'default_show' concert:\n• Seats numbered 1-100\n• Use 'Query Seat' to check specific seat availability\n• Seats are reserved in real-time across all booking nodes\n• First-come, first-served basis\n\nTo see all available seats, use the 'List Seats' option from the menu!",
                "suggestions": [
                    {"title": "Check Seat Status", "payload": "query_seat"},
                    {"title": "Book Now", "payload": "book_seat"}
                ]
            },
            "help_general": {
                "keywords": ["help", "how to", "how do i", "what is", "explain", "tell me"],
                "response": "I can help you with:\n\n📋 Booking: How to reserve seats\n🔍 Seat Queries: Check seat availability  \n💳 Payments: Processing transactions\n👤 Accounts: Registration and login\n❌ Cancellations: Refund policies\n📊 Seat Info: Available seats and show details\n\nWhat would you like to know more about?",
                "suggestions": [
                    {"title": "How to Book", "payload": "booking_help"},
                    {"title": "Check Seats", "payload": "seat_help"},
                    {"title": "Payment Info", "payload": "payment_help"}
                ]
            },
            "show_info": {
                "keywords": ["show", "concert", "event", "default_show", "what show"],
                "response": "Current Show: 'default_show' Concert\n• Total Seats: 100 (numbered 1-100)\n• Distributed Booking: Multi-node system with Raft consensus\n• Real-time Availability: Instant seat status updates\n• Secure Payment: Encrypted transactions\n\nBook your seats now before they're gone!",
                "suggestions": [
                    {"title": "Book Seats", "payload": "book_seat"},
                    {"title": "View Seats", "payload": "list_seats"}
                ]
            }
        }
        
        logger.info("Ticket Booking Assistant initialized successfully")
    
    def classify_intent(self, user_query: str) -> str:
        """Classify user intent based on keywords (improved matching)"""
        query_lower = user_query.lower()
        
        # Check each intent's keywords
        for intent, data in self.response_templates.items():
            if any(keyword in query_lower for keyword in data["keywords"]):
                return intent
        
        # Default to help
        return "help_general"
    
    def generate_response(self, user_query: str, context: dict = None):
        """
        Generate accurate response using templates
        Returns: (response_text, intent, suggestions)
        """
        try:
            # Classify intent
            intent = self.classify_intent(user_query)
            logger.info(f"Classified intent: {intent} for query: {user_query[:50]}...")
            
            # Get template response
            template = self.response_templates.get(intent, self.response_templates["help_general"])
            
            response_text = template["response"]
            suggestions = template["suggestions"]
            
            logger.info(f"Generated template response for intent: {intent}")
            
            return response_text, intent, suggestions
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._get_fallback_response(user_query)
    
    def _get_fallback_response(self, user_query: str):
        """Fallback response if something goes wrong"""
        response = "I'm here to help with ticket bookings! You can ask me about:\n• How to book seats\n• Checking seat availability\n• Payment process\n• Account registration\n• Cancellation policy\n\nWhat would you like to know?"
        suggestions = [
            {"title": "Booking Help", "payload": "booking_help"},
            {"title": "Check Seats", "payload": "check_seats"},
            {"title": "View FAQ", "payload": "faq"}
        ]
        
        return response, "help_general", suggestions


class ChatbotService(chatbot_pb2_grpc.ChatbotServicer):
    """gRPC service for improved chatbot"""
    
    def __init__(self):
        """Initialize the chatbot service"""
        logger.info("Initializing Chatbot Service...")
        self.assistant = TicketBookingAssistant()
        logger.info("Chatbot Service initialized successfully")
    
    def Ask(self, request, context):
        """Handle chatbot query requests"""
        user_id = request.user_id
        user_query = request.text
        session_id = request.session_id
        user_context = dict(request.context) if request.context else {}
        
        logger.info(f"Received query from user {user_id}: {user_query}")
        
        try:
            # Generate response
            response_text, intent, suggestions = self.assistant.generate_response(
                user_query, 
                user_context
            )
            
            # Convert suggestions to protobuf format
            pb_suggestions = [
                chatbot_pb2.Suggestion(title=s["title"], payload=s["payload"])
                for s in suggestions
            ]
            
            return chatbot_pb2.AskResponse(
                reply_text=response_text,
                intent=intent,
                suggestions=pb_suggestions
            )
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return chatbot_pb2.AskResponse(
                reply_text="I apologize, but I'm having trouble processing your request. Please try asking: 'How do I book a seat?' or 'What is the seat query button for?'",
                intent="error",
                suggestions=[]
            )


def serve():
    """Start the chatbot gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    chatbot_pb2_grpc.add_ChatbotServicer_to_server(
        ChatbotService(), 
        server
    )
    
    # Use port 7000 to match config
    server.add_insecure_port("[::]:9000")
    
    logger.info("=" * 60)
    logger.info("Chatbot Service running on port 9000")
    logger.info("Domain: Ticket Booking Assistance")
    logger.info("Mode: Template-based with high accuracy")
    logger.info("=" * 60)
    
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()