# Distributed Ticket Booking System

A production-grade distributed ticket booking platform implementing **Raft consensus algorithm** for strong consistency across multiple nodes. The system prevents double-bookings through leader election, log replication, and state machine synchronization while maintaining high availability through automatic failover.

---

## Project Overview

This system demonstrates core distributed systems concepts by building a real-world ticket booking platform where multiple service instances coordinate through the Raft consensus protocol. When thousands of users attempt to reserve the same seats simultaneously across different servers, the system maintains consistency and prevents conflicts through distributed consensus.

### Key Achievements
- **Zero Double-Bookings**: Raft consensus guarantees exactly-once seat reservations
- **High Availability**: Automatic leader election and failover (< 300ms recovery)
- **Strong Consistency**: All nodes maintain identical state through log replication
- **Concurrent Safety**: Tested with 30+ simultaneous booking requests
- **Production Patterns**: gRPC communication, JWT authentication, payment integration

---

### Service Descriptions

#### 1. **Authentication Service** (Port 8000)
- **Purpose**: User identity management and session handling
- **Features**:
  - Email-based registration with regex validation
  - Password authentication (production would use bcrypt)
  - JWT-like session tokens
  - Admin user management (deterministic UUID: `00000000-0000-0000-0000-000000000000`)
  - Persistent storage (`auth_data.json`)
- **Tech**: gRPC, Protocol Buffers, JSON file storage

#### 2. **Payment Service** (Port 6000)
- **Purpose**: Transaction processing and validation
- **Features**:
  - Card number validation (fails on `9999` for testing)
  - Transaction ID generation
  - Transaction history querying
  - Persistent storage (`payment_data.json`)
  - Masked card number storage for security
- **Tech**: gRPC, UUID-based transaction IDs

#### 3. **Chatbot Service** (Port 9000)
- **Purpose**: User assistance and query handling
- **Features**:
  - Intent classification (booking, payment, account, etc.)
  - Template-based responses for accuracy
  - Contextual suggestions
  - Multi-turn conversation support
- **Supported Intents**:
  - Booking assistance
  - Seat availability queries
  - Payment information
  - Account management
  - Cancellation policies

#### 4. **Booking Service Cluster** (Ports 50051-50053)
- **Purpose**: Core ticket reservation with distributed consensus
- **Raft Implementation**:
  - **Leader Election**: Automatic election with randomized timeouts (150-300ms)
  - **Log Replication**: Commands replicated to all nodes before commit
  - **State Machine**: Applies committed commands for seat reservations
  - **Heartbeats**: Leader sends heartbeats every 50ms
- **Admin Operations** (Admin-only):
  - `AddShow`: Create/update shows with seat capacity and pricing
  - `ListShows`: View all available shows
- **User Operations**:
  - `BookSeat`: Reserve a seat (payment → Raft → commit)
  - `QuerySeat`: Check seat availability
  - `ListSeats`: View seat status (paginated)

---

##  Technical Implementation

### Raft Consensus Protocol

#### Leader Election
```python
# Election Timeout: 150-300ms (randomized)
# Heartbeat Interval: 50ms

Candidate State:
1. Increment term
2. Vote for self
3. Send RequestVote to all peers
4. If majority votes received → Become Leader
5. If higher term discovered → Become Follower
```

**Key Features**:
- Randomized election timeouts prevent split votes
- Candidates with up-to-date logs win elections
- Automatic re-election on leader failure

#### Log Replication
```python
Leader:
1. Append command to local log
2. Send AppendEntries RPC to all followers
3. Wait for majority acknowledgment
4. Commit entry and apply to state machine
5. Update followers' commit index

Follower:
1. Receive AppendEntries RPC
2. Check log consistency (prev_log_index, prev_log_term)
3. Append entries if consistent
4. Acknowledge to leader
5. Apply committed entries
```

**Consistency Guarantees**:
- All nodes apply commands in same order
- Committed entries never lost (even with failures)
- Safety: Only one leader per term

#### State Machine
```python
Command Types:
- reserve: {"type": "reserve", "show_id": "...", "seat_id": 1, "user_id": "...", "booking_id": "..."}
- add_show: {"type": "add_show", "show_id": "...", "total_seats": 100, "price_cents": 1000}
- release: {"type": "release", "show_id": "...", "seat_id": 1}

State Storage:
{
  "show_id": {
    "total_seats": 100,
    "price_cents": 1000,
    "seats": {
      "1": {"reserved": true, "user_id": "...", "booking_id": "...", "reserved_at": 1234567890}
    }
  }
}
```

**Persistence**: State saved to `state_machine_data.json` after every command

### Booking Flow (End-to-End)

