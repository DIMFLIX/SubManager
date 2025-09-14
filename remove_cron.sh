#!/bin/bash

# SubManager Cron Removal Script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║   SubManager Cron Removal Script      ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════╝${NC}"
echo

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WRAPPER_SCRIPT="$SCRIPT_DIR/cron_wrapper.sh"

# Check current cron jobs
CURRENT_JOBS=$(crontab -l 2>/dev/null | grep "$WRAPPER_SCRIPT" | wc -l)

if [ "$CURRENT_JOBS" -eq 0 ]; then
    echo -e "${YELLOW}No SubManager cron jobs found.${NC}"
    exit 0
fi

echo -e "${GREEN}Found $CURRENT_JOBS SubManager cron job(s).${NC}"
echo
echo "Current SubManager cron job(s):"
crontab -l 2>/dev/null | grep "$WRAPPER_SCRIPT"
echo

read -p "Do you want to remove all SubManager cron jobs? (y/n): " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    # Remove SubManager cron jobs
    (crontab -l 2>/dev/null | grep -v "$WRAPPER_SCRIPT" | grep -v "SubManager") | crontab -
    
    echo -e "${GREEN}✅ SubManager cron jobs removed successfully!${NC}"
    
    # Ask about log file
    LOG_FILE="$SCRIPT_DIR/cron_execution.log"
    if [ -f "$LOG_FILE" ]; then
        echo
        read -p "Do you want to remove the log file? (y/n): " remove_log
        if [[ "$remove_log" =~ ^[Yy]$ ]]; then
            rm -f "$LOG_FILE"
            echo -e "${GREEN}Log file removed.${NC}"
        fi
    fi
    
    echo
    echo -e "${GREEN}Cleanup complete!${NC}"
else
    echo -e "${YELLOW}Operation cancelled.${NC}"
fi
