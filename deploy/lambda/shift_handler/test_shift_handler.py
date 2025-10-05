# test_shift_handler.py
import sys
import os
import json
import base64
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
    os.environ.setdefault('OPENAI_API_KEY', 'sk-test-key')
    os.environ.setdefault('OPENAI_STT_MODEL', 'whisper-1')
    os.environ.setdefault('OPENAI_MODEL', 'gpt-4.1-nano-2025-04-14')
    os.environ.setdefault('OPENAI_TEMPERATURE', '0.2')
    os.environ.setdefault('OPENAI_MAX_COMPLETION_TOKENS', '4096')
    os.environ.setdefault('MAX_SIGN_IN_AUDIO_SIZE_BYTES', '512000')  # 500KB for local tests

from shift_handler import lambda_handler


def guess_content_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    return {
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/m4a',
        '.webm': 'audio/webm',
        '.ogg': 'audio/ogg',
        '.flac': 'audio/flac',
    }.get(ext, 'application/octet-stream')


def build_multipart_body(field_name: str, filename: str, content_type: str, file_bytes: bytes, boundary: str) -> bytes:
    crlf = b"\r\n"
    lines = []
    lines.append(b"--" + boundary.encode('utf-8'))
    disposition = f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode('utf-8')
    lines.append(disposition)
    lines.append(f'Content-Type: {content_type}'.encode('utf-8'))
    lines.append(b"")  # empty line before file content
    lines.append(file_bytes)
    lines.append(b"--" + boundary.encode('utf-8') + b"--")
    return crlf.join(lines)


def make_start_event(file_path: str, tenant: str = 'orif', facility_id: str = '123'):
    boundary = '----LocalBoundaryForTesting'
    content_type = guess_content_type(file_path)
    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    multipart_bytes = build_multipart_body('recording', os.path.basename(file_path), content_type, file_bytes, boundary)
    body_b64 = base64.b64encode(multipart_bytes).decode('ascii')

    event = {
        "pathParameters": {
            "version": "v1",
            "space": "sandboxes",
            "tenant": tenant
        },
        "queryStringParameters": {
            "facilityId": facility_id
        },
        "httpMethod": "POST",
        "path": f"/api/v1/sandboxes/{tenant}/shifts/actions/start",
        "headers": {
            "content-type": f"multipart/form-data; boundary={boundary}"
        },
        "body": body_b64,
        "isBase64Encoded": True
    }
    return event


def make_end_event(user_id: str = 'nurse001', tenant: str = 'orif'):
    return {
        "pathParameters": {
            "version": "v1",
            "space": "sandboxes",
            "tenant": tenant,
            "userId": user_id
        },
        "httpMethod": "POST",
        "path": f"/api/v1/sandboxes/{tenant}/shifts/actions/end/{user_id}"
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
    import argparse
    parser = argparse.ArgumentParser(description='Local tester for shift_handler.lambda_handler')
    parser.add_argument('--file', '-f', required=True, help='Path to an audio file (wav/mp3/m4a/webm/ogg/flac)')
    parser.add_argument('--tenant', default='orif', help='Tenant name')
    parser.add_argument('--facility', default='123', help='Facility ID')
    parser.add_argument('--end-user', dest='end_user', default=None, help='If provided, call end shift for this userId instead of start')
    args = parser.parse_args()

    if args.end_user:
        event = make_end_event(args.end_user, args.tenant)
        print("Testing end shift...")
        response = lambda_handler(event, test_context)
        print(f"Status Code: {response['statusCode']}")
        print(f"Body: {response['body']}")
    else:
        if not os.path.isfile(args.file):
            print(f"File not found: {args.file}")
            sys.exit(1)
        event = make_start_event(args.file, args.tenant, args.facility)
        print("Testing start shift with file:", args.file)
        response = lambda_handler(event, test_context)
        print(f"Status Code: {response['statusCode']}")
        print(f"Body: {response['body']}")
