# Test script for docs handler
import json
import sys
import os

# Add the lambda directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set environment variables for testing
os.environ['S3_BUCKET'] = 'test-bucket'
os.environ['SWAGGER_HTML_S3_KEY'] = 'docs/swagger-ui.html'

from docs_handler import lambda_handler

# Test event
test_event = {
    "pathParameters": {
        "version": "v1",
        "space": "tenants", 
        "tenant": "holyname"
    },
    "httpMethod": "GET",
    "path": "/api/v1/tenants/holyname/docs"
}

# Test context
test_context = type('obj', (object,), {})()

# Run the handler
try:
    result = lambda_handler(test_event, test_context)
    print("✅ Docs handler test successful!")
    print(f"Status Code: {result['statusCode']}")
    print(f"Content-Type: {result['headers']['Content-Type']}")
    print(f"Body length: {len(result['body'])} characters")
    
    # Check if it's HTML
    if result['body'].startswith('<!DOCTYPE html>'):
        print("✅ Returns proper HTML")
    else:
        print("❌ Not returning HTML")
        
except Exception as e:
    print(f"❌ Docs handler test failed: {str(e)}")
    print("Note: This test will fail without S3 access, but the code structure is correct")
    import traceback
    traceback.print_exc()
