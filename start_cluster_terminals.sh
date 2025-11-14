#!/bin/bash
# start_cluster_terminals.sh
# Opens each service in a separate terminal window (macOS compatible)


PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Starting Distributed Booking Cluster${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}  Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    pip install -r requirements.txt
fi

# Detect the operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use osascript to open Terminal windows
    TERM_CMD="osascript"
    
    echo -e "${GREEN} Detected macOS - using Terminal.app${NC}\n"
    
    # Function to open a new Terminal window and run command
    open_terminal_mac() {
        local title=$1
        local command=$2
        
        osascript <<EOF
tell application "Terminal"
    do script "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════' && echo '  $title' && echo '═══════════════════════════════════════' && echo '' && $command"
    set custom title of front window to "$title"
end tell
EOF
    }
    
    # Launch each service
    echo -e "${GREEN} Launching Auth Service...${NC}"
    open_terminal_mac "Auth Service (Port 8000)" "python auth-service/auth-server.py"
    sleep 1
    
    echo -e "${GREEN} Launching Payment Service...${NC}"
    open_terminal_mac "Payment Service (Port 6000)" "python payment-service/payment-server.py"
    sleep 1
    
    echo -e "${GREEN} Launching Chatbot Service...${NC}"
    open_terminal_mac "Chatbot Service (Port 9000)" "python chatbot-service/chatbot-server.py"
    sleep 1
    
    echo -e "${GREEN} Launching Booking Node 1...${NC}"
    open_terminal_mac "Booking Node 1 (Port 50051)" "python booking-node/main.py --config booking-node/config-node1.json"
    sleep 2
    
    echo -e "${GREEN} Launching Booking Node 2...${NC}"
    open_terminal_mac "Booking Node 2 (Port 50052)" "python booking-node/main.py --config booking-node/config-node2.json"
    sleep 2
    
    echo -e "${GREEN} Launching Booking Node 3...${NC}"
    open_terminal_mac "Booking Node 3 (Port 50053)" "python booking-node/main.py --config booking-node/config-node3.json"
    sleep 1

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - try various terminal emulators
    echo -e "${GREEN} Detected Linux${NC}\n"
    
    # Detect available terminal emulator
    if command -v gnome-terminal &> /dev/null; then
        TERM_CMD="gnome-terminal"
        echo -e "${GREEN}Using gnome-terminal${NC}\n"
        
        open_terminal_linux() {
            local title=$1
            local command=$2
            gnome-terminal --title="$title" -- bash -c "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════' && echo '  $title' && echo '═══════════════════════════════════════' && echo '' && $command; exec bash"
        }
        
    elif command -v konsole &> /dev/null; then
        TERM_CMD="konsole"
        echo -e "${GREEN}Using konsole${NC}\n"
        
        open_terminal_linux() {
            local title=$1
            local command=$2
            konsole --new-tab -p tabtitle="$title" -e bash -c "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════' && echo '  $title' && echo '═══════════════════════════════════════' && echo '' && $command; exec bash"
        }
        
    elif command -v xterm &> /dev/null; then
        TERM_CMD="xterm"
        echo -e "${GREEN}Using xterm${NC}\n"
        
        open_terminal_linux() {
            local title=$1
            local command=$2
            xterm -title "$title" -e bash -c "cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && clear && echo '═══════════════════════════════════════' && echo '  $title' && echo '═══════════════════════════════════════' && echo '' && $command; exec bash" &
        }
        
    else
        echo -e "${YELLOW}  No supported terminal emulator found${NC}"
        echo -e "${YELLOW}Please install gnome-terminal, konsole, or xterm${NC}"
        exit 1
    fi
    
    # Launch each service
    echo -e "${GREEN} Launching Auth Service...${NC}"
    open_terminal_linux "Auth Service (Port 8000)" "python auth-service/auth-server.py"
    sleep 1
    
    echo -e "${GREEN} Launching Payment Service...${NC}"
    open_terminal_linux "Payment Service (Port 6000)" "python payment-service/payment-server.py"
    sleep 1
    
    echo -e "${GREEN} Launching Chatbot Service...${NC}"
    open_terminal_linux "Chatbot Service (Port 9000)" "python chatbot-service/chatbot-server.py"
    sleep 1
    
    echo -e "${GREEN} Launching Booking Node 1...${NC}"
    open_terminal_linux "Booking Node 1 (Port 50051)" "python booking-node/main.py --config booking-node/config-node1.json"
    sleep 2
    
    echo -e "${GREEN} Launching Booking Node 2...${NC}"
    open_terminal_linux "Booking Node 2 (Port 50052)" "python booking-node/main.py --config booking-node/config-node2.json"
    sleep 2
    
    echo -e "${GREEN} Launching Booking Node 3...${NC}"
    open_terminal_linux "Booking Node 3 (Port 50053)" "python booking-node/main.py --config booking-node/config-node3.json"
    sleep 1

else
    echo -e "${YELLOW}  Unsupported OS: $OSTYPE${NC}"
    echo -e "${YELLOW}This script supports macOS and Linux${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN} All services launched in separate terminals!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Service Overview:${NC}"
echo -e "   Auth Service:      Port 8000"
echo -e "   Payment Service:   Port 6000"
echo -e "   Chatbot Service:   Port 9000"
echo -e "   Booking Node 1:    Port 50051"
echo -e "   Booking Node 2:    Port 50052"
echo -e "   Booking Node 3:    Port 50053"
echo ""
echo -e "${YELLOW} Wait 15 seconds for Raft leader election to stabilize${NC}"
echo -e "${YELLOW}   Then run: python3 client/client-cli.py${NC}"
echo ""
echo -e "${YELLOW}To stop all services:${NC}"
echo -e "   ./stop_cluster.sh"
echo ""