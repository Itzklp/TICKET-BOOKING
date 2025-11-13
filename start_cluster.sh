#!/bin/bash
# start_cluster.sh

# Activate virtual environment
source venv/bin/activate

echo "Using Python environment: $(which python)"
echo "Starting services..."

echo "Starting Auth Service..."
python auth-service/auth-server.py &
AUTH_PID=$!

echo "Starting Payment Service..."
python payment-service/payment-server.py &
PAYMENT_PID=$!

echo "Starting Chatbot Service..."
python chatbot-service/chatbot-server.py &
CHATBOT_PID=$!

echo "Starting Booking Node 1..."
python booking-node/main.py --config booking-node/config-node1.json &
NODE1_PID=$!

sleep 2

echo "Starting Booking Node 2..."
python booking-node/main.py --config booking-node/config-node2.json &
NODE2_PID=$!

sleep 2

echo "Starting Booking Node 3..."
python booking-node/main.py --config booking-node/config-node3.json &
NODE3_PID=$!

echo "All services started!"
echo "Auth PID: $AUTH_PID"
echo "Payment PID: $PAYMENT_PID"
echo "Chatbot PID: $CHATBOT_PID"
echo "Node1 PID: $NODE1_PID (Leader candidate)"
echo "Node2 PID: $NODE2_PID"
echo "Node3 PID: $NODE3_PID"
