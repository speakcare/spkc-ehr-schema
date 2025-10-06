# user_handler.py

import json
import time
import boto3
import os, sys
import base64
import uuid
import logging
vendor_path = os.path.join(os.path.dirname(__file__), 'vendor')
sys.path.insert(0, vendor_path)   
from requests_toolbelt.multipart import decoder as multipart_decoder
from shared_config import get_nurses_for_facility
from audio_validator import validate_audio_comprehensive


# Initialize DynamoDB
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

def _sanitize_event_for_log(event: dict) -> dict:
    try:
        redacted = dict(event or {})
        body = redacted.get('body')
        if body:
            # If base64 string, truncate to first 50 bytes worth of chars
            if isinstance(body, str):
                redacted['body'] = body[:50] + '...<truncated>' if len(body) > 50 else body
            else:
                redacted['body'] = '<binary body>'
        return redacted
    except Exception:
        return {'message': 'failed to sanitize event for log'}

logger = logging.getLogger()
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received event: %s", _sanitize_event_for_log(event))
    
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
            return create_error_response(400, 'No recording file found in request', ['AUDIO_INVALID'])
        
        # Process user enrollment
        enrollment_success, enrollment_message, error_code = enroll_user(user_id, tenant, recording_data)
        if not enrollment_success:
            return create_error_response(400, enrollment_message, [error_code])
        
        # Get username from shared config
        nurses = get_nurses_for_facility("default")  # TODO: get actual facility
        username = f"user.{user_id}"  # Default fallback
        nurse_found = False
        for nurse in nurses:
            if nurse['userId'] == user_id:
                username = nurse['username']
                nurse_found = True
                break
        
        # Validate that userId exists in the system
        if not nurse_found:
            return create_error_response(400, f"User ID '{user_id}' not found in system", ['USER_ID_NOT_FOUND'])
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'ok',
                'message': 'User enrolled successfully',
                'userId': user_id,
                'username': username
            })
        }
        
    except Exception as e:
        error_msg = f'Unexpected error enrolling user: {str(e)}'
        logger.exception(error_msg)
        return create_error_response(500, error_msg)

def parse_multipart_form_data(event):
    """
    Robustly parse API Gateway multipart/form-data events and return raw bytes.
    """
    try:
        headers = event.get('headers', {}) or {}
        headers = {k.lower(): v for k, v in headers.items()}
        content_type = headers.get('content-type', '')
        body = event.get('body', '')

        if not body:
            return None

        if 'multipart/form-data' not in content_type:
            logger.warning("Expected multipart/form-data, got: %s", content_type)
            return None

        is_b64 = event.get('isBase64Encoded', False)
        raw_bytes = base64.b64decode(body) if is_b64 else (body.encode('utf-8') if isinstance(body, str) else body)

        try:
            multipart_data = multipart_decoder.MultipartDecoder(raw_bytes, content_type)
        except Exception as e:
            logger.exception("Multipart decoding failed: %s", e)
            return None

        for part in multipart_data.parts:
            content_disposition = part.headers.get(b'Content-Disposition', b'').decode('utf-8', errors='ignore')
            if 'name="recording"' not in content_disposition:
                continue
            filename = 'recording.wav'
            for token in content_disposition.split(';'):
                token = token.strip()
                if token.startswith('filename='):
                    filename = token.split('=', 1)[1].strip('"')
                    break
            content_type_hdr = part.headers.get(b'Content-Type', b'audio/wav').decode('utf-8', errors='ignore')
            return {
                'filename': filename,
                'content': part.content,  # bytes
                'content_type': content_type_hdr
            }
        return None
    except Exception as e:
        logger.exception("Error parsing multipart form data: %s", e)
        return None

def enroll_user(user_id, tenant, recording_data):
    """
    Enroll a user with voice recording.
    
    Returns:
        tuple: (success, message, error_code)
    """
    # TODO: Implement actual enrollment logic
    # This could involve:
    # 1. Processing the uploaded recording file (recording_data['content'])
    # 2. Creating voice embeddings using the recording
    # 3. Storing enrollment data in DynamoDB
    # 4. Calling external voice recognition services
    
    logger.info("Enrolling user %s for tenant %s", user_id, tenant)
    
    # Validate audio using shared validator    
    is_valid, validation_message, error_code = validate_audio_comprehensive(recording_data)
    if not is_valid:
        return False, validation_message, error_code
    
    try:
        size = len(recording_data['content']) if recording_data and recording_data.get('content') is not None else 0
    except Exception:
        size = 0
    logger.debug("Recording file: %s, size: %s bytes", recording_data.get('filename'), size)
    
    # TODO: Add voice quality validation here
    # This could check for:
    # - Background noise levels
    # - Speech clarity
    # - Minimum duration
    # - Voice recognition confidence
    
    # Placeholder - replace with actual implementation
    # Example of what you might do:
    # 1. Save recording to S3
    # 2. Process with voice recognition service
    # 3. Store embeddings in DynamoDB
    
    return True, "User enrolled successfully", ""

def create_error_response(status_code, message, error_codes=None):
    """
    Create standardized error response
    """
    error_body = {
        'message': message
    }
    
    if error_codes:
        error_body['errorCodes'] = error_codes
    
    return {
        'statusCode': status_code,
        'body': json.dumps(error_body)
    }
