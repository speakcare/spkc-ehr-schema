# test_shift_handler.py
import sys
import os
import json
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
    os.environ['OPENAI_API_KEY'] = 'sk-test-key'
    os.environ['OPENAI_STT_MODEL'] = 'whisper-1'
    os.environ['OPENAI_MODEL'] = 'gpt-4.1-nano-2025-04-14'
    os.environ['OPENAI_TEMPERATURE'] = '0.2'
    os.environ['OPENAI_MAX_COMPLETION_TOKENS'] = '4096'
    os.environ['MAX_AUDIO_SIZE_BYTES'] = '102400'

from shift_handler import lambda_handler

# Test event for start shift
test_event = {
    "pathParameters": {
        "version": "v1",
        "space": "sandboxes", 
        "tenant": "orif"
    },
    "queryStringParameters": {
        "facilityId": "123"
    },
    "httpMethod": "POST",
    "path": "/api/v1/sandboxes/orif/shifts/actions/start",
    "headers": {
        "content-type": "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW"
    },
    "body": """------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="recording"; filename="test.wav"
Content-Type: audio/wav

[fake audio data]
------WebKitFormBoundary7MA4YWxkTrZu0gW--""",
    "isBase64Encoded": False
}

# Test event for end shift
test_event_end = {
    "pathParameters": {
        "version": "v1",
        "space": "sandboxes", 
        "tenant": "orif",
        "shiftId": "shift_1234567890"
    },
    "httpMethod": "POST",
    "path": "/api/v1/sandboxes/orif/shifts/actions/end/shift_1234567890"
}

# Test context
test_context = type('Context', (), {
    'function_name': 'test-shift-handler',
    'function_version': '$LATEST',
    'invoked_function_arn': 'arn:aws:lambda:us-east-1:123456789012:function:test-shift-handler',
    'memory_limit_in_mb': '128',
    'remaining_time_in_millis': lambda: 30000,
    'log_group_name': '/aws/lambda/test-shift-handler',
    'log_stream_name': '2023/01/01/[$LATEST]test',
    'aws_request_id': 'test-request-id'
})()

if __name__ == "__main__":
    print("Testing shift handler...")
    try:
        response = lambda_handler(test_event, test_context)
        print("✅ Shift handler test successful!")
        print(f"Status Code: {response['statusCode']}")
        print(f"Body: {response['body']}")
    except Exception as e:
        print(f"❌ Shift handler test failed: {str(e)}")
        import traceback
        traceback.print_exc()
