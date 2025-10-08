# docs_handler.py

import json
import os
import boto3

def lambda_handler(event, context):
    print(f"Received event: {event}")
    
    try:
        # Parse path parameters to extract tenant, version, space
        path_params = event.get('pathParameters', {})
        tenant = path_params.get('tenant')
        version = path_params.get('version')
        space = path_params.get('space')
        
        if not all([tenant, version, space]):
            return create_error_response(400, 'Missing required path parameters')
        
        # Read the pre-generated Swagger UI HTML from S3
        s3_bucket = os.environ['S3_BUCKET']
        swagger_html_key = os.environ['SWAGGER_HTML_S3_KEY']
        
        s3_client = boto3.client('s3')
        try:
            response = s3_client.get_object(Bucket=s3_bucket, Key=swagger_html_key)
            html_content = response['Body'].read().decode('utf-8')
        except Exception as e:
            print(f"Error reading Swagger HTML from S3: {str(e)}")
            return create_error_response(500, 'Swagger UI not found in S3')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': html_content
        }
        
    except Exception as e:
        error_msg = f'Error serving Swagger UI: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def create_error_response(status_code, message):
    """Create standardized error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message
        })
    }
