"""
LLM-Powered Chatbot Service for Ticket Booking Domain
Uses Hugging Face Transformers with a lightweight, CPU-optimized model
"""

import logging
from concurrent import futures
import grpc
import os
import sys
import json
from typing import List, Dict

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import proto.chatbot_pb2 as chatbot_pb2
import proto.chatbot_pb2_grpc as chatbot_pb2_grpc

# LLM imports
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch

logger = logging.getLogger("llm-chatbot")
logging.basicConfig(level=logging.INFO)


class TicketBookingLLM:
    """
    Domain-specific LLM wrapper for ticket booking assistance.
    Uses DistilGPT2 for lightweight CPU inference with booking context.
    """
    
    def __init__(self, model_name="distilgpt2"):
        """Initialize the LLM model with booking domain knowledge"""
        logger.info(f"Loading LLM model: {model_name}")
        
        try:
            # Use CPU-optimized settings
            self.device = "cpu"
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float32,  # CPU works best with float32
                low_cpu_mem_usage=True
            )
            
            # Set padding token
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Create text generation pipeline
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1,  # -1 means CPU
                max_new_tokens=100,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.2
            )
            
            logger.info("LLM model loaded successfully on CPU")
            
        except Exception as e:
            logger.error(f"Failed to load LLM model: {e}")
            raise
    
    def get_domain_context(self) -> str:
        """Return domain-specific context for ticket booking"""
        return """You are a helpful ticket booking assistant. You help users with:
- Booking concert and event tickets
- Checking seat availability
- Understanding the booking process
- Payment information
- Cancellation policies
- Account management

Keep responses concise (2-3 sentences), friendly, and specific to ticket booking."""
    
    def classify_intent(self, user_query: str) -> str:
        """Classify user intent based on keywords"""
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in ["book", "reserve", "buy", "purchase"]):
            return "booking"
        elif any(word in query_lower for word in ["cancel", "refund", "return"]):
            return "cancellation"
        elif any(word in query_lower for word in ["available", "free", "seats", "left"]):
            return "availability"
        elif any(word in query_lower for word in ["pay", "payment", "cost", "price"]):
            return "payment"
        elif any(word in query_lower for word in ["account", "login", "register", "password"]):
            return "account"
        elif any(word in query_lower for word in ["help", "how", "what", "when"]):
            return "help"
        else:
            return "general"
    
    def get_context_prompt(self, intent: str, user_query: str) -> str:
        """Build context-aware prompt based on intent"""
        
        domain_context = self.get_domain_context()
        
        # Intent-specific guidance
        intent_guidance = {
            "booking": "Explain how to book tickets step by step.",
            "cancellation": "Explain the cancellation and refund policy.",
            "availability": "Explain how to check seat availability.",
            "payment": "Explain payment options and security.",
            "account": "Explain account registration and login.",
            "help": "Provide helpful guidance.",
            "general": "Provide relevant booking assistance."
        }
        
        guidance = intent_guidance.get(intent, intent_guidance["general"])
        
        prompt = f"""{domain_context}

Intent: {intent}
Task: {guidance}
User Question: {user_query}

Assistant Response:"""
        
        return prompt
    
    def generate_response(self, user_query: str, context: Dict[str, str] = None) -> tuple[str, str, List[Dict]]:
        """
        Generate LLM response for user query
        Returns: (response_text, intent, suggestions)
        """
        try:
            # Classify intent
            intent = self.classify_intent(user_query)
            logger.info(f"Classified intent: {intent} for query: {user_query[:50]}...")
            
            # Build context-aware prompt
            prompt = self.get_context_prompt(intent, user_query)
            
            # Generate response using LLM
            outputs = self.generator(
                prompt,
                max_new_tokens=80,
                num_return_sequences=1,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            # Extract generated text
            full_response = outputs[0]['generated_text']
            
            # Extract only the assistant's response (after "Assistant Response:")
            if "Assistant Response:" in full_response:
                response_text = full_response.split("Assistant Response:")[-1].strip()
            else:
                response_text = full_response.strip()
            
            # Clean up response
            response_text = self._clean_response(response_text)
            
            # Generate intent-specific suggestions
            suggestions = self._get_suggestions(intent)
            
            logger.info(f"Generated response: {response_text[:100]}...")
            
            return response_text, intent, suggestions
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._get_fallback_response(user_query)
    
    def _clean_response(self, text: str) -> str:
        """Clean up generated text"""
        # Remove incomplete sentences
        if not text.endswith(('.', '!', '?')):
            # Find last complete sentence
            for punct in ['.', '!', '?']:
                if punct in text:
                    text = text.rsplit(punct, 1)[0] + punct
                    break
        
        # Limit length
        sentences = text.split('.')
        if len(sentences) > 3:
            text = '. '.join(sentences[:3]) + '.'
        
        # Remove any prompt artifacts
        text = text.replace("User Question:", "").replace("Assistant:", "").strip()
        
        return text
    
    def _get_suggestions(self, intent: str) -> List[Dict]:
        """Get intent-specific action suggestions"""
        suggestion_map = {
            "booking": [
                {"title": "Check Available Seats", "payload": "check_availability"},
                {"title": "Book a Seat", "payload": "book_seat"}
            ],
            "cancellation": [
                {"title": "View My Bookings", "payload": "view_bookings"},
                {"title": "Contact Support", "payload": "contact_support"}
            ],
            "availability": [
                {"title": "View Seat Map", "payload": "view_seats"},
                {"title": "Book Now", "payload": "book_seat"}
            ],
            "payment": [
                {"title": "View Payment Methods", "payload": "payment_methods"},
                {"title": "Proceed to Payment", "payload": "process_payment"}
            ],
            "account": [
                {"title": "Register Account", "payload": "register"},
                {"title": "Login", "payload": "login"}
            ],
            "help": [
                {"title": "View FAQ", "payload": "faq"},
                {"title": "Contact Support", "payload": "support"}
            ],
            "general": [
                {"title": "Browse Events", "payload": "browse_events"},
                {"title": "Help Center", "payload": "help"}
            ]
        }
        
        return suggestion_map.get(intent, suggestion_map["general"])
    
    def _get_fallback_response(self, user_query: str) -> tuple[str, str, List[Dict]]:
        """Fallback response if LLM fails"""
        intent = self.classify_intent(user_query)
        
        fallback_responses = {
            "booking": "To book a ticket, please login to your account, select your desired event and seats, then proceed to payment. Our system ensures secure and instant booking confirmation.",
            "cancellation": "You can cancel bookings through your account dashboard within 24 hours of booking for a full refund. After 24 hours, cancellation fees may apply.",
            "availability": "Check real-time seat availability by selecting your event. Available seats are shown in green on the seat map.",
            "payment": "We accept all major credit cards and digital payment methods. All transactions are encrypted and secure.",
            "account": "Create an account using your email address. You'll receive a confirmation email to activate your account.",
            "general": "I'm here to help with ticket bookings! You can ask me about booking seats, checking availability, payments, or cancellations."
        }
        
        response = fallback_responses.get(intent, fallback_responses["general"])
        suggestions = self._get_suggestions(intent)
        
        return response, intent, suggestions


class LLMChatbotService(chatbot_pb2_grpc.ChatbotServicer):
    """gRPC service for LLM-powered chatbot"""
    
    def __init__(self):
        """Initialize the LLM chatbot service"""
        logger.info("Initializing LLM Chatbot Service...")
        self.llm = TicketBookingLLM(model_name="distilgpt2")
        logger.info("LLM Chatbot Service initialized successfully")
    
    def Ask(self, request, context):
        """Handle chatbot query requests"""
        user_id = request.user_id
        user_query = request.text
        session_id = request.session_id
        user_context = dict(request.context) if request.context else {}
        
        logger.info(f"Received query from user {user_id}: {user_query}")
        
        try:
            # Generate response using LLM
            response_text, intent, suggestions = self.llm.generate_response(
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
                reply_text="I apologize, but I'm having trouble processing your request. Please try again or contact support.",
                intent="error",
                suggestions=[]
            )


def serve():
    """Start the LLM chatbot gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    chatbot_pb2_grpc.add_ChatbotServicer_to_server(
        LLMChatbotService(), 
        server
    )
    server.add_insecure_port("[::]:9000")
    
    logger.info("=" * 60)
    logger.info("LLM Chatbot Service running on port 9000")
    logger.info("Domain: Ticket Booking Assistance")
    logger.info("Model: DistilGPT2 (CPU-optimized)")
    logger.info("=" * 60)
    
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()