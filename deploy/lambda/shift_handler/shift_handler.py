# shift_handler.py

import json
import time
import boto3
import os
import base64
from requests_toolbelt.multipart import decoder as multipart_decoder
from shift_start_processor import ShiftStartProcessor
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared.shared_config import get_allowed_shifts, get_allowed_corridors, find_nurse_by_name, get_nurses_for_facility

# Initialize DynamoDB
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

def _sanitize_event_for_log(event: dict) -> dict:
    try:
        sanitized = dict(event)
        body = sanitized.get('body')
        if body:
            # Replace potentially huge/base64 body with length summary and small preview
            preview = body[:100] + ('...' if isinstance(body, str) and len(body) > 100 else '')
            sanitized['body'] = f"<body len={len(body)} preview={preview!r}>"
        return sanitized
    except Exception:
        return {'message': 'unable to sanitize event for log'}


def lambda_handler(event, context):
    print(f"Received event: {_sanitize_event_for_log(event)}")
    
    try:
        # Parse path parameters to extract tenant
        path_params = event.get('pathParameters', {})
        tenant = path_params.get('tenant')
        
        if not tenant:
            return create_error_response(400, 'Missing tenant in path')
        
        # Validate tenant matches customer
        if tenant != customer:
            return create_error_response(400, 'Invalid tenant')
        
        # Determine operation based on path
        path = event.get("path", "")
        
        if "/shifts/actions/start" in path:
            return handle_start_shift(event, context, tenant)
        elif "/shifts/actions/end/" in path:
            return handle_end_shift(event, context, tenant)
        else:
            return create_error_response(400, 'Invalid shift operation')
        
    except Exception as e:
        error_msg = f'Unexpected error in shift handler: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def handle_start_shift(event, context, tenant):
    """Handle shift start operation"""
    try:
        # Parse query parameters to get facilityId
        query_params = event.get('queryStringParameters', {}) or {}
        facility_id = query_params.get('facilityId')
        
        if not facility_id:
            return create_error_response(400, 'Missing facilityId query parameter', ['AUDIO_INVALID'])
        
        # Parse multipart form data for recording file
        recording_data = parse_multipart_form_data(event)
        
        if not recording_data:
            return create_error_response(400, 'No recording file found in request', ['AUDIO_INVALID'])
        
        # Initialize audio processor
        audio_processor = ShiftStartProcessor()
        
        # Validate audio file
        is_valid, validation_message = audio_processor.validate_audio(recording_data['content'])
        if not is_valid:
            return create_error_response(400, validation_message, ['AUDIO_INVALID'])
        
        # Transcribe audio
        transcription_success, transcription_message, transcription_text = audio_processor.transcribe_audio(
            recording_data['content'], 
            recording_data.get('filename')
        )
        if not transcription_success:
            return create_error_response(400, transcription_message, ['TRANSCRIPTION_FAILED'])
        
        # Load allowed lists (TODO: replace with DB fetch)
        # Get allowed shifts and corridors from shared config
        allowed_shifts = get_allowed_shifts()
        allowed_corridors = get_allowed_corridors()
        
        # Get nurse names for matching
        nurses = get_nurses_for_facility("default")  # TODO: get actual facility
        nurse_names = [f"{nurse['firstName']} {nurse['lastName']}" for nurse in nurses]

        # Extract shift data from transcription
        extraction_success, extraction_message, shift_data = audio_processor.extract_shift_data(
            transcription_text,
            allowed_shifts,
            allowed_corridors,
            nurse_names
        )
        if not extraction_success:
            return create_error_response(400, extraction_message, ['EXTRACTION_FAILED'])
        
        # Validate nurse name and get user details
        if not shift_data.fullName:
            return create_error_response(400, "Nurse name is required", ['MISSING_NURSE_NAME'])
        
        # Find nurse by name
        nurse = find_nurse_by_name(shift_data.fullName)
        if not nurse:
            return create_error_response(400, f"Nurse '{shift_data.fullName}' not found in system", ['NURSE_NOT_FOUND'])
        
        # Use actual nurse data
        user_id = nurse['userId']
        username = nurse['username']
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': 'Shift started',
                'userId': user_id,
                'username': username,
                'extractedData': {
                    'fullName': shift_data.fullName,
                    'shift': shift_data.shift,
                    'corridor': shift_data.corridor
                }
            }, ensure_ascii=False, indent=4)
        }
        
    except Exception as e:
        error_msg = f'Error starting shift: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def handle_end_shift(event, context, tenant):
    """Handle shift end operation"""
    try:
        # Parse path parameters to extract userId
        path_params = event.get('pathParameters', {})
        user_id = path_params.get('userId')
        
        if not user_id:
            return create_error_response(400, 'Missing userId in path')
        
        # Process shift end
        result = end_shift(user_id, tenant)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': 'Shift ended successfully',
                'userId': user_id
            }, ensure_ascii=False, indent=4)
        }
        
    except Exception as e:
        error_msg = f'Error ending shift: {str(e)}'
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
        headers = event.get('headers', {}) or {}
        # Normalize header keys to lowercase for robustness
        headers = {k.lower(): v for k, v in headers.items()}
        content_type = headers.get('content-type', '')
        body = event.get('body', '')
        
        if not body:
            return None
        
        # Check if it's multipart/form-data
        if 'multipart/form-data' not in content_type:
            print(f"Expected multipart/form-data, got: {content_type}")
            return None
        
        # For API Gateway, the body might be base64 encoded
        is_b64 = event.get('isBase64Encoded', False)
        raw_bytes = base64.b64decode(body) if is_b64 else body.encode('utf-8')

        # Robust multipart parsing using requests-toolbelt
        if 'multipart/form-data' in content_type:
            try:
                multipart_data = multipart_decoder.MultipartDecoder(raw_bytes, content_type)
            except Exception as e:
                print(f"Multipart decoding failed: {e}")
                return None
            for part in multipart_data.parts:
                content_disposition = part.headers.get(b'Content-Disposition', b'').decode('utf-8', errors='ignore')
                if 'name="recording"' not in content_disposition:
                    continue
                # Extract filename
                filename = 'recording.wav'
                for token in content_disposition.split(';'):
                    token = token.strip()
                    if token.startswith('filename='):
                        filename = token.split('=', 1)[1].strip('"')
                        break
                content_type_hdr = part.headers.get(b'Content-Type', b'audio/wav').decode('utf-8', errors='ignore')
                return {
                    'filename': filename,
                    'content': part.content,
                    'content_type': content_type_hdr
                }
        
        return None
        
    except Exception as e:
        print(f"Error parsing multipart form data: {str(e)}")
        return None

