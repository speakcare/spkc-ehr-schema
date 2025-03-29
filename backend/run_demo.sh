#!/bin/bash

# Load .env file and extract APP_PORT
# Export ENV_FILE environment variable
export ENV_FILE="./.env.demo"

if [ -f $ENV_FILE ]; then
  export $(grep -v '^#' $ENV_FILE | grep -E '^[A-Za-z_][A-Za-z0-9_]*=.*' | xargs)
fi

# Set default log level to 'info'
LOG_LEVEL="info"
TIMEOUT=60

# Check if the log level override is passed
while [[ "$#" -gt 0 ]]; do
    case $1 in
        ---log-level) LOG_LEVEL="$2"; shift ;;
        ---timeout) TIMEOUT="$2"; shift ;;
    esac
    shift
done

# Make sure APP_PORT is set, otherwise default to 3000
PORT="${APP_PORT:-3000}"



# create the database 
python3 speakcare_db_create.py

# Initialize the vocoder model before starting workers

# Run Gunicorn with the specified port and log level
gunicorn -b localhost:$PORT -w 4 --access-logfile - --log-level $LOG_LEVEL --reload --timeout $TIMEOUT speakcare_demo_backend:app
