#!/bin/bash

# Production deployment script for Condition Task List Trader
# This script handles complete deployment including database, monitoring, and security

set -e  # Exit on any error

# Configuration
PROJECT_NAME="condition-task-list-trader"
ENV_FILE_PATH=".env"
BACKUP_DIR="/tmp/${PROJECT_NAME}-backup-$(date +%Y%m%d-%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +%Y-%m-%d %H:%M:%S)] $1${NC}"
}

success() {
    echo -e "${GREEN}[✅] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[⚠️] $1${NC}"
}

error() {
    echo -e "${RED}[❌] $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker and Docker Compose
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if docker-compose.yml exists
    if [ ! -f "deployment/docker-compose.yml" ]; then
        error "docker-compose.yml not found in deployment directory"
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Create backup of existing data
backup_data() {
    log "Creating backup of existing data..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Backup database if exists
    if docker ps -q -f name=postgres &> /dev/null; then
        log "Backing up database..."
        docker exec postgres pg_dump -U postgres condition_task_list_trader > "$BACKUP_DIR/database.sql" && 
            success "Database backup completed" ||
            warning "Database backup failed (may not exist yet)"
    fi
    
    # Backup logs directory
    if [ -d "logs" ]; then
        cp -r logs "$BACKUP_DIR/"
    fi
    
    success "Backup completed: $BACKUP_DIR"
}

# Setup environment variables
setup_environment() {
    log "Setting up environment variables..."
    
    if [ ! -f "$ENV_FILE_PATH" ]; then
        warning "No .env file found, creating from template..."
        cp deployment/.env.example "$ENV_FILE_PATH"
        
        error "Please edit .env file with your actual credentials before continuing"
        exit 1
    fi
    
    # Generate secure secret key if not set
    if ! grep -q "SECRET_KEY=" "$ENV_FILE_PATH" || grep -q "your_32_character_secret" "$ENV_FILE_PATH"; then
        log "Generating secure secret key..."
        SECRET_KEY=$(openssl rand -hex 32)
        sed -i.bak "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE_PATH"
        rm "$ENV_FILE_PATH.bak"
        success "Generated secure secret key"
    fi
    
    success "Environment setup completed"
}

# Initialize database
init_database() {
    log "Initializing database..."
    
    # Start only database service first
    cd deployment
    docker-compose up -d postgres
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    for i in {1..30}; do
        if docker exec postgres pg_isready -U postgres &> /dev/null; then
            success "Database is ready"
            break
        fi
        sleep 2
    done
    
    # Run database initialization
    docker exec postgres psql -U postgres -d condition_task_list_trader -f /docker-entrypoint-initdb.d/init-db.sql
    
    cd ..
    success "Database initialization completed"
}

# Deploy application
deploy_application() {
    log "Deploying application services..."
    
    cd deployment
    
    # Build and start all services
    docker-compose up -d --build
    
    cd ..
    
    success "Application deployment completed"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Wait for services to start
    sleep 10
    
    # Check application health
    if curl -f http://localhost:8001/health &> /dev/null; then
        success "Application health check passed"
    else
        error "Application health check failed"
        docker-compose -f deployment/docker-compose.yml logs trading-app
        exit 1
    fi
    
    # Check database connection
    if docker exec postgres pg_isready -U postgres &> /dev/null; then
        success "Database connection verified"
    else
        error "Database connection failed"
        exit 1
    fi
    
    # Check monitoring services
    if curl -f http://localhost:9090/-/healthy &> /dev/null; then
        success "Prometheus monitoring is running"
    else
        warning "Prometheus monitoring not yet ready (may still be starting)"
    fi
    
    success "Deployment verification completed"
}

# Setup monitoring alerts
setup_monitoring() {
    log "Setting up monitoring and alerts..."
    
    # Wait a bit for services to settle
    sleep 30
    
    # Check if Grafana is accessible
    if curl -f http://localhost:3000/api/health &> /dev/null; then
        success "Grafana dashboard is accessible at http://localhost:3000"
        log "   Username: admin"
        log "   Password: Set from .env file (GRAFANA_PASSWORD)"
    else
        warning "Grafana may still be starting - check http://localhost:3000"
    fi
    
    success "Monitoring setup completed"
}

# Display deployment summary
show_summary() {
    log "Deployment Summary"
    echo "=================="
    success "✅ Application deployed successfully!"
    echo ""
    echo "Service URLs:"
    echo "  Health Checks:   http://localhost:8001/health"
    echo "  Metrics:         http://localhost:8000/metrics"
    echo "  Grafana:         http://localhost:3000"
    echo "  Prometheus:      http://localhost:9090"
    echo "  Kibana Logs:     http://localhost:5601"
    echo ""
    echo "Application Logs:"
    echo "  docker-compose -f deployment/docker-compose.yml logs -f trading-app"
    echo ""
    echo "Commands:"
    echo "  Stop:    docker-compose -f deployment/docker-compose.yml down"
    echo "  Restart: docker-compose -f deployment/docker-compose.yml restart"
    echo "  Scale:   docker-compose -f deployment/docker-compose.yml up --scale trading-app=3"
    echo ""
    echo "Backup Location: $BACKUP_DIR"
}

# Main deployment function
main() {
    log "Starting production deployment of $PROJECT_NAME"
    
    check_prerequisites
    backup_data
    setup_environment
    init_database
    deploy_application
    verify_deployment
    setup_monitoring
    show_summary
    
    success "🚀 Production deployment completed successfully!"
}

# Handle script interruption
trap 'warning "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"
