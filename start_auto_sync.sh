#!/bin/bash

# Auto-sync startup script for GitHub synchronization
# Runs in background and continuously pushes changes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_SYNC_SCRIPT="${SCRIPT_DIR}/auto_sync.py"
PID_FILE="${SCRIPT_DIR}/.auto_sync.pid"
LOG_FILE="${SCRIPT_DIR}/auto_sync_background.log"

# Function to stop existing auto-sync
stop_auto_sync() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping existing auto-sync process (PID: $PID)"
            kill "$PID"
            sleep 2
            # Force kill if still running
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID"
            fi
        fi
        rm -f "$PID_FILE"
    fi
}

# Function to start auto-sync
start_auto_sync() {
    echo "Starting auto-sync in background..."
    
    # Stop any existing process
    stop_auto_sync
    
    # Start new process
    nohup python3 "$AUTO_SYNC_SCRIPT" --continuous --interval 10 > "$LOG_FILE" 2>&1 &
    PID=$!
    
    # Save PID
    echo "$PID" > "$PID_FILE"
    
    echo "✅ Auto-sync started (PID: $PID)"
    echo "📋 Log file: $LOG_FILE"
    echo "🔄 Checking status: tail -f $LOG_FILE"
}

# Function to check status
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ Auto-sync is running (PID: $PID)"
            echo "📋 Recent logs:"
            tail -5 "$LOG_FILE"
        else
            echo "❌ Auto-sync process not found (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ Auto-sync is not running"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "📋 Auto-sync logs:"
        echo "=================="
        tail -20 "$LOG_FILE"
    else
        echo "❌ No log file found"
    fi
}

# Function to try immediate sync
sync_now() {
    echo "🔄 Attempting immediate sync..."
    python3 "$AUTO_SYNC_SCRIPT" --once
    if [ $? -eq 0 ]; then
        echo "✅ Sync completed successfully"
    else
        echo "❌ Sync failed - check logs for details"
    fi
}

# Main menu
case "${1:-start}" in
    start)
        start_auto_sync
        ;;
    stop)
        stop_auto_sync
        echo "🛑 Auto-sync stopped"
        ;;
    restart)
        stop_auto_sync
        sleep 1
        start_auto_sync
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    sync)
        sync_now
        ;;
    help|--help|-h)
        echo "Usage: $0 {start|stop|restart|status|logs|sync|help}"
        echo ""
        echo "Commands:"
        echo "  start   - Start auto-sync in background"
        echo "  stop    - Stop auto-sync"
        echo "  restart - Restart auto-sync"
        echo "  status  - Check if auto-sync is running"
        echo "  logs    - Show recent log entries"
        echo "  sync    - Try immediate sync once"
        echo "  help    - Show this help"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
