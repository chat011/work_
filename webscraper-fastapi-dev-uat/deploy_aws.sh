#!/bin/bash

# AWS EC2 Deployment Script for AI-Powered Web Scraper API
# This script sets up the application on a fresh AWS EC2 instance
# Supports Ubuntu 20.04+ and Amazon Linux 2

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
APP_USER="scraper"
APP_DIR="/opt/ai-scraper"
SERVICE_NAME="ai-scraper"
PYTHON_VERSION="3.11"

echo -e "${PURPLE}🚀 AWS EC2 Deployment - AI-Powered Web Scraper API${NC}"
echo -e "${BLUE}📊 Setting up production environment...${NC}"
echo ""

# Detect OS
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
    else
        echo -e "${RED}❌ Cannot detect OS${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Detected OS: $OS $VERSION${NC}"
}

# Update system packages
update_system() {
    echo -e "${YELLOW}📦 Updating system packages...${NC}"
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        sudo apt-get update -y
        sudo apt-get upgrade -y
        sudo apt-get install -y software-properties-common curl wget git nginx supervisor
        
        # Install Python 3.11 if not available
        if ! command -v python3.11 &> /dev/null; then
            sudo add-apt-repository ppa:deadsnakes/ppa -y
            sudo apt-get update -y
            sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
        fi
        
        # Install additional dependencies
        sudo apt-get install -y build-essential libssl-dev libffi-dev libnss3-dev \
                               libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 \
                               libxdamage1 libxrandr2 libgbm1 libxss1 libasound2
                               
    elif [[ "$OS" == *"Amazon Linux"* ]] || [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        sudo yum update -y
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y curl wget git nginx supervisor
        
        # Install Python 3.11
        sudo yum install -y python3.11 python3.11-pip python3.11-devel
        
        # Install additional dependencies for Playwright
        sudo yum install -y alsa-lib-devel atk-devel cups-devel gtk3-devel \
                           libXcomposite-devel libXcursor-devel libXdamage-devel \
                           libXext-devel libXi-devel libXrandr-devel libXScrnSaver-devel \
                           libXtst-devel pango-devel xorg-x11-fonts-100dpi \
                           xorg-x11-fonts-75dpi xorg-x11-fonts-cyrillic \
                           xorg-x11-fonts-misc xorg-x11-fonts-Type1 xorg-x11-utils
    fi
    
    echo -e "${GREEN}✅ System packages updated${NC}"
}

# Create application user
create_app_user() {
    echo -e "${YELLOW}👤 Creating application user...${NC}"
    
    if ! id "$APP_USER" &>/dev/null; then
        sudo useradd -r -s /bin/bash -d $APP_DIR $APP_USER
        echo -e "${GREEN}✅ User $APP_USER created${NC}"
    else
        echo -e "${BLUE}ℹ️  User $APP_USER already exists${NC}"
    fi
}

# Setup application directory
setup_app_directory() {
    echo -e "${YELLOW}📁 Setting up application directory...${NC}"
    
    sudo mkdir -p $APP_DIR
    sudo chown $APP_USER:$APP_USER $APP_DIR
    
    # Copy application files (assuming script is run from project directory)
    sudo cp -r . $APP_DIR/
    sudo chown -R $APP_USER:$APP_USER $APP_DIR
    
    echo -e "${GREEN}✅ Application directory setup complete${NC}"
}

# Install Python dependencies
install_python_dependencies() {
    echo -e "${YELLOW}🐍 Installing Python dependencies...${NC}"
    
    sudo -u $APP_USER bash -c "
        cd $APP_DIR
        python3.11 -m venv venv_py311
        source venv_py311/bin/activate
        pip install --upgrade pip setuptools wheel
        pip install -r requirements.txt
        playwright install chromium --with-deps
    "
    
    echo -e "${GREEN}✅ Python dependencies installed${NC}"
}

# Create systemd service
create_systemd_service() {
    echo -e "${YELLOW}⚙️  Creating systemd service...${NC}"
    
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=AI-Powered Web Scraper API
After=network.target

[Service]
Type=exec
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv_py311/bin
Environment=ENVIRONMENT=production
Environment=HOST=127.0.0.1
Environment=PORT=8000
ExecStart=$APP_DIR/venv_py311/bin/gunicorn api:app --bind 127.0.0.1:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker --log-level info --access-logfile - --error-logfile - --preload --max-requests 1000 --max-requests-jitter 100 --timeout 300 --keep-alive 2
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME}
    
    echo -e "${GREEN}✅ Systemd service created${NC}"
}

# Configure Nginx
configure_nginx() {
    echo -e "${YELLOW}🌐 Configuring Nginx...${NC}"
    
    sudo tee /etc/nginx/sites-available/${SERVICE_NAME} > /dev/null << 'EOF'
# WebSocket upgrade map
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    server_name _;
    
    client_max_body_size 50M;
    
    # WebSocket specific location
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # WebSocket specific timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 86400s;  # 24 hours
        proxy_read_timeout 86400s;   # 24 hours
        proxy_buffering off;
    }

    # Main application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for upgrade requests
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        
        # Regular HTTP timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
    
    # Static files (if any)
    location /static/ {
        alias /opt/ai-scraper/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF

    # Enable the site
    sudo ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Test Nginx configuration
    sudo nginx -t
    sudo systemctl enable nginx
    sudo systemctl restart nginx
    
    echo -e "${GREEN}✅ Nginx configured${NC}"
}