```
User Request
     ↓
1. Auth Service validates session token
     ↓
2. Booking Service checks seat availability
     ↓
3. Payment Service processes transaction
     ↓ (If payment succeeds)
4. Leader appends reserve command to log
     ↓
5. Leader replicates to followers (Raft)
     ↓
6. Once majority acknowledges → Commit
     ↓
7. State machine applies reservation
     ↓
8. Confirmation returned to user
```

**Failure Handling**:
- Payment fails → No Raft proposal, return error
- Leader fails → Automatic failover, retry on new leader
- Network partition → Only majority partition accepts bookings

### gRPC & Protocol Buffers

**Why gRPC?**
- 5-10x faster than REST (binary serialization)
- Strongly-typed contracts (`.proto` files)
- Bi-directional streaming support
- Language-agnostic

**Key Proto Definitions**:
- `booking.proto`: BookSeat, QuerySeat, ListSeats, AddShow, ListShows
- `raft.proto`: AppendEntries, RequestVote
- `auth.proto`: Register, Login, ValidateSession
- `payment.proto`: ProcessPayment, QueryTransaction
- `chatbot.proto`: Ask

---

##  Installation & Setup

### Prerequisites
- **Python**: 3.8 or higher
- **pip**: Python package manager
- **OS**: macOS or Linux (Windows WSL supported)

