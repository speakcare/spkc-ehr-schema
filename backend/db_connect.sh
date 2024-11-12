#!/bin/bash

# Load .env file and extract APP_PORT
if [ -f .env ]; then
  export $(grep -v '^#' .env  | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | xargs)
fi


DB_FILE="db/speakcare.db"
PORT=8001


while [[ "$#" -gt 0 ]]; do
    case $1 in
        ---db) DB_FILE="$2"; shift ;;
        --port) PORT="$2"; shift ;;
    esac
    shift
done

# Create the command
CMD="datasette serve $DB_FILE --port $PORT"

# Echo the command
echo "Running command: $CMD"

# Run the command
eval $CMD

