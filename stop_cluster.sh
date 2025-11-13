#!/bin/bash
# stop_cluster.sh

echo "Stopping all cluster services..."
pkill -f "auth-server.py"
pkill -f "payment-server.py"
pkill -f "chatbot-server.py"
pkill -f "booking-node/main.py"
echo "All services stopped!"