### Step 1: Clone Repository
```bash
git clone <https://github.com/Itzklp/TICKET-BOOKING>
cd distributed-ticket-booking
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Dependencies**:
- `grpcio`: gRPC framework
- `grpcio-tools`: Protocol Buffer compiler
- `protobuf`: Protocol Buffer runtime
- `asyncio`: Async I/O support

### Step 4: Generate Protocol Buffer Code (Optional)
```bash
# Only needed if .proto files are modified
python -m grpc_tools.protoc -I=proto --python_out=proto --grpc_python_out=proto proto/*.proto
```

---

##  Running the System

### Option 1: Automated Terminal Launcher (Recommended)

**Start All Services**:
```bash
chmod +x start_cluster_terminals.sh  # First time only for Linux or MacOs
./start_cluster_terminals.sh
start_cluster_terminals.bat # First time only for Windows
```

This opens 6 separate terminal windows:
- Auth Service (8000)
- Payment Service (6000)
- Chatbot Service (9000)
- Booking Node 1 (50051) - Leader candidate
- Booking Node 2 (50052)
- Booking Node 3 (50053)

**Wait for Stabilization** (15 seconds):
The cluster needs time for leader election and log synchronization.

**Start Client**:
```bash
chmod +x start_client.sh  # First time only for Linux or MacOs
./start_client.sh
start_client.bat # First time only for Windows
```

**Stop All Services**:
```bash
./stop_cluster.sh # For Linux or MacOs
stop_cluster.bat # For Windows
```

### Option 2: Manual Startup

**Terminal 1 - Auth Service**:
```bash
source venv/bin/activate
python auth-service/auth-server.py
```

**Terminal 2 - Payment Service**:
```bash
source venv/bin/activate
python payment-service/payment-server.py
```

**Terminal 3 - Chatbot Service**:
```bash
source venv/bin/activate
python chatbot-service/chatbot-server.py
```

**Terminal 4 - Booking Node 1**:
```bash
source venv/bin/activate
python booking-node/main.py --config booking-node/config-node1.json
```

**Terminal 5 - Booking Node 2**:
```bash
source venv/bin/activate
python booking-node/main.py --config booking-node/config-node2.json
```

**Terminal 6 - Booking Node 3**:
```bash
source venv/bin/activate
python booking-node/main.py --config booking-node/config-node3.json
```

**Terminal 7 - Client**:
```bash
source venv/bin/activate
python client/client-cli.py
```

---

##  Using the Client Interface

### Main Menu Options

```
═══════════════════════════════════════════════════════════
  Status: Logged in as: abc123... [ADMIN]
  Target Node: 127.0.0.1:50051
═══════════════════════════════════════════════════════════

[SHOWS & BOOKING]
  1. List All Shows
  2. View Show Details
  3. Book a Seat
  4. My Bookings

[ACCOUNT]
  5. Register User
  6. Login User

[SERVICES]
  7. Booking Assistant (Chatbot)
  8. Payment Test

[ADMIN]
  9. Add/Update Show

  0. Exit
```

### User Workflows

#### First-Time User Flow
1. **Register** (Option 5)
   - Enter email (must be valid format)
   - Enter password
   - Confirmation received

2. **Login** (Option 6)
   - Enter email and password
   - Receive session token

3. **Browse Shows** (Option 1)
   - View available shows
   - See pricing and availability

4. **Book Seat** (Option 3)
   - Select show from list
   - Enter seat number
   - Enter credit card (use any valid number, avoid `9999`)
   - Receive booking confirmation

#### Admin User Flow
**Default Admin Credentials**:
- Email: `admin@gmail.com`
- Password: `admin123`

1. **Login as Admin** (Option 6)

2. **Add Show** (Option 9)
   - Enter show ID (e.g., `concert_2025`)
   - Enter total seats (e.g., `100`)
   - Enter price in dollars (e.g., `25.00`)
   - System converts to cents and creates show

3. **View Shows** (Option 1)
   - See all created shows with statistics

#### Chatbot Assistance (Option 7)
**Example Queries**:
- "How do I book a seat?"
- "What seats are available?"
- "How does payment work?"
- "Can I cancel my booking?"

The chatbot provides detailed, context-aware responses with actionable suggestions.

---

##  Project Structure

```
distributed-ticket-booking/
│
├── auth-service/
│   ├── auth-server.py          # Authentication gRPC server
│   └── auth_data.json           # Persistent user/session storage
│
├── payment-service/
│   ├── payment-server.py        # Payment processing server
│   └── payment_data.json        # Transaction history
│
├── chatbot-service/
│   └── chatbot-server.py        # Intent-based chatbot
│
├── booking-node/
│   ├── booking/
│   │   ├── booking_service.py   # gRPC booking handlers
│   │   └── seat_manager.py      # Seat state management
│   ├── raft/
│   │   ├── raft.py               # Core Raft implementation
│   │   ├── raft_service.py       # Raft RPC handlers
│   │   ├── log.py                # Log storage
│   │   └── state_machine.py      # State machine with persistence
│   ├── data/
│   │   ├── raft_log_1/           # Node 1 log storage
│   │   ├── raft_log_2/           # Node 2 log storage
│   │   ├── raft_log_3/           # Node 3 log storage
│   │   └── state_machine_data.json  # Shared state
│   ├── config.json               # Single-node config
│   ├── config-node1.json         # Node 1 cluster config
│   ├── config-node2.json         # Node 2 cluster config
│   ├── config-node3.json         # Node 3 cluster config
│   └── main.py                   # Node entry point
│
├── client/
│   ├── client-cli.py             # Enhanced CLI with auto-failover
│   └── client.py                 # Basic client (legacy)
│
├── proto/
│   ├── auth.proto                # Authentication definitions
│   ├── auth_pb2.py               # Generated code
│   ├── auth_pb2_grpc.py          # Generated gRPC stubs
│   ├── booking.proto             # Booking service definitions
│   ├── booking_pb2.py
│   ├── booking_pb2_grpc.py
│   ├── payment.proto             # Payment service definitions
│   ├── payment_pb2.py
│   ├── payment_pb2_grpc.py
│   ├── chatbot.proto             # Chatbot definitions
│   ├── chatbot_pb2.py
│   ├── chatbot_pb2_grpc.py
│   ├── raft.proto                # Raft RPC definitions
│   ├── raft_pb2.py
│   └── raft_pb2_grpc.py
│
├── start_cluster_terminals.sh    # Launch all services
├── start_client.sh               # Launch client in new terminal
├── stop_cluster.sh               # Stop all services
├── stress_test.py                # Concurrent booking test
├── test_leader_election.py       # Leader election validation
├── test_raft_failover.py         # Failover test
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

##  Configuration

### Booking Node Configuration

**Key Parameters**:
- `heartbeat_interval_ms`: Leader sends heartbeat every 150ms
- `election_timeout_ms`: Follower starts election after 300ms without heartbeat
- `storage_path`: Raft log persistence location
- `persistence_file`: State machine data location

---

##  Key Features Explained

### 1. Raft Consensus Implementation

**Leader Election**:
- Randomized timeouts (150-300ms) prevent split votes
- Candidates request votes from all peers
- Majority vote required to become leader
- Automatic re-election on failure

**Log Replication**:
- Leader appends commands to local log
- Replicates to all followers via AppendEntries RPC
- Waits for majority acknowledgment
- Commits entry once replicated
- Followers apply committed entries in order

**Safety Properties**:
- **Election Safety**: At most one leader per term
- **Leader Append-Only**: Leader never overwrites log
- **Log Matching**: If two logs contain entry with same index/term, all preceding entries match
- **Leader Completeness**: If entry committed in term, present in all future leaders
- **State Machine Safety**: Servers apply same commands in same order

### 2. Distributed Booking Logic

**Seat Reservation Flow**:
```python
1. Client sends BookSeat request
2. Booking service validates session (Auth Service)
3. Checks seat availability (State Machine)
4. Processes payment (Payment Service)
5. Creates reserve command
6. Proposes command to Raft leader
7. Leader replicates to followers
8. Once majority acknowledges, commits
9. State machine applies reservation
10. Returns confirmation to client
```

**Conflict Resolution**:
- Raft serializes all operations
- Only committed reservations persist
- Failures during proposal → No reservation
- Payment succeeds but Raft fails → Needs refund (noted in code)

### 3. Authentication & Authorization

**Session Management**:
- Session tokens stored in memory (not localStorage-safe)
- Each token maps to user_id
- Validated before each booking operation
- Admin user has special UUID: `00000000-0000-0000-0000-000000000000`

**Admin-Only Operations**:
- `AddShow`: Create/update shows
- `ListShows`: View all shows (implementation detail)

### 4. Payment Integration

**Mock Payment Flow**:
- Validates card number (fails on `9999`)
- Generates UUID transaction ID
- Stores transaction history
- Returns success/failure status

### 5. Chatbot Intelligence

**Intent Classification**:
- Template-based responses (high accuracy)
- Keyword matching on user queries
- Context-aware suggestions

**Supported Intents**:
- `booking`: How to reserve seats
- `query_seat`: Check availability
- `payment`: Payment process
- `account`: Registration/login
- `cancellation`: Refund policies
- `show_info`: Event details
- `help_general`: General assistance

---

##  Troubleshooting

### Common Issues

#### 1. Services Won't Start
**Error**: `Address already in use`

**Solution**:
```bash
# Find and kill existing processes
lsof -ti:8000 | xargs kill -9  # Auth
lsof -ti:6000 | xargs kill -9  # Payment
lsof -ti:9000 | xargs kill -9  # Chatbot
lsof -ti:50051 | xargs kill -9 # Node 1
lsof -ti:50052 | xargs kill -9 # Node 2
lsof -ti:50053 | xargs kill -9 # Node 3

# Or use stop script
./stop_cluster.sh
```

#### 2. No Leader Elected
**Symptoms**: All bookings fail with "not the leader"

**Diagnosis**:
```bash
# Check node logs
tail -f logs/booking_node_*.log

# Look for:
# - "Starting election for term X"
# - "Node X is the LEADER for term Y"
```

**Solution**:
- Wait 15 seconds after startup
- Ensure all 3 nodes are running
- Restart cluster if needed

#### 3. Authentication Fails
**Error**: `Invalid or expired session token`

**Solution**:
- Re-login (option 6)
- Check auth-service is running
- Verify `auth_data.json` exists

#### 4. Booking Fails After Payment
**Error**: `Payment successful but booking failed`

**Root Cause**: Raft proposal timeout

**Solution**:
- Check network connectivity between nodes
- Verify at least 2 nodes are running (majority)
- Increase Raft timeout in config

#### 5. Inconsistent State Across Nodes
**Symptoms**: Different nodes show different seat status

**Diagnosis**:
```bash
# Query same seat from all nodes
# Option 2 in client, try each node
```

**Solution**:
- Wait for log replication (2-3 seconds)
- Check leader is replicating (logs should show AppendEntries)
- Restart cluster if persistent

#### 6. proto file disturbed when build
**Symptoms**: import booking_pb2 as booking__pb2 not found



**Solution**:
- after building the proto files
- open the booking_pb2_grpc.py
- change this line to "import booking_pb2 as booking__pb2"
- to this "from proto import booking_pb2 as booking__pb2"
---

##  Performance & Scalability

### Current Limits
- **Seats per Show**: Unlimited (tested up to 1000)
- **Concurrent Users**: 30+ simultaneous bookings
- **Request Throughput**: ~50 req/sec per leader
- **Election Time**: < 300ms (1 timeout period)
- **Log Replication Latency**: 50-150ms (heartbeat interval)

### Scaling Considerations

**Horizontal Scaling**:
- Add more Raft nodes (5 or 7 recommended for production)
- Separate read-only replicas for queries
- Partition shows across multiple clusters (shard by show_id)

**Vertical Scaling**:
- Increase node resources (CPU/RAM)
- Use SSDs for log storage
- Tune Raft timeouts (lower for faster failover)

**Database Integration**:
- Replace JSON files with PostgreSQL/MongoDB
- Use connection pooling
- Implement caching layer (Redis)

---

##  Learning Resources

### Raft Consensus
- [Original Paper](https://raft.github.io/raft.pdf): "In Search of an Understandable Consensus Algorithm"
- [Visualization](https://raft.github.io/): Interactive Raft demo
- [The Secret Lives of Data](http://thesecretlivesofdata.com/raft/): Animated explanation

### gRPC & Protocol Buffers
- [gRPC Documentation](https://grpc.io/docs/)
- [Protocol Buffers Guide](https://developers.google.com/protocol-buffers)

### Distributed Systems
- [Designing Data-Intensive Applications](https://dataintensive.net/) by Martin Kleppmann
- [Distributed Systems](https://www.distributed-systems.net/) by Maarten van Steen

---

## 👥 Authors

- **Kalp Dalsania** 
  **Saksham Singhal**  


**Built with ❤️ to demonstrate distributed systems in action**
