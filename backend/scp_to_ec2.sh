#!/bin/bash
# Load environment variables from .env file
export $(grep -v '^#' .env.ec2 | xargs)

# Check if source file is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <local_file_path> [remote_file_path]"
  exit 1
fi

# Define source and destination file paths
LOCAL_FILE=$1
REMOTE_FILE=${2:-"/home/$EC2_USERNAME/"}  # Default to home directory if no remote path is given

# Construct the SCP command
scp_cmd="scp -i $EC2_KEY_PAIR_FILE_PATH $LOCAL_FILE $EC2_USERNAME@$EC2_SERVER_NAME:$REMOTE_FILE"

echo "Executing SCP command: $scp_cmd"
eval "$scp_cmd"
