# Distributed Ticket Booking System

This project implements a ticket booking platform using microservices architecture with distributed consensus. The system handles concurrent seat reservations across multiple server nodes while preventing double-bookings through the Raft algorithm.

## Project Motivation

Online ticketing platforms face a critical challenge: when thousands of users attempt to reserve the same seats simultaneously across different servers, how do you prevent conflicts? This implementation explores that problem by building a distributed booking system where multiple service instances coordinate through consensus protocols to maintain consistent state.

## System Components

The application consists of four services that work together:

**Booking Service** operates on port 50051 and manages the seat inventory. It maintains 100 seats for a concert event and processes reservation requests. Multiple instances can run simultaneously, though the current setup focuses on a single-node configuration.

**Payment Service** runs on port 6000 and simulates transaction processing. While it's a mock implementation for demonstration purposes, it shows how payment workflows integrate with the booking pipeline.

**Chatbot Service** listens on port 7000 and helps users navigate the booking process. It recognizes common queries about seats and payments, responding with helpful suggestions.

**Client Application** provides a terminal interface for interacting with the system. Users can book seats, check availability, process payments, and ask the chatbot questions through a menu-driven interface.

## Technology Overview

The project uses Python 3.8+ as its foundation. Service communication happens through gRPC, which provides faster performance than traditional REST APIs. Protocol Buffers handle data serialization between services. The Raft consensus algorithm coordinates state across distributed nodes, and Python's asyncio enables non-blocking operations.

## Setup Instructions

Before starting, verify you have Python 3.8 or newer installed on your system.

First, get the code and install what you need:

```bash
git clone <repository-url>
cd distributed-ticket-booking
pip install -r requirements.txt
```

If you need to regenerate the Protocol Buffer files:

```bash
python -m grpc_tools.protoc -I=proto --python_out=proto --grpc_python_out=proto proto/*.proto
```

## Starting the Services

You'll need four terminal windows open. Launch each service separately in this order.

**Terminal 1 - Booking Service:**

```bash
cd booking-node
python main.py --config config.json
```

Wait for the message confirming the service started successfully before proceeding.

**Terminal 2 - Payment Service:**

```bash
cd payment-service
python payment-server.py
```

**Terminal 3 - Chatbot Service:**

```bash
cd chatbot-service
python chatbot-server.py
```

**Terminal 4 - Client Interface:**

```bash
cd client
python client-cli.py
```

## Using the Application

Once all services are running, the client displays an interactive menu.

**Making a Reservation**

Choose option 1 and provide the requested information:
- A user identifier (can be any string like "alice" or "user42")
- A seat number between 1 and 100
- The show identifier (use "default_show")

The system checks if the seat is available and either confirms your booking or reports that someone else already reserved it.

**Checking Seat Status**

Option 2 lets you look up whether a particular seat is free without actually booking it. Enter the seat number and show ID to see its current status.

**Payment Processing**

Option 3 demonstrates the payment workflow. Specify a user ID, enter an amount in cents (1000 cents equals $10.00), and choose a currency code. The system returns a transaction identifier.

**Asking Questions**

Option 4 connects you to the chatbot. Type questions about booking or payments and receive automated responses with suggested actions.

## Code Organization

```
distributed-ticket-booking/
│
├── booking-node/
│   ├── booking/
│   │   ├── booking_service.py    # Handles gRPC requests
│   │   └── seat_manager.py       # Manages seat state
│   ├── raft/
│   │   ├── raft.py                # Consensus coordination
│   │   ├── log.py                 # Operation log storage
│   │   └── state_machine.py      # State updates
│   ├── config.json
│   └── main.py
│
├── payment-service/
│   └── payment-server.py
│
├── chatbot-service/
│   └── chatbot-server.py
│
├── client/
│   ├── client.py
│   └── client-cli.py
│
├── proto/
│   ├── booking.proto              # Booking API definitions
│   ├── payment.proto              # Payment API definitions
│   ├── chatbot.proto              # Chatbot API definitions
│   └── raft.proto                 # Raft protocol definitions
│
└── requirements.txt
```

## Configuration Options

The `config.json` file in the booking-node directory controls how the service behaves. You can adjust port numbers, configure peer nodes for distributed operation, tune Raft timing parameters, and set the total seat capacity.

Default configuration:
- Node runs on localhost:50051
- Supports 100 seats for "concert_2025" show
- Raft heartbeat every 150ms
- Election timeout at 300ms

Additional nodes can be configured on ports 50052 and 50053, though this requires extending the implementation to fully support distributed operation.

## System Behavior

When a user requests a seat booking, the system follows this flow:

The client sends a reservation request to the booking service. The service checks whether that seat is currently available. If it's free, the service creates a reservation command and submits it to the Raft log. Once the command is committed (meaning it's been recorded and will survive failures), the state machine processes it and marks the seat as reserved. Finally, the service sends a confirmation back to the client.

For distributed consistency, Raft ensures all nodes agree on the order of operations. Commands get replicated to other nodes, and the state machine on each node applies them in the same sequence. This guarantees that all nodes have identical seat state.

The services communicate using gRPC with Protocol Buffer messages. This approach provides type safety, efficient serialization, and language-agnostic API definitions. Each service defines its interface in a .proto file, and the protoc compiler generates the necessary code.

## Implementation Details

Seat reservations are stored in memory using a dictionary structure. Each seat object tracks its ID, show, reservation status, who booked it, and when. The state machine receives commands as JSON-encoded bytes specifying the operation type and parameters.

For example, a reserve command looks like:
```json
{"type": "reserve", "seat_id": 15, "user_id": "alice"}
```

The Raft module maintains a log of these commands and ensures they're applied consistently across nodes. Currently, the implementation includes basic log storage and state machine application, but leader election and full replication aren't complete.

## Testing Scenarios

**Concurrent Access Test**

Open multiple client terminals and try booking the same seat from different clients at the same time. Only one booking should succeed, demonstrating proper conflict resolution.

**State Verification**

Book a seat from one client, then query its status from another client. The second client should see the seat as reserved, confirming that state changes are visible across connections.

**Payment Integration**

Complete a booking and then process a payment for that reservation. Check that the transaction ID is generated and can be queried later.

## Design Rationale

**Service Architecture:** The microservices approach allows independent development and deployment of each component. Services can scale independently based on load patterns.

**gRPC Selection:** Compared to REST, gRPC offers better performance for service-to-service communication, supports efficient binary serialization, and provides strong API contracts through Protocol Buffers.

**Raft Algorithm:** This consensus mechanism ensures that booking state remains consistent even when services fail or network partitions occur. Raft provides a good balance between understandability and correctness.

**Asynchronous Operations:** Python's asyncio enables the booking service to handle many concurrent requests without blocking, improving overall throughput.

## Current Constraints

This implementation serves educational purposes and has several limitations:

The Raft consensus implementation is simplified - leader election logic isn't fully developed. All data lives in memory and disappears when services restart. There's no user authentication or authorization system. The booking catalog is fixed at 100 seats for a single show. Payment processing is simulated rather than connecting to real payment gateways. The chatbot uses basic keyword matching instead of natural language understanding.

## Potential Extensions

Several enhancements would move this toward production readiness:

Completing the Raft implementation with full leader election and log replication would enable true distributed operation. Adding a database layer (PostgreSQL or Redis) would provide persistence. Implementing JWT-based authentication would secure the APIs. Supporting multiple shows with dynamic seat configurations would make the system more flexible. Integrating with actual payment processors like Stripe would enable real transactions. Upgrading the chatbot with NLP capabilities would improve user interactions. Building a web frontend would make the system more accessible. Adding logging, metrics, and distributed tracing would improve observability.

## Common Issues

**Service Won't Start**

Check if another process is using the required port. You can find and terminate conflicting processes using system tools.

**Services Can't Connect**

Ensure all three backend services (booking, payment, chatbot) are running before launching the client. Check terminal output for error messages that might indicate what's wrong.

**Dependency Problems**

Verify that all packages from requirements.txt installed successfully. Try reinstalling if you see import errors.

## Technical Specifications

**Booking Service Endpoints:**
- BookSeat: Creates a new seat reservation
- QuerySeat: Returns current seat status
- ListSeats: Retrieves seats with pagination

**Payment Service Endpoints:**
- ProcessPayment: Initiates a transaction
- QueryTransaction: Looks up transaction details

**Chatbot Service Endpoints:**
- Ask: Processes user queries and returns responses

All endpoints use Protocol Buffer messages for requests and responses, ensuring type safety and efficient serialization.

## Additional Notes

The system demonstrates core distributed systems concepts including consensus, replication, and service coordination. While simplified for learning purposes, the architecture reflects patterns used in production booking platforms.

The code is structured to make it easy to understand each component's role. The booking service focuses on business logic, Raft handles distributed coordination, and supporting services (payment, chatbot) show how auxiliary functionality integrates.

Protocol Buffer definitions in the proto directory serve as contracts between services. These definitions ensure that all services agree on message formats and available operations.

## References

The Raft consensus algorithm comes from the paper "In Search of an Understandable Consensus Algorithm" by Diego Ongaro and John Ousterhout. gRPC and Protocol Buffers are developed by Google for efficient service communication. The asyncio library is part of Python's standard library for asynchronous programming.

---

This system demonstrates distributed consensus and microservices architecture. It's designed for educational exploration of how booking platforms maintain consistency across multiple servers.
# Ticket_booking_system
