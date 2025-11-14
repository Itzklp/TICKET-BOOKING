#!/bin/bash
# start_client.sh
# Opens the client CLI in a new terminal window


PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE} Launching Client CLI in new terminal...${NC}\n"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}  Virtual environment not found!${NC}"
    echo -e "${YELLOW}Please run ./start_cluster_terminals.sh first${NC}"
    exit 1
fi

# Detect OS and open terminal
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    osascript <<EOF
tell application "Terminal"
    do script "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════════════════' && echo '  🎫 Distributed Ticket Booking System - Client' && echo '═══════════════════════════════════════════════════' && echo '' && echo '✅ Connected to cluster' && echo '📡 Auth: 127.0.0.1:8000' && echo '💳 Payment: 127.0.0.1:6000' && echo '🤖 Chatbot: 127.0.0.1:9000' && echo '🎫 Booking Nodes: 50051-50053' && echo '' && python client/client-cli.py"
    set custom title of front window to "Booking System Client"
end tell
EOF
    
    echo -e "${GREEN} Client terminal opened!${NC}"

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal --title="Booking System Client" -- bash -c "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════════════════' && echo '  🎫 Distributed Ticket Booking System - Client' && echo '═══════════════════════════════════════════════════' && echo '' && echo '✅ Connected to cluster' && echo '📡 Auth: 127.0.0.1:8000' && echo '💳 Payment: 127.0.0.1:6000' && echo '🤖 Chatbot: 127.0.0.1:9000' && echo '🎫 Booking Nodes: 50051-50053' && echo '' && python client/client-cli.py; exec bash"
        
    elif command -v konsole &> /dev/null; then
        konsole --new-tab -p tabtitle="Booking System Client" -e bash -c "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════════════════' && echo '  🎫 Distributed Ticket Booking System - Client' && echo '═══════════════════════════════════════════════════' && echo '' && echo '✅ Connected to cluster' && echo '📡 Auth: 127.0.0.1:8000' && echo '💳 Payment: 127.0.0.1:6000' && echo '🤖 Chatbot: 127.0.0.1:9000' && echo '🎫 Booking Nodes: 50051-50053' && echo '' && python client/client-cli.py; exec bash"
        
    elif command -v xterm &> /dev/null; then
        xterm -title "Booking System Client" -e bash -c "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════════════════' && echo '  🎫 Distributed Ticket Booking System - Client' && echo '═══════════════════════════════════════════════════' && echo '' && echo '✅ Connected to cluster' && echo '📡 Auth: 127.0.0.1:8000' && echo '💳 Payment: 127.0.0.1:6000' && echo '🤖 Chatbot: 127.0.0.1:9000' && echo '🎫 Booking Nodes: 50051-50053' && echo '' && python client/client-cli.py; exec bash" &
    else
        echo -e "${YELLOW}⚠️  No supported terminal emulator found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN} Client terminal opened!${NC}"
else
    echo -e "${YELLOW}  Unsupported OS: $OSTYPE${NC}"
    exit 1
fi