#!/bin/bash

# SubManager Cron Wrapper Script
# This script runs SubManager and sends desktop notifications

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="$SCRIPT_DIR/cron_execution.log"

# Get username - try from argument first, then auto-detect
USERNAME="$1"
ENABLE_NOTIFICATIONS="$2"

# If username not provided, auto-detect
if [ -z "$USERNAME" ]; then
    # Try to get username from various sources
    if [ -n "$USER" ]; then
        USERNAME="$USER"
    elif [ -n "$LOGNAME" ]; then
        USERNAME="$LOGNAME"
    else
        USERNAME=$(whoami)
    fi
    
    # If still no username, error out
    if [ -z "$USERNAME" ]; then
        echo "Error: Could not determine username" >> "$LOG_FILE"
        exit 1
    fi
    
    # Default notifications to true if not specified
    if [ -z "$ENABLE_NOTIFICATIONS" ]; then
        ENABLE_NOTIFICATIONS="true"
    fi
fi

# Log execution start
echo "========================================" >> "$LOG_FILE"
echo "Execution started at $(date)" >> "$LOG_FILE"
echo "User: $USERNAME" >> "$LOG_FILE"

# Get user ID
USER_ID=$(id -u "$USERNAME")

# Function to setup display environment
setup_display_env() {
    # Set up basic environment
    export XDG_RUNTIME_DIR="/run/user/$USER_ID"
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_ID/bus"
    
    # Try to detect display environment
    # For X11
    export DISPLAY=":0"
    
    # For Wayland - check for wayland socket
    for wayland_socket in /run/user/$USER_ID/wayland-*; do
        if [ -S "$wayland_socket" ]; then
            export WAYLAND_DISPLAY="$(basename "$wayland_socket")"
            break
        fi
    done
}

# Function to send notification
send_notification() {
    local title="$1"
    local message="$2"
    local urgency="$3"
    
    if [ "$ENABLE_NOTIFICATIONS" != "true" ]; then
        echo "Notifications disabled" >> "$LOG_FILE"
        return
    fi
    
    echo "Attempting to send notification..." >> "$LOG_FILE"
    setup_display_env
    
    # Log environment for debugging
    echo "Display env: DISPLAY=$DISPLAY, WAYLAND_DISPLAY=$WAYLAND_DISPLAY" >> "$LOG_FILE"
    echo "User: $USERNAME, UID: $USER_ID" >> "$LOG_FILE"
    
    # Try different notification methods
    if command -v notify-send &> /dev/null; then
        # For cron, we need to run as the user directly without su
        export DISPLAY="${DISPLAY:-:0}"
        export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_ID/bus"
        export XDG_RUNTIME_DIR="/run/user/$USER_ID"
        
        # Send notification directly
        /usr/bin/notify-send -u "$urgency" -i github "$title" "$message" 2>>"$LOG_FILE" || {
            echo "Failed to send notification with notify-send" >> "$LOG_FILE"
            # Try with sudo -u as fallback
            sudo -u "$USERNAME" DISPLAY="$DISPLAY" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" /usr/bin/notify-send -u "$urgency" -i github "$title" "$message" 2>>"$LOG_FILE" || echo "Failed with sudo too" >> "$LOG_FILE"
        }
    else
        echo "notify-send not found" >> "$LOG_FILE"
    fi
}

# Change to script directory
cd "$SCRIPT_DIR"

# Create temp file for output
TEMP_OUTPUT=$(mktemp)

# Run SubManager and capture output
echo "Running SubManager..." >> "$LOG_FILE"
python3 "$SCRIPT_DIR/main.py" 2>&1 | tee "$TEMP_OUTPUT" >> "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Parse output for statistics
if [ $EXIT_CODE -eq 0 ]; then
    # Extract statistics from output
    FOLLOWERS=$(grep "👥 Followers:" "$TEMP_OUTPUT" | grep -oE '[0-9]+' | head -1 || echo "0")
    FOLLOWING=$(grep "➡️  Following:" "$TEMP_OUTPUT" | grep -oE '[0-9]+' | head -1 || echo "0")
    MUTUAL=$(grep "🤝 Mutual:" "$TEMP_OUTPUT" | grep -oE '[0-9]+' | head -1 || echo "0")
    
    # Extract follow/unfollow counts from progress logs
    FOLLOWED_COUNT=$(grep "Successfully followed" "$TEMP_OUTPUT" | grep -oE 'Successfully followed [0-9]+/[0-9]+' | grep -oE '[0-9]+' | head -1 || echo "0")
    UNFOLLOWED_COUNT=$(grep "Successfully unfollowed" "$TEMP_OUTPUT" | grep -oE 'Successfully unfollowed [0-9]+/[0-9]+' | grep -oE '[0-9]+' | head -1 || echo "0")
    
    # If not found, try alternative format
    if [ "$FOLLOWED_COUNT" = "0" ]; then
        FOLLOWED_COUNT=$(grep "Progress:.*users followed" "$TEMP_OUTPUT" | tail -1 | grep -oE 'Progress: [0-9]+' | grep -oE '[0-9]+' || echo "0")
    fi
    if [ "$UNFOLLOWED_COUNT" = "0" ]; then
        UNFOLLOWED_COUNT=$(grep "Progress:.*users unfollowed" "$TEMP_OUTPUT" | tail -1 | grep -oE 'Progress: [0-9]+' | grep -oE '[0-9]+' || echo "0")
    fi
    
    # Check for users to follow/unfollow
    TO_FOLLOW=$(grep "Users to follow:" "$TEMP_OUTPUT" | grep -oE 'follow: [0-9]+' | grep -oE '[0-9]+' || echo "0")
    TO_UNFOLLOW=$(grep "Users to unfollow:" "$TEMP_OUTPUT" | grep -oE 'unfollow: [0-9]+' | grep -oE '[0-9]+' || echo "0")
    
    # Create notification message
    NOTIFICATION_TITLE="✅ SubManager Success"
    NOTIFICATION_MSG="📊 Stats:
Followers: $FOLLOWERS
Following: $FOLLOWING
Mutual: $MUTUAL

🔄 Changes:
Followed: +$FOLLOWED_COUNT users
Unfollowed: -$UNFOLLOWED_COUNT users"
    
    echo "Execution completed successfully" >> "$LOG_FILE"
    echo "Statistics: Followers=$FOLLOWERS, Following=$FOLLOWING, Followed=$FOLLOWED_COUNT, Unfollowed=$UNFOLLOWED_COUNT" >> "$LOG_FILE"
    
    send_notification "$NOTIFICATION_TITLE" "$NOTIFICATION_MSG" "normal"
else
    # Error occurred
    ERROR_MSG=$(tail -5 "$TEMP_OUTPUT" | head -4)
    
    NOTIFICATION_TITLE="❌ SubManager Error"
    NOTIFICATION_MSG="Failed to execute SubManager.
Check log: $LOG_FILE

Error:
$ERROR_MSG"
    
    echo "Execution failed with code $EXIT_CODE" >> "$LOG_FILE"
    
    send_notification "$NOTIFICATION_TITLE" "$NOTIFICATION_MSG" "critical"
fi

# Clean up
rm -f "$TEMP_OUTPUT"

echo "Execution ended at $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
