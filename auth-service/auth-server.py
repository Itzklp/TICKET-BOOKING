"""
Auth Service gRPC Server - Mock implementation for user registration and session management.
"""

import logging
from concurrent import futures
import grpc
import uuid
import os
import sys
import re # <--- NEW: Import the regex module

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from proto import auth_pb2, auth_pb2_grpc

logger = logging.getLogger("auth-service")
logging.basicConfig(level=logging.INFO)

# A robust but common regex pattern for email validation
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# In-memory store: email -> {password, user_id}
USERS = {} 
# In-memory store: token -> user_id
SESSIONS = {} 

class AuthService(auth_pb2_grpc.AuthServiceServicer):
    def Register(self, request, context):
        
        # 1. Basic validation
        if not request.email or not request.password:
            return auth_pb2.RegisterResponse(success=False, message="Email and password are required.")

        # 2. Regex Email Validation <--- NEW LOGIC ADDED HERE
        if not re.fullmatch(EMAIL_REGEX, request.email):
            logger.warning("Registration failed due to invalid email format: %s", request.email)
            return auth_pb2.RegisterResponse(
                success=False, 
                message="Invalid email format. Please use a standard email address (e.g., user@example.com)."
            )

        # 3. Check for existing user
        if request.email in USERS:
            return auth_pb2.RegisterResponse(success=False, message="User already exists.")
        
        # 4. Successful registration (mock)
        user_id = str(uuid.uuid4())
        USERS[request.email] = {"password": request.password, "user_id": user_id}
        logger.info("New user registered: %s", request.email)
        return auth_pb2.RegisterResponse(success=True, message="Registration successful. Please log in.")

    def Login(self, request, context):
        user_data = USERS.get(request.email)
        if not user_data or user_data["password"] != request.password:
            return auth_pb2.LoginResponse(success=False, message="Invalid email or password.")
        
        token = str(uuid.uuid4())
        user_id = user_data["user_id"]
        SESSIONS[token] = user_id
        
        logger.info("User logged in: %s (Token: %s)", user_id, token)
        return auth_pb2.LoginResponse(
            success=True, 
            message="Login successful.",
            session=auth_pb2.Session(token=token, user_id=user_id)
        )

    def ValidateSession(self, request, context):
        user_id = SESSIONS.get(request.token)
        if user_id:
            return auth_pb2.ValidateSessionResponse(valid=True, user_id=user_id)
        
        return auth_pb2.ValidateSessionResponse(valid=False, user_id="")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    server.add_insecure_port("[::]:8000")
    logger.info("Auth service running on port 8000...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()