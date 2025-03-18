#!/bin/bash
# This is a sample Bash script
# Load environment variables from .env file
export $(grep -v '^#' .env.ec2 | xargs)

 Define the transcribe command
transcribe_command="python3 transcribe.py"

# Define the commands to execute on the remote server
remote_commands="cd speakcare/speakcare-poc; source venv/bin/activate; 
                echo 'Remote executing: $transcribe_command'; $transcribe_command; echo 'Done. Exiting'; exit"
# Execute SSH command
cmd="ssh -i $EC2_KEY_PAIR_FILE_PATH $EC2_USERNAME@$EC2_SERVER_NAME \"$remote_commands\""

echo "Executing ssh command: $cmd"
eval "$cmd"