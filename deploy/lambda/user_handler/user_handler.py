# user_handler.py

import json
import time
import boto3
import os
import base64
import uuid

# Initialize DynamoDB
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

def lambda_handler(event, context):
    print(f"Received event: {event}")
    
    try:
        # Parse path parameters to extract tenant and userId
        path_params = event.get('pathParameters', {})
        tenant = path_params.get('tenant')
        user_id = path_params.get('userId')
        
        if not tenant:
            return create_error_response(400, 'Missing tenant in path')
        
        if not user_id:
            return create_error_response(400, 'Missing userId in path')
        
        # Validate tenant matches customer
        if tenant != customer:
            return create_error_response(400, 'Invalid tenant')
        
        # Parse multipart form data for recording file
        recording_data = parse_multipart_form_data(event)
        
        if not recording_data:
            return create_error_response(400, 'No recording file found in request')
        
        # Process user enrollment
        result = enroll_user(user_id, tenant, recording_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'ok',
                'message': 'User enrolled successfully',
                'userId': user_id,
                'username': f"user.{user_id}"  # Generate username from userId
            })
        }
        
    except Exception as e:
        error_msg = f'Unexpected error enrolling user: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def parse_multipart_form_data(event):
    """
    Parse multipart/form-data from API Gateway event.
    This is a simplified implementation - in production you might want to use
    a proper multipart parser library.
    """
    try:
        # Get the content type and body
        content_type = event.get('headers', {}).get('content-type', '')
        body = event.get('body', '')
        
        if not body:
            return None
        
        # Check if it's multipart/form-data
        if 'multipart/form-data' not in content_type:
            print(f"Expected multipart/form-data, got: {content_type}")
            return None
        
        # For API Gateway, the body might be base64 encoded
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('utf-8')
        
        # Simple multipart parsing (this is basic - consider using a proper library)
        # Look for the recording file in the multipart data
        if 'filename=' in body and 'recording' in body.lower():
            # Extract the file content (simplified)
            # In a real implementation, you'd use a proper multipart parser
            return {
                'filename': 'recording.wav',  # Extract actual filename
                'content': body,  # This would be the actual file content
                'content_type': 'audio/wav'  # Extract actual content type
            }
        
        return None
        
    except Exception as e:
        print(f"Error parsing multipart form data: {str(e)}")
        return None

def enroll_user(user_id, tenant, recording_data):
    """
    Enroll a user with voice recording.
    This is a placeholder implementation - you'll need to implement
    the actual enrollment logic based on your requirements.
    """
    # TODO: Implement actual enrollment logic
    # This could involve:
    # 1. Processing the uploaded recording file (recording_data['content'])
    # 2. Creating voice embeddings using the recording
    # 3. Storing enrollment data in DynamoDB
    # 4. Calling external voice recognition services
    
    print(f"Enrolling user {user_id} for tenant {tenant}")
    print(f"Recording file: {recording_data['filename']}, size: {len(recording_data['content'])} bytes")
    
    # Placeholder - replace with actual implementation
    # Example of what you might do:
    # 1. Save recording to S3
    # 2. Process with voice recognition service
    # 3. Store embeddings in DynamoDB
    
    return {
        'userId': user_id,
        'status': 'enrolled',
        'timestamp': int(time.time()),
        'recordingProcessed': True
    }

def create_error_response(status_code, message):
    """
    Create standardized error response
    """
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'error': message
        })
    }
