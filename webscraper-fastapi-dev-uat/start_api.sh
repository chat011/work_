#!/bin/bash

# AI-Powered Web Scraper API Startup Script
# Compatible with local development and AWS EC2 deployment
# Supports Python 3.11+ with enhanced production features

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8000"
DEFAULT_WORKERS="1"
PYTHON_VERSION="3.11"

# Environment detection
detect_environment() {
    if [[ -n "${AWS_EXECUTION_ENV}" ]] || [[ -n "${AWS_LAMBDA_FUNCTION_NAME}" ]] || [[ -n "${AWS_REGION}" ]] || [[ -f "/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json" ]]; then
        echo "aws"
    elif [[ -f "/.dockerenv" ]]; then
        echo "docker"
    elif [[ "${ENVIRONMENT}" == "production" ]] || [[ "${NODE_ENV}" == "production" ]]; then
        echo "production"
    else
        echo "development"
    fi
}

ENVIRONMENT=$(detect_environment)

# Header
echo -e "${PURPLE}🚀 AI-Powered Web Scraper API${NC}"
echo -e "${BLUE}📊 Features: Simple HTML Parser + AI Agent (Gemini 1.5 Flash)${NC}"
echo -e "${CYAN}🌐 Environment: ${ENVIRONMENT}${NC}"
echo ""

# Check Python version
check_python_version() {
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PYTHON_VER=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
        if [[ "$PYTHON_VER" < "3.11" ]]; then
            echo -e "${YELLOW}⚠️  Warning: Python $PYTHON_VER detected. Python 3.11+ recommended.${NC}"
        fi
    else
        echo -e "${RED}❌ Error: Python 3.11+ not found. Please install Python 3.11 or higher.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Python: $($PYTHON_CMD --version)${NC}"
}

# Setup virtual environment
setup_virtual_environment() {
    local venv_dir="venv_py311"
    
    if [[ "$ENVIRONMENT" == "development" ]]; then
        if [[ ! -d "$venv_dir" ]]; then
            echo -e "${YELLOW}🔧 Creating virtual environment...${NC}"
            $PYTHON_CMD -m venv $venv_dir
        fi
        
        echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
        source $venv_dir/bin/activate
        
        # Upgrade pip
        pip install --upgrade pip setuptools wheel
    else
        echo -e "${BLUE}🔧 Production environment detected, using system Python${NC}"
    fi
}

# Install dependencies
install_dependencies() {
    echo -e "${YELLOW}📦 Installing/updating dependencies...${NC}"
    
    # Install Python dependencies
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        echo -e "${GREEN}✅ Python dependencies installed${NC}"
    else
        echo -e "${RED}❌ requirements.txt not found${NC}"
        exit 1
    fi
    
    # Install Playwright browsers
    echo -e "${YELLOW}🎭 Setting up Playwright browsers...${NC}"
    if command -v playwright &> /dev/null; then
        playwright install chromium --with-deps 2>/dev/null || {
            echo -e "${YELLOW}⚠️  Playwright browser installation failed, continuing...${NC}"
        }
        echo -e "${GREEN}✅ Playwright setup complete${NC}"
    else
        echo -e "${YELLOW}⚠️  Playwright not found, skipping browser setup${NC}"
    fi
}

# Environment validation
validate_environment() {
    echo -e "${YELLOW}🔍 Validating environment...${NC}"
    
    # Check for required environment variables
    if [[ -z "${GEMINI_API_KEY}" ]] && [[ -z "${GOOGLE_API_KEY}" ]]; then
        echo -e "${YELLOW}⚠️  Warning: GEMINI_API_KEY not set. AI features will be disabled.${NC}"
        echo -e "${CYAN}   Get your API key from: https://makersuite.google.com/app/apikey${NC}"
    else
        echo -e "${GREEN}✅ AI API key configured${NC}"
    fi
    
    # Create necessary directories
    mkdir -p logs
    mkdir -p templates
    
    # Check if main API file exists
    if [[ ! -f "api.py" ]]; then
        echo -e "${RED}❌ Error: api.py not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Environment validation complete${NC}"
}

