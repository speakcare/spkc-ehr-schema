# nurse_handler.py

import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared.shared_config import get_nurses_for_facility as get_shared_nurses
import boto3
import os

# Initialize DynamoDB
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']

def lambda_handler(event, context):
    print(f"Received event: {event}")
    
    try:
        # Parse path parameters to extract tenant and facilityId
        path_params = event.get('pathParameters', {})
        query_params = event.get('queryStringParameters', {}) or {}
        
        tenant = path_params.get('tenant')
        facility_id = query_params.get('facilityId')
        
        if not tenant:
            return create_error_response(400, 'Missing tenant in path')
        
        if not facility_id:
            return create_error_response(400, 'Missing facilityId query parameter')
        
        # Validate tenant matches customer
        if tenant != customer:
            return create_error_response(400, 'Invalid tenant')
        
        # Get nurses for the facility
        nurses = get_shared_nurses(facility_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps(nurses)
        }
        
    except Exception as e:
        error_msg = f'Unexpected error getting nurses: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)


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
