# 🚀 AI-Powered Web Scraper - Deployment Guide

This guide covers deployment options for the AI-Powered Web Scraper API, supporting Python 3.11+ with enhanced production features.

## 📋 Prerequisites

- **Python 3.11+** (recommended for best performance)
- **Git** for version control
- **curl** for health checks
- **Internet connection** for dependency installation

### Required API Keys
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)

## 🏠 Local Development Setup

### Quick Start
```bash
# Clone the repository
git clone <your-repo-url>
cd ai-scraper/backend

# Make scripts executable
chmod +x start_api.sh

# Start the application
./start_api.sh
```

### Manual Setup
```bash
# Create virtual environment
python3.11 -m venv venv_py311
source venv_py311/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium --with-deps

# Create environment file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the server
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## ☁️ AWS EC2 Deployment

### Automated Deployment
```bash
# On your local machine
scp -r . ubuntu@your-ec2-instance:/tmp/ai-scraper

# SSH to your EC2 instance
ssh ubuntu@your-ec2-instance

# Run deployment script
cd /tmp/ai-scraper
sudo chmod +x deploy_aws.sh
sudo ./deploy_aws.sh
```

### Manual AWS Setup

#### 1. Launch EC2 Instance
- **Instance Type**: t3.medium or larger (for AI processing)
- **OS**: Ubuntu 20.04+ or Amazon Linux 2
- **Security Group**: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- **Storage**: 20GB+ SSD

#### 2. Connect and Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev python3-pip -y

# Install system dependencies
sudo apt install nginx supervisor curl wget git build-essential -y

# Clone your repository
git clone <your-repo-url> /opt/ai-scraper
cd /opt/ai-scraper/backend

# Run deployment script
sudo ./deploy_aws.sh
```

#### 3. Post-Deployment Configuration
```bash
# Edit environment file
sudo nano /opt/ai-scraper/.env
# Add your GEMINI_API_KEY

# Restart service
sudo systemctl restart ai-scraper

# Check status
sudo systemctl status ai-scraper
```

### AWS Security Group Configuration
```
Type: SSH, Protocol: TCP, Port: 22, Source: Your IP
Type: HTTP, Protocol: TCP, Port: 80, Source: 0.0.0.0/0
Type: HTTPS, Protocol: TCP, Port: 443, Source: 0.0.0.0/0
```

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)
```yaml
# docker-compose.yml
version: '3.8'

services:
  ai-scraper:
    build:
      context: .
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl  # For SSL certificates
    depends_on:
      - ai-scraper
    restart: unless-stopped
```

### Build and Run
```bash
# Create environment file
echo "GEMINI_API_KEY=your_api_key_here" > .env

# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f ai-scraper

# Stop
docker-compose down
```

### Single Container
```bash
# Build image
docker build -f Dockerfile.prod -t ai-scraper:latest .

# Run container
docker run -d \
  --name ai-scraper \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_api_key_here \
  -e ENVIRONMENT=production \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  ai-scraper:latest
```

## 🌐 Production Considerations

### Environment Variables
```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=info
SECRET_KEY=your_secret_key_here
```

### Nginx Configuration
```nginx
# /etc/nginx/sites-available/ai-scraper
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }
}
```

### SSL Certificate (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal (crontab)
0 12 * * * /usr/bin/certbot renew --quiet
```

### Monitoring and Logging
```bash
# Check service status
sudo systemctl status ai-scraper

# View logs
sudo journalctl -u ai-scraper -f

# Monitor resource usage
htop
df -h
free -h

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 📊 Performance Optimization

### System Requirements
- **CPU**: 2+ cores (4+ recommended for AI processing)
- **RAM**: 4GB minimum (8GB+ recommended)
- **Storage**: 20GB+ SSD
- **Network**: Stable internet connection

### Scaling Options
1. **Vertical Scaling**: Increase instance size
2. **Horizontal Scaling**: Load balancer + multiple instances
3. **Container Orchestration**: Kubernetes/Docker Swarm

### Gunicorn Configuration
```bash
# For CPU-bound workloads
workers = (2 * CPU_cores) + 1

# For I/O-bound workloads (AI API calls)
workers = (4 * CPU_cores) + 1

# Example for 4-core machine
workers = 8
worker_class = uvicorn.workers.UvicornWorker
max_requests = 1000
max_requests_jitter = 100
timeout = 300
```

## 🔒 Security Best Practices

### Firewall Configuration
```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# Fail2ban (optional)
sudo apt install fail2ban -y
```

### Application Security
- Use strong API keys
- Enable HTTPS in production
- Regularly update dependencies
- Monitor for security vulnerabilities
- Use environment variables for secrets
- Implement rate limiting

### Regular Maintenance
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
pip install -r requirements.txt --upgrade

# Restart services
sudo systemctl restart ai-scraper nginx
```

## 🔧 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
sudo systemctl status ai-scraper

# Check logs
sudo journalctl -u ai-scraper -n 50

# Common fixes
sudo systemctl daemon-reload
sudo systemctl restart ai-scraper
```

#### Playwright Issues
```bash
# Reinstall browsers
playwright install chromium --with-deps

# Check dependencies
playwright install-deps
```

#### Permission Issues
```bash
# Fix ownership
sudo chown -R scraper:scraper /opt/ai-scraper

# Fix permissions
sudo chmod +x /opt/ai-scraper/start_api.sh
```

#### Memory Issues
```bash
# Check memory usage
free -h

# Reduce workers if needed
# Edit /etc/systemd/system/ai-scraper.service
sudo systemctl daemon-reload
sudo systemctl restart ai-scraper
```

### Health Checks
```bash
# API health check
curl http://localhost/health

# Detailed status
curl http://localhost/api

# Test scraping (replace with actual URL)
curl -X POST http://localhost/scrape/ai \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com"], "max_pages_per_url": 1}'
```

## 📞 Support

For issues and questions:
1. Check the logs: `sudo journalctl -u ai-scraper -f`
2. Verify environment variables are set correctly
3. Ensure all dependencies are installed
4. Check API documentation at `http://your-server/docs`

## 🔄 Updates and Maintenance

### Update Application
```bash
# Backup current version
sudo cp -r /opt/ai-scraper /opt/ai-scraper.backup

# Pull latest changes
cd /opt/ai-scraper
sudo git pull origin main

# Update dependencies
sudo -u scraper bash -c "
  source venv_py311/bin/activate
  pip install -r requirements.txt --upgrade
"

# Restart service
sudo systemctl restart ai-scraper
```

### Backup Strategy
```bash
# Create backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /backup/ai-scraper_$DATE.tar.gz /opt/ai-scraper
find /backup -name "ai-scraper_*.tar.gz" -mtime +7 -delete
```

---

## 🎉 Success!

Your AI-Powered Web Scraper API should now be running successfully. Access it at:
- **Web Interface**: `http://your-server/`
- **API Documentation**: `http://your-server/docs`
- **Health Check**: `http://your-server/health`

Happy scraping! 🕷️✨ 