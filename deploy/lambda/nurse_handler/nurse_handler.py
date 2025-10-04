# nurse_handler.py

import json
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
        nurses = get_nurses_for_facility(facility_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps(nurses)
        }
        
    except Exception as e:
        error_msg = f'Unexpected error getting nurses: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def get_nurses_for_facility(facility_id):
    """
    Get list of nurses for a given facility.
    This is a placeholder implementation - you'll need to implement
    the actual logic based on your data source (DynamoDB, RDS, etc.)
    """
    # TODO: Implement actual nurse retrieval logic
    # This could query a nurses table, call an external API, etc.
    
    # Placeholder response - replace with actual implementation
    return [
        {
            "userId": "nurse001",
            "firstName": "Jane",
            "lastName": "Smith",
            "nickname": "Jane"
        },
        {
            "userId": "nurse002", 
            "firstName": "Rebecca",
            "lastName": "Jones",
            "nickname": "Becca"
        },
        {
            "userId": "nurse003", 
            "firstName": "Taylor",
            "lastName": "Swift",
            "nickname": "Tay"
        },
        {
            "userId": "nurse004", 
            "firstName": "Olivia",
            "lastName": "Rodrigo",
            "nickname": "Olivia"
        },
        {
            "userId": "nurse005", 
            "firstName": "Ariana",
            "lastName": "Grande",
            "nickname": "Ariana"
        }

    ]

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
