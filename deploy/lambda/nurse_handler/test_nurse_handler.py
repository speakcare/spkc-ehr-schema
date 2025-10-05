# test_nurse_handler.py
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add the lambda directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables from .env file
env_file_path = Path(__file__).parent.parent.parent / '.env'
if env_file_path.exists():
    load_dotenv(env_file_path)
    print(f"Loaded environment variables from {env_file_path}")
else:
    print(f"No .env file found at {env_file_path}")
    # Set default test values
    os.environ['CUSTOMER_NAME'] = 'orif'

from nurse_handler import lambda_handler

# Test event for getting nurses
test_event = {
    "pathParameters": {
        "version": "v1",
        "space": "sandboxes", 
        "tenant": "orif"
    },
    "queryStringParameters": {
        "facilityId": "123"
    },
    "httpMethod": "GET",
    "path": "/api/v1/sandboxes/orif/nurses"
}

# Test context
test_context = type('Context', (), {
    'function_name': 'test-nurse-handler',
    'function_version': '$LATEST',
    'invoked_function_arn': 'arn:aws:lambda:us-east-1:123456789012:function:test-nurse-handler',
    'memory_limit_in_mb': '128',
    'remaining_time_in_millis': lambda: 30000,
    'log_group_name': '/aws/lambda/test-nurse-handler',
    'log_stream_name': '2023/01/01/[$LATEST]test',
    'aws_request_id': 'test-request-id'
})()

if __name__ == "__main__":
    print("Testing nurse handler...")
    try:
        response = lambda_handler(test_event, test_context)
        print("✅ Nurse handler test successful!")
        print(f"Status Code: {response['statusCode']}")
        
        # Parse and validate the response
        nurses = eval(response['body'])  # Using eval since it's a string representation of list
        print(f"Number of nurses returned: {len(nurses)}")
        
        # Check if username field is present in each nurse
        for i, nurse in enumerate(nurses):
            if 'username' in nurse:
                print(f"✅ Nurse {i+1}: {nurse['firstName']} {nurse['lastName']} - Username: {nurse['username']}")
            else:
                print(f"❌ Nurse {i+1}: Missing username field")
                
    except Exception as e:
        print(f"❌ Nurse handler test failed: {str(e)}")
        import traceback
        traceback.print_exc()
