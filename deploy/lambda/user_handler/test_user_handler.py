#!/usr/bin/env python3
import os
import sys
import argparse
import base64
import json

# Allow importing the handler in this folder
sys.path.append(os.path.dirname(__file__))

from requests_toolbelt import MultipartEncoder
from user_handler import lambda_handler


def build_multipart_event(file_path: str, tenant: str, user_id: str):
    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    encoder = MultipartEncoder(
        fields={
            'recording': (os.path.basename(file_path), file_bytes, 'application/octet-stream'),
        }
    )

    body_bytes = encoder.to_string()
    event = {
        'resource': '/api/{version}/{space}/{tenant}/users/actions/enroll/{userId}',
        'path': f'/api/v1/sandboxes/{tenant}/users/actions/enroll/{user_id}',
        'httpMethod': 'POST',
        'headers': {
            'content-type': encoder.content_type,
        },
        'multiValueHeaders': {},
        'queryStringParameters': {},
        'multiValueQueryStringParameters': {},
        'pathParameters': {
            'version': 'v1',
            'space': 'sandboxes',
            'tenant': tenant,
            'userId': user_id,
        },
        'stageVariables': {},
        'requestContext': {},
        'body': base64.b64encode(body_bytes).decode('utf-8'),
        'isBase64Encoded': True,
    }
    return event


def main():
    parser = argparse.ArgumentParser(description='Local test for user_handler enrollment (multipart).')
    parser.add_argument('--file', required=True, help='Path to audio file to upload')
    parser.add_argument('--tenant', default=os.environ.get('CUSTOMER_NAME', 'orif'), help='Tenant name')
    parser.add_argument('--user-id', required=True, help='User ID path parameter')
    args = parser.parse_args()

    event = build_multipart_event(args.file, args.tenant, args.user_id)
    resp = lambda_handler(event, None)
    print('Status Code:', resp.get('statusCode'))
    try:
        print('Body:', json.dumps(json.loads(resp.get('body', '{}')), ensure_ascii=False, indent=4))
    except Exception:
        print('Body:', resp.get('body'))


if __name__ == '__main__':
    main()