def start_shift(tenant, facility_id, recording_data):
    """
    Start a shift by processing voice recording and identifying the user.
    This is a placeholder implementation - you'll need to implement
    the actual shift start logic based on your requirements.
    """
    # TODO: Implement actual shift start logic
    # This could involve:
    # 1. Processing the uploaded recording file (recording_data['content'])
    # 2. Voice recognition to identify the user
    # 3. Creating shift record in DynamoDB
    # 4. Returning the identified userId
    
    print(f"Starting shift for tenant {tenant}, facility {facility_id}")
    content = recording_data['content']
    preview = content[:100] if isinstance(content, (bytes, bytearray)) else bytes(str(content), 'utf-8')[:100]
    print(f"Recording file: {recording_data['filename']} | type: {recording_data.get('content_type')} | size: {len(content)} bytes | preview(100): {preview!r}")
    
    # Placeholder - replace with actual implementation
    # In reality, this would process the voice recording and return the identified userId
    # Example of what you might do:
    # 1. Save recording to S3
    # 2. Process with voice recognition service
    # 3. Match against enrolled users
    # 4. Create shift record in DynamoDB
    
    return {
        'userId': 'nurse001',  # This should come from voice recognition
        'startTime': int(time.time()),
        'facilityId': facility_id
    }

def end_shift(user_id, tenant):
    """
    End a shift for the specified user ID.
    This is a placeholder implementation - you'll need to implement
    the actual shift end logic based on your requirements.
    """
    # TODO: Implement actual shift end logic
    # This could involve:
    # 1. Finding the active shift by userId
    # 2. Updating the shift record with end time
    # 3. Calculating shift duration
    # 4. Generating shift summary
    
    print(f"Ending shift for user {user_id} in tenant {tenant}")
    
    # Placeholder - replace with actual implementation
    return {
        'userId': user_id,
        'endTime': int(time.time())
    }

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
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(error_body, ensure_ascii=False, indent=4)
    }