# Setup firewall
setup_firewall() {
    echo -e "${YELLOW}🔥 Configuring firewall...${NC}"
    
    if command -v ufw &> /dev/null; then
        sudo ufw --force enable
        sudo ufw allow ssh
        sudo ufw allow 80
        sudo ufw allow 443
        echo -e "${GREEN}✅ UFW firewall configured${NC}"
    elif command -v firewall-cmd &> /dev/null; then
        sudo systemctl enable firewalld
        sudo systemctl start firewalld
        sudo firewall-cmd --permanent --add-service=ssh
        sudo firewall-cmd --permanent --add-service=http
        sudo firewall-cmd --permanent --add-service=https
        sudo firewall-cmd --reload
        echo -e "${GREEN}✅ Firewalld configured${NC}"
    else
        echo -e "${YELLOW}⚠️  No firewall found, skipping firewall configuration${NC}"
    fi
}

# Create environment file
create_env_file() {
    echo -e "${YELLOW}🔧 Creating environment file...${NC}"
    
    sudo -u $APP_USER tee $APP_DIR/.env > /dev/null << 'EOF'
# AI API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here

# Application Configuration
ENVIRONMENT=production
HOST=127.0.0.1
PORT=8000
WORKERS=4

# Logging
LOG_LEVEL=info

# Security (generate strong secrets for production)
SECRET_KEY=your_secret_key_here

# Database (if needed)
# DATABASE_URL=postgresql://user:password@localhost/dbname
EOF

    sudo chown $APP_USER:$APP_USER $APP_DIR/.env
    sudo chmod 600 $APP_DIR/.env
    
    echo -e "${GREEN}✅ Environment file created${NC}"
    echo -e "${YELLOW}⚠️  Please edit $APP_DIR/.env and add your API keys${NC}"
}

# Setup log rotation
setup_log_rotation() {
    echo -e "${YELLOW}📝 Setting up log rotation...${NC}"
    
    sudo tee /etc/logrotate.d/${SERVICE_NAME} > /dev/null << EOF
/var/log/${SERVICE_NAME}/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        systemctl reload ${SERVICE_NAME}
    endscript
}
EOF

    sudo mkdir -p /var/log/${SERVICE_NAME}
    sudo chown $APP_USER:$APP_USER /var/log/${SERVICE_NAME}
    
    echo -e "${GREEN}✅ Log rotation configured${NC}"
}

# Start services
start_services() {
    echo -e "${YELLOW}🚀 Starting services...${NC}"
    
    sudo systemctl start ${SERVICE_NAME}
    sudo systemctl start nginx
    
    # Wait for services to start
    sleep 5
    
    # Check service status
    if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
        echo -e "${GREEN}✅ AI Scraper service is running${NC}"
    else
        echo -e "${RED}❌ AI Scraper service failed to start${NC}"
        sudo systemctl status ${SERVICE_NAME}
    fi
    
    if sudo systemctl is-active --quiet nginx; then
        echo -e "${GREEN}✅ Nginx is running${NC}"
    else
        echo -e "${RED}❌ Nginx failed to start${NC}"
        sudo systemctl status nginx
    fi
}

# Health check
perform_health_check() {
    echo -e "${YELLOW}🏥 Performing health check...${NC}"
    
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s -f "http://localhost/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Health check passed${NC}"
            return 0
        fi
        
        echo -e "${YELLOW}⏳ Health check attempt $attempt/$max_attempts...${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ Health check failed${NC}"
    return 1
}

# Display deployment summary
display_summary() {
    echo ""
    echo -e "${PURPLE}🎉 Deployment Complete!${NC}"
    echo -e "${CYAN}===========================================${NC}"
    echo -e "${GREEN}✅ AI-Powered Web Scraper API deployed successfully${NC}"
    echo ""
    echo -e "${BLUE}📋 Deployment Summary:${NC}"
    echo -e "   Application Directory: $APP_DIR"
    echo -e "   Service User: $APP_USER"
    echo -e "   Service Name: $SERVICE_NAME"
    echo -e "   Python Version: $(python3.11 --version)"
    echo ""
    echo -e "${BLUE}🌐 Access URLs:${NC}"
    echo -e "   Web Interface: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/"
    echo -e "   API Documentation: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/docs"
    echo -e "   Health Check: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/health"
    echo ""
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo -e "   Start:   sudo systemctl start $SERVICE_NAME"
    echo -e "   Stop:    sudo systemctl stop $SERVICE_NAME"
    echo -e "   Restart: sudo systemctl restart $SERVICE_NAME"
    echo -e "   Status:  sudo systemctl status $SERVICE_NAME"
    echo -e "   Logs:    sudo journalctl -u $SERVICE_NAME -f"
    echo ""
    echo -e "${YELLOW}⚠️  Next Steps:${NC}"
    echo -e "   1. Edit $APP_DIR/.env and add your GEMINI_API_KEY"
    echo -e "   2. Restart the service: sudo systemctl restart $SERVICE_NAME"
    echo -e "   3. Configure SSL certificate (recommended for production)"
    echo -e "   4. Set up monitoring and backups"
    echo ""
}

# Main execution
main() {
    # Check if running as root or with sudo
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}❌ This script must be run as root or with sudo${NC}"
        exit 1
    fi
    
    detect_os
    update_system
    create_app_user
    setup_app_directory
    install_python_dependencies
    create_systemd_service
    configure_nginx
    setup_firewall
    create_env_file
    setup_log_rotation
    start_services
    
    if perform_health_check; then
        display_summary
    else
        echo -e "${RED}❌ Deployment completed but health check failed${NC}"
        echo -e "${YELLOW}Please check the logs: sudo journalctl -u $SERVICE_NAME -f${NC}"
        exit 1
    fi
}

# Execute main function
main "$@" 