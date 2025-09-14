#!/bin/bash

# SubManager Cron Setup Script
# This script sets up automatic execution of SubManager with desktop notifications

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     SubManager Cron Setup Wizard      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run this script as root${NC}"
   exit 1
fi

# Get current username
CURRENT_USER=$(whoami)
echo -e "${GREEN}Setting up cron for user:${NC} $CURRENT_USER"

# Choose schedule
echo
echo -e "${YELLOW}Choose execution schedule:${NC}"
echo "1) Every hour"
echo "2) Every 2 hours"
echo "3) Every 4 hours"
echo "4) Every 6 hours"
echo "5) Every 12 hours"
echo "6) Once a day (at midnight)"
echo "7) Once a day (at noon)"
echo "8) Custom cron expression"
echo

read -p "Enter your choice (1-8): " choice

case $choice in
    1)
        CRON_SCHEDULE="0 * * * *"
        SCHEDULE_DESC="every hour"
        ;;
    2)
        CRON_SCHEDULE="0 */2 * * *"
        SCHEDULE_DESC="every 2 hours"
        ;;
    3)
        CRON_SCHEDULE="0 */4 * * *"
        SCHEDULE_DESC="every 4 hours"
        ;;
    4)
        CRON_SCHEDULE="0 */6 * * *"
        SCHEDULE_DESC="every 6 hours"
        ;;
    5)
        CRON_SCHEDULE="0 */12 * * *"
        SCHEDULE_DESC="every 12 hours"
        ;;
    6)
        CRON_SCHEDULE="0 0 * * *"
        SCHEDULE_DESC="daily at midnight"
        ;;
    7)
        CRON_SCHEDULE="0 12 * * *"
        SCHEDULE_DESC="daily at noon"
        ;;
    8)
        echo -e "${YELLOW}Enter custom cron expression:${NC}"
        echo "Format: MIN HOUR DAY MONTH WEEKDAY"
        echo "Example: 0 */3 * * * (every 3 hours)"
        read -p "Cron expression: " CRON_SCHEDULE
        SCHEDULE_DESC="custom schedule"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Ask about notifications
echo
read -p "Enable desktop notifications? (y/n): " enable_notif

if [[ "$enable_notif" =~ ^[Yy]$ ]]; then
    ENABLE_NOTIFICATIONS="true"
else
    ENABLE_NOTIFICATIONS="false"
fi

# Check if wrapper script exists
WRAPPER_SCRIPT="$SCRIPT_DIR/cron_wrapper.sh"
if [ ! -f "$WRAPPER_SCRIPT" ]; then
    echo -e "${RED}Error: cron_wrapper.sh not found!${NC}"
    echo "Please make sure cron_wrapper.sh exists in the same directory."
    exit 1
fi

# Make sure wrapper script is executable
chmod +x "$WRAPPER_SCRIPT"

# Create the cron job
echo -e "${GREEN}Setting up cron job...${NC}"

# Remove any existing SubManager cron jobs
(crontab -l 2>/dev/null | grep -v "SubManager" | grep -v "$WRAPPER_SCRIPT") | crontab - 2>/dev/null || true

# Add new cron job
# If notifications enabled, pass it as parameter, otherwise wrapper will auto-detect user
if [ "$ENABLE_NOTIFICATIONS" = "true" ]; then
    CRON_JOB="$CRON_SCHEDULE $WRAPPER_SCRIPT '' true # SubManager Auto-execution"
else
    CRON_JOB="$CRON_SCHEDULE $WRAPPER_SCRIPT '' false # SubManager Auto-execution"
fi

(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo
echo -e "${GREEN}✅ Cron job successfully installed!${NC}"
echo
echo -e "${YELLOW}Configuration:${NC}"
echo "  Schedule: $SCHEDULE_DESC ($CRON_SCHEDULE)"
echo "  User: $CURRENT_USER"
echo "  Notifications: $ENABLE_NOTIFICATIONS"
echo "  Wrapper script: $WRAPPER_SCRIPT"
echo "  Log file: $SCRIPT_DIR/cron_execution.log"
echo
echo -e "${GREEN}Commands:${NC}"
echo "  View cron jobs:    crontab -l"
echo "  Edit cron jobs:    crontab -e"
echo "  Remove this job:   crontab -l | grep -v '$WRAPPER_SCRIPT' | crontab -"
echo "  View logs:         tail -f $SCRIPT_DIR/cron_execution.log"
echo
echo -e "${YELLOW}Note:${NC} Make sure you have 'notify-send' installed for notifications:"
echo "  sudo pacman -S libnotify"
echo
echo -e "${GREEN}Setup complete! SubManager will run $SCHEDULE_DESC.${NC}"