# Configure server settings based on environment
configure_server() {
    # Set defaults
    HOST=${HOST:-$DEFAULT_HOST}
    PORT=${PORT:-$DEFAULT_PORT}
    
    case "$ENVIRONMENT" in
        "aws"|"production")
            WORKERS=${WORKERS:-$(nproc)}
            RELOAD="--no-reload"
            LOG_LEVEL="info"
            ACCESS_LOG="--access-log"
            ;;
        "docker")
            WORKERS=${WORKERS:-2}
            RELOAD="--no-reload"
            LOG_LEVEL="info"
            ACCESS_LOG="--access-log"
            ;;
        *)
            WORKERS=${WORKERS:-1}
            RELOAD="--reload"
            LOG_LEVEL="debug"
            ACCESS_LOG=""
            ;;
    esac
    
    echo -e "${CYAN}🔧 Server Configuration:${NC}"
    echo -e "   Host: ${HOST}"
    echo -e "   Port: ${PORT}"
    echo -e "   Workers: ${WORKERS}"
    echo -e "   Environment: ${ENVIRONMENT}"
    echo -e "   Log Level: ${LOG_LEVEL}"
}

# Health check function
health_check() {
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}🏥 Performing health check...${NC}"
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s -f "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Health check passed${NC}"
            return 0
        fi
        
        echo -e "${YELLOW}⏳ Health check attempt $attempt/$max_attempts...${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ Health check failed after $max_attempts attempts${NC}"
    return 1
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    pkill -f "uvicorn api:app" 2>/dev/null || true
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start server function
start_server() {
    echo -e "${GREEN}🚀 Starting AI Scraper API Server...${NC}"
    echo -e "${CYAN}📖 API Documentation: http://${HOST}:${PORT}/docs${NC}"
    echo -e "${CYAN}🌐 Web Interface: http://${HOST}:${PORT}/${NC}"
    echo -e "${CYAN}❤️  Health Check: http://${HOST}:${PORT}/health${NC}"
    echo ""
    echo -e "${PURPLE}🤖 AI Agent Features:${NC}"
    echo -e "   • Intelligent page structure analysis"
    echo -e "   • Automatic pagination discovery"
    echo -e "   • Dynamic product extraction"
    echo -e "   • Adaptive to different website layouts"
    echo -e "   • Real-time WebSocket updates"
    echo ""
    
    if [[ "$ENVIRONMENT" == "production" ]] || [[ "$ENVIRONMENT" == "aws" ]]; then
        echo -e "${BLUE}🔥 Starting production server with Gunicorn...${NC}"
        exec gunicorn api:app \
            --bind "${HOST}:${PORT}" \
            --workers "${WORKERS}" \
            --worker-class uvicorn.workers.UvicornWorker \
            --log-level "${LOG_LEVEL}" \
            --access-logfile - \
            --error-logfile - \
            --preload \
            --max-requests 1000 \
            --max-requests-jitter 100 \
            --timeout 300 \
            --keep-alive 2 \
            --worker-tmp-dir /dev/shm 2>/dev/null || --worker-tmp-dir /tmp
    else
        echo -e "${BLUE}🔥 Starting development server with Uvicorn...${NC}"
        exec uvicorn api:app \
            --host "${HOST}" \
            --port "${PORT}" \
            --log-level "${LOG_LEVEL}" \
            ${RELOAD} \
            ${ACCESS_LOG}
    fi
}

# Main execution
main() {
    check_python_version
    setup_virtual_environment
    install_dependencies
    validate_environment
    configure_server
    
    # Start server in background for health check in production
    if [[ "$ENVIRONMENT" == "production" ]] || [[ "$ENVIRONMENT" == "aws" ]]; then
        start_server &
        SERVER_PID=$!
        
        # Wait a moment for server to start
        sleep 5
        
        # Perform health check
        if health_check; then
            echo -e "${GREEN}🎉 Server started successfully!${NC}"
            wait $SERVER_PID
        else
            echo -e "${RED}❌ Server failed to start properly${NC}"
            kill $SERVER_PID 2>/dev/null || true
            exit 1
        fi
    else
        start_server
    fi
}

# Execute main function
main "$@" 