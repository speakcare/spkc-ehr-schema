# Test script for SwaggerHtmlGenerator
import sys
import os
from pathlib import Path

# Add the cdk directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from swagger_html_generator import SwaggerHtmlGenerator

def test_html_generation():
    """Test just the HTML generation method without CDK constructs"""
    try:
        # Test HTML generation with mock spec
        mock_spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/{version}/{space}/{tenant}/nurses": {
                    "get": {
                        "summary": "List nurses",
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            }
        }
        
        # Create a generator instance just to access the method
        generator = SwaggerHtmlGenerator.__new__(SwaggerHtmlGenerator)
        
        html = generator._generate_swagger_html(mock_spec, "v1", "tenants", "holyname")
        
        print("✅ HTML generation works correctly")
        
        # Test key elements are present
        checks = [
            ("<!DOCTYPE html>", "HTML doctype"),
            ("SpeakCare API Documentation - holyname", "Title with tenant"),
            ("v1", "Version placeholder"),
            ("tenants", "Space placeholder"),
            ("holyname", "Tenant placeholder"),
            ("swagger-ui", "Swagger UI elements"),
            ("SwaggerUIBundle", "Swagger UI JavaScript")
        ]
        
        for check_text, description in checks:
            if check_text in html:
                print(f"✅ {description} found")
            else:
                print(f"❌ {description} missing")
                
        print(f"✅ Generated HTML length: {len(html)} characters")
        
    except Exception as e:
        print(f"❌ HTML generation test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_html_generation()
