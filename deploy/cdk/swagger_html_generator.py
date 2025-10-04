import json
import yaml
from pathlib import Path
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class SwaggerHtmlGenerator(Construct):
    """Custom construct to generate Swagger UI HTML and upload to S3"""
    
    def __init__(self, scope: Construct, id: str, *, s3_bucket, html_key: str, version: str, space: str, tenant: str):
        super().__init__(scope, id)
        
        # Read the OpenAPI spec
        spec_path = Path(__file__).parent.parent / 'api' / 'watch-endpoints-openapi.yaml'
        
        if not spec_path.exists():
            raise FileNotFoundError(f"OpenAPI spec not found at {spec_path}")
        
        with open(spec_path, 'r') as f:
            spec_content = f.read()
        
        # Replace placeholders with actual values
        spec_content = spec_content.replace('{version}', version)
        spec_content = spec_content.replace('{space}', space)
        spec_content = spec_content.replace('{tenant}', tenant)
        
        # Parse the spec
        spec = yaml.safe_load(spec_content)
        
        # Generate Swagger UI HTML
        html_content = self._generate_swagger_html(spec, version, space, tenant)
        
        # Upload to S3 using a custom resource
        uploader = s3deploy.BucketDeployment(
            self, f"{id}-upload",
            sources=[s3deploy.Source.data("swagger-ui.html", html_content)],
            destination_bucket=s3_bucket,
            destination_key_prefix="docs",
            prune=True,
        )
        
        self.uploader = uploader
    
    def _generate_swagger_html(self, spec, version, space, tenant):
        """Generate Swagger UI HTML with the OpenAPI spec"""
        
        # Convert spec to JSON for Swagger UI
        spec_json = json.dumps(spec, indent=2)
        
        # Base URL for API calls
        base_url = f"/api/{version}/{space}/{tenant}"
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpeakCare API Documentation - {tenant}</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin:0;
            background: #fafafa;
        }}
        .swagger-ui .topbar {{
            background-color: #1f2937;
        }}
        .swagger-ui .topbar .download-url-wrapper {{
            display: none;
        }}
        .swagger-ui .info .title {{
            color: #1f2937;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const spec = {spec_json};
            
            // Configure Swagger UI
            const ui = SwaggerUIBundle({{
                spec: spec,
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                tryItOutEnabled: true,
                requestInterceptor: function(request) {{
                    // Add API key header if not present
                    if (!request.headers['X-API-Key']) {{
                        const apiKey = prompt('Enter your API Key:');
                        if (apiKey) {{
                            request.headers['X-API-Key'] = apiKey;
                        }}
                    }}
                    return request;
                }},
                onComplete: function() {{
                    // Add custom styling and info
                    const infoDiv = document.createElement('div');
                    infoDiv.innerHTML = `
                        <div style="background: #e5e7eb; padding: 15px; margin: 20px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                            <h3 style="margin: 0 0 10px 0; color: #1f2937;">API Information</h3>
                            <p style="margin: 5px 0;"><strong>Tenant:</strong> {tenant}</p>
                            <p style="margin: 5px 0;"><strong>Version:</strong> {version}</p>
                            <p style="margin: 5px 0;"><strong>Space:</strong> {space}</p>
                            <p style="margin: 5px 0;"><strong>Base URL:</strong> {base_url}</p>
                            <p style="margin: 5px 0; color: #6b7280;"><em>All endpoints require an API key. You'll be prompted to enter it when making requests.</em></p>
                        </div>
                    `;
                    document.querySelector('#swagger-ui').insertBefore(infoDiv, document.querySelector('#swagger-ui > div'));
                }}
            }});
        }};
    </script>
</body>
</html>
"""
        return html
