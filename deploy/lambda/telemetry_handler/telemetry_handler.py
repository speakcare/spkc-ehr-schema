# telemetry_handler.py

import json
import csv
import io
import time
import boto3
import os
from datetime import datetime
from collections import defaultdict

s3 = boto3.client('s3')
customer = os.environ['CUSTOMER_NAME']
bucket = os.environ['S3_BUCKET']
telemetry_dir = os.environ['S3_TELEMETRY_DIR']

def lambda_handler(event, context):
    print(f"Received event: {event}")
    
    try:
        # 1) Parse and validate request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        customer_id = body.get('customerId')
        if not customer_id:
            return create_error_response(400, 'customerId is required')
        
        if customer_id != customer:
            return create_error_response(400, 'Invalid customerId')
        
        username = body.get('username')
        if not username:
            return create_error_response(400, 'username is required')
        
        device_type = body.get('deviceType', 'unknown')
        device_unique_id = body.get('deviceUniqueId', 'unknown')
        telemetry_data = body.get('telemetryData', [])
        
        if not telemetry_data:
            return create_error_response(400, 'telemetryData is required and cannot be empty')
        
        # 2) Group telemetry data by sensorType
        sensor_groups = defaultdict(list)
        for data_point in telemetry_data:
            sensor_type = data_point.get('sensorType')
            if not sensor_type:
                print(f"Warning: Skipping data point without sensorType: {data_point}")
                continue
            sensor_groups[sensor_type].append(data_point)
        
        if not sensor_groups:
            return create_error_response(400, 'No valid telemetry data found (missing sensorType)')
        
        # 3) Generate CSV files for each sensor type
        current_time = int(time.time())
        timestamp_str = datetime.utcfromtimestamp(current_time).strftime('%Y%m%d_%H%M%S')
        
        uploaded_files = []
        
        for sensor_type, data_points in sensor_groups.items():
            try:
                # Generate CSV content
                csv_content = generate_csv(data_points)
                
                # Create filename with sensor type
                filename = f"{customer_id}-{username}-{device_type}-{device_unique_id}-{sensor_type}-{timestamp_str}.csv"
                
                # S3 key
                s3_key = f"{telemetry_dir}/{username}/{sensor_type}/{filename}"
                
                # Upload to S3
                s3.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=csv_content,
                    ContentType='text/csv'
                )
                
                uploaded_files.append({
                    'sensorType': sensor_type,
                    'filename': filename,
                    's3Key': s3_key,
                    'recordCount': len(data_points)
                })
                
                print(f"Successfully uploaded {len(data_points)} records for sensorType '{sensor_type}' to {s3_key}")
                
            except Exception as e:
                error_msg = f"Error processing sensorType '{sensor_type}': {str(e)}"
                print(error_msg)
                # Continue processing other sensor types even if one fails
                continue
        
        if not uploaded_files:
            return create_error_response(500, 'Failed to process any telemetry data')
        
        # 4) Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Telemetry data processed successfully',
                'uploadedFiles': uploaded_files,
                'totalFiles': len(uploaded_files),
                'timestamp': current_time
            })
        }
        
    except json.JSONDecodeError as e:
        return create_error_response(400, f'Invalid JSON in request body: {str(e)}')
    except Exception as e:
        error_msg = f'Unexpected error processing telemetry data: {str(e)}'
        print(error_msg)
        return create_error_response(500, error_msg)

def generate_csv(data_points):
    """
    Generate CSV content from telemetry data points
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['timestamp', 'sensorType', 'sensorMac', 'sensorId', 'sensorDeviceName', 'readings'])
    
    # Write data rows
    for point in data_points:
        # Format readings as dictionary string without spaces
        readings = point.get('readings', [])
        readings_str = format_readings(readings)
        
        writer.writerow([
            point.get('timestamp', ''),
            point.get('sensorType', ''),
            point.get('sensorMac', ''),
            point.get('sensorId', ''),
            point.get('sensorDeviceName', ''),
            readings_str
        ])
    
    return output.getvalue()

def format_readings(readings):
    """
    Format readings list as dictionary string with quoted keys
    Example: [{"RSSI": "-65", "TX_POWER": "0"}] -> "{'RSSI':-65,'TX_POWER':0}"
    """
    if not readings:
        return ""
    
    # Handle single reading object
    if isinstance(readings, dict):
        readings = [readings]
    
    # Format each reading object
    formatted_readings = []
    for reading in readings:
        if isinstance(reading, dict):
            # Create key:value pairs with quoted keys and no spaces
            pairs = [f"'{k}':{v}" for k, v in reading.items()]
            formatted_readings.append("{" + ",".join(pairs) + "}")
    
    return ",".join(formatted_readings)

def create_error_response(status_code, message):
    """
    Create standardized error response
    """
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'error': message,
            'timestamp': int(time.time())
        })
    }
