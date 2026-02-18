#!/bin/bash

# Prime Bank Chatbot - Startup Script
# Automates the setup and running of all components

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$SCRIPT_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "${BLUE}➜${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check Python
check_python() {
    print_step "Checking Python installation..."
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3.9+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    print_success "Python $PYTHON_VERSION found"
}

# Check Ollama
check_ollama() {
    print_step "Checking Ollama service..."
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_success "Ollama is running"
        
        # Check if model exists
        if curl -s http://localhost:11434/api/tags | grep -q "qwen3-1.7b-q4"; then
            print_success "Qwen3-1.7B Q4 model found"
        else
            print_warning "Qwen3-1.7B Q4 model not found"
            echo "Run in another terminal: ollama pull qwen3-1.7b-q4"
        fi
    else
        print_error "Ollama is not running"
        echo "Start Ollama with: ollama serve"
        exit 1
    fi
}

# Setup virtual environment
setup_venv() {
    print_step "Setting up Python virtual environment..."
    
    if [ -d "$VENV_DIR" ]; then
        print_success "Virtual environment already exists"
    else
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    fi
    
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip --quiet
    print_success "Pip upgraded"
}

# Install dependencies
install_deps() {
    print_step "Installing dependencies..."
    cd "$BACKEND_DIR"
    pip install -r requirements.txt --quiet
    print_success "Dependencies installed"
}

# Start backend
start_backend() {
    print_step "Starting FastAPI backend..."
    
    source "$VENV_DIR/bin/activate"
    cd "$BACKEND_DIR"
    
    exec python3 app.py
}

# Start frontend server
start_frontend() {
    print_step "Starting frontend HTTP server..."
    
    cd "$FRONTEND_DIR"
    
    echo ""
    echo "🌐 Frontend available at:"
    echo "   → http://localhost:8001/index.html"
    echo ""
    
    python3 -m http.server 8001
}

# Main menu
show_menu() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Prime Bank Chatbot - Setup & Run         ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "1) Quick start (setup + run backend)"
    echo "2) Backend only (FastAPI server)"
    echo "3) Frontend only (HTTP server)"
    echo "4) Check system health"
    echo "5) View logs"
    echo "6) Exit"
    echo ""
    read -p "Select option (1-6): " choice
    
    case $choice in
        1) quick_start ;;
        2) 
            check_python
            check_ollama
            setup_venv
            install_deps
            start_backend
            ;;
        3)
            start_frontend
            ;;
        4)
            check_health
            ;;
        5)
            view_logs
            ;;
        6)
            print_success "Goodbye!"
            exit 0
            ;;
        *)
            print_error "Invalid option"
            show_menu
            ;;
    esac
}

# Quick start
quick_start() {
    check_python
    check_ollama
    
    setup_venv
    install_deps
    
    print_success "Setup complete!"
    echo ""
    echo "🚀 Ready to run the chatbot"
    echo ""
    echo "Next steps:"
    echo "  1. Ensure Ollama is running (ollama serve)"
    echo "  2. Run this script again and select 'Backend only'"
    echo "  3. Open http://localhost:8001/index.html in browser"
    echo ""
}

# Check health
check_health() {
    print_step "Checking system health..."
    
    echo ""
    echo "Checking Python..."
    python3 --version
    
    echo ""
    echo "Checking Ollama..."
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_success "Ollama is running"
    else
        print_error "Ollama is not running"
    fi
    
    echo ""
    echo "Checking backend API..."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        RESPONSE=$(curl -s http://localhost:8000/health)
        print_success "Backend is running"
        echo "$RESPONSE" | python3 -m json.tool
    else
        print_warning "Backend is not running (start with option 2)"
    fi
    
    echo ""
    show_menu
}

# View logs
view_logs() {
    LOG_FILE="$BACKEND_DIR/logs/chatbot.log"
    
    if [ -f "$LOG_FILE" ]; then
        print_step "Displaying logs..."
        tail -f "$LOG_FILE"
    else
        print_warning "No logs found yet"
        show_menu
    fi
}

# Main entry point
main() {
    # If running with argument, use it as command
    if [ $# -gt 0 ]; then
        case "$1" in
            backend)
                check_python
                check_ollama
                setup_venv
                install_deps
                start_backend
                ;;
            frontend)
                start_frontend
                ;;
            setup)
                check_python
                setup_venv
                install_deps
                print_success "Setup complete!"
                ;;
            health)
                check_health
                ;;
            *)
                print_error "Unknown command: $1"
                echo "Usage: $0 [backend|frontend|setup|health]"
                exit 1
                ;;
        esac
    else
        show_menu
    fi
}

# Run main
main "$@"
