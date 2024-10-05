#!/bin/bash

# Load .env file and extract APP_PORT
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Set default log level to 'info'
LOG_LEVEL="info"

# Check if the log level override is passed
while [[ "$#" -gt 0 ]]; do
    case $1 in
        ---log-level) LOG_LEVEL="$2"; shift ;;
    esac
    shift
done

# Make sure APP_PORT is set, otherwise default to 3000
PORT="${APP_PORT:-3000}"

# Run Gunicorn with the specified port and log level
gunicorn -b localhost:$PORT -w 4 --access-logfile - --log-level $LOG_LEVEL --reload speakcare_backend:app
