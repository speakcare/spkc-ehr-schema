#!/bin/bash
# This is a sample Bash script
# Load environment variables from .env file
export $(grep -v '^#' .env.ec2 | xargs)

# Execute SSH command
cmd="ssh -i $EC2_KEY_PAIR_FILE_PATH $EC2_USERNAME@$EC2_SERVER_NAME"

echo "Executing ssh command: $cmd"
eval "$cmd"