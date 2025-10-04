# shift_handler.py

import json
import time
import boto3
import os
import base64
from audio_processor import AudioProcessor

# Initialize DynamoDB
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

def lambda_handler(event, context):
    print(f"Received event: {event}")
    
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
        audio_processor = AudioProcessor()
        
        # Validate audio file
        is_valid, validation_message = audio_processor.validate_audio(recording_data['content'])
        if not is_valid:
            return create_error_response(400, validation_message, ['AUDIO_INVALID'])
        
        # Transcribe audio
        transcription_success, transcription_message, transcription_text = audio_processor.transcribe_audio(recording_data['content'])
        if not transcription_success:
            return create_error_response(400, transcription_message, ['TRANSCRIPTION_FAILED'])
        
        # Extract shift data from transcription
        extraction_success, extraction_message, shift_data = audio_processor.extract_shift_data(transcription_text)
        if not extraction_success:
            return create_error_response(400, extraction_message, ['EXTRACTION_FAILED'])
        
        # Generate stub response
        shift_id = f"shift_{int(time.time())}"
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': 'Shift started',
                'userId': 'nurse001',  # Stub value
                'shiftId': shift_id,
                'extractedData': {
                    'fullName': shift_data.fullName,
                    'shift': shift_data.shift,
                    'corridor': shift_data.corridor
                }
            })
        }
        
    except Exception as e:
        error_msg = f'Error starting shift: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def handle_end_shift(event, context, tenant):
    """Handle shift end operation"""
    try:
        # Parse path parameters to extract shiftId
        path_params = event.get('pathParameters', {})
        shift_id = path_params.get('shiftId')
        
        if not shift_id:
            return create_error_response(400, 'Missing shiftId in path')
        
        # Process shift end
        result = end_shift(shift_id, tenant)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'message': 'Shift ended successfully',
                'shiftId': shift_id
            })
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
    print(f"Recording file: {recording_data['filename']}, size: {len(recording_data['content'])} bytes")
    
    # Placeholder - replace with actual implementation
    # In reality, this would process the voice recording and return the identified userId
    # Example of what you might do:
    # 1. Save recording to S3
    # 2. Process with voice recognition service
    # 3. Match against enrolled users
    # 4. Create shift record in DynamoDB
    
    return {
        'userId': 'nurse001',  # This should come from voice recognition
        'shiftId': f"shift_{int(time.time())}",
        'startTime': int(time.time()),
        'facilityId': facility_id
    }

def end_shift(shift_id, tenant):
    """
    End a shift for the specified shift ID.
    This is a placeholder implementation - you'll need to implement
    the actual shift end logic based on your requirements.
    """
    # TODO: Implement actual shift end logic
    # This could involve:
    # 1. Finding the shift by shiftId
    # 2. Updating the shift record with end time
    # 3. Calculating shift duration
    # 4. Generating shift summary
    
    print(f"Ending shift {shift_id} in tenant {tenant}")
    
    # Placeholder - replace with actual implementation
    return {
        'shiftId': shift_id,
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
        'body': json.dumps(error_body)
    }
