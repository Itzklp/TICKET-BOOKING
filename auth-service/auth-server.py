import logging
from concurrent import futures
import grpc
import uuid
import os
import sys
import re 
import json


sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from proto import auth_pb2, auth_pb2_grpc

logger = logging.getLogger("auth-service")
logging.basicConfig(level=logging.INFO)

# A robust but common regex pattern for email validation
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# --- PERSISTENCE CONFIG ---
# Data will be saved in auth-service/auth_data.json
PERSISTENCE_FILE = os.path.join(os.path.dirname(__file__), "auth_data.json")

# --- ADMIN CONFIG ---
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

ADMIN_UUID_SEED = "00000000-0000-0000-0000-000000000000" 
ADMIN_ID = str(uuid.UUID(ADMIN_UUID_SEED)) 


USERS = {} 

SESSIONS = {} 

def _load_data():
    """Load user and session data from local file."""
    global USERS, SESSIONS
    try:
        if os.path.exists(PERSISTENCE_FILE):
            with open(PERSISTENCE_FILE, "r") as f:
                data = json.load(f)
                USERS = data.get("users", {})
                SESSIONS = data.get("sessions", {})
        logger.info("Loaded auth data from %s", PERSISTENCE_FILE)
    except Exception as e:
        logger.error("Error loading auth data: %s", e)

def _save_data():
    """Save user and session data to local file."""
    try:
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump({"users": USERS, "sessions": SESSIONS}, f, indent=2)
        logger.debug("Saved auth data to %s", PERSISTENCE_FILE)
    except Exception as e:
        logger.error("Error saving auth data: %s", e)

def _ensure_admin_user():
    """Ensure the default admin user exists."""
    if ADMIN_EMAIL not in USERS:
        USERS[ADMIN_EMAIL] = {"password": ADMIN_PASSWORD, "user_id": ADMIN_ID}
        logger.warning("Default admin user created: %s (ID: %s)", ADMIN_EMAIL, ADMIN_ID)
        _save_data() 
    elif USERS[ADMIN_EMAIL].get("user_id") != ADMIN_ID:

        USERS[ADMIN_EMAIL]["user_id"] = ADMIN_ID
        _save_data()
        logger.info("Admin user ID ensured to be correct: %s", ADMIN_ID)


# Load data on service start and ensure admin exists
_load_data()
_ensure_admin_user()


class AuthService(auth_pb2_grpc.AuthServiceServicer):
    def Register(self, request, context):
        
        #  Basic validation
        if not request.email or not request.password:
            return auth_pb2.RegisterResponse(success=False, message="Email and password are required.")

        #  Prevent overwriting admin
        if request.email == ADMIN_EMAIL:
             return auth_pb2.RegisterResponse(success=False, message="Cannot register admin email.")

        #  Regex Email Validation 
        if not re.fullmatch(EMAIL_REGEX, request.email):
            logger.warning("Registration failed due to invalid email format: %s", request.email)
            return auth_pb2.RegisterResponse(
                success=False, 
                message="Invalid email format. Please use a standard email address (e.g., user@example.com)."
            )

        #  Check for existing user
        if request.email in USERS:
            return auth_pb2.RegisterResponse(success=False, message="User already exists.")
        
        #  Successful registration
        user_id = str(uuid.uuid4())
        USERS[request.email] = {"password": request.password, "user_id": user_id}
        logger.info("New user registered: %s", request.email)
        _save_data() 
        return auth_pb2.RegisterResponse(success=True, message="Registration successful. Please log in.")

    def Login(self, request, context):
        user_data = USERS.get(request.email)
        if not user_data or user_data["password"] != request.password:
            return auth_pb2.LoginResponse(success=False, message="Invalid email or password.")
        
        token = str(uuid.uuid4())
        user_id = user_data["user_id"]
        SESSIONS[token] = user_id
        
        logger.info("User logged in: %s (Token: %s)", user_id, token)
        _save_data() 
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