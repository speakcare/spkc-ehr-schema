# recording_handler.py

import json
import uuid
import time
import boto3
import os

s3     = boto3.client('s3')
dynamo = boto3.resource('dynamodb')
customer = os.environ['CUSTOMER_NAME']
recordingDir = os.environ['S3_RECORDING_DIR']

def lambda_handler(event, context):
    # 1) Parse input
    body = json.loads(event['body'])
    customerId = body.get('customerId')
    if not customerId:
        return {
            'statusCode': 400,
            'body': json.dumps({'error':'customerId is required'})
        }
    if customerId != customer:
        return {
            'statusCode': 400,
            'body': json.dumps({'error':'Invalid customerId'})
        }
    
    recordingType = body.get('type')            # must be "enroll" or "session"
    if recordingType not in ('enroll','session'):
        return {
            'statusCode': 400,
            'body': json.dumps({'error':'Invalid type; must be "enroll" or "session"'})
        }

    fileName = body['fileName']            # e.g. "rec-20250422.flac"
    username  = body['username']

    # 2) Derive bucket, table, S3 key
    bucket     = f"speakcare-{customer}"
    if recordingType == 'enroll':
        prefix     = f"{recordingDir}/enrollments/{username}"
        tableName = f"{customer}-enrollments"
    else:
        prefix     = f"{recordingDir}/sessions/{username}"
        tableName = f"{customer}-sessions"

    key = f"{prefix}/{fileName}"

    # 3) Timestamps for TTL
    now       = int(time.time())
    expiresAt = now + 3600   # expire in 1 hour

    # 4) Write a pending_upload record
    recordingId = str(uuid.uuid4())
    table  = dynamo.Table(tableName)
    item = {
      'recordingId':      recordingId,
      'customerId':       customerId,
      'type':             recordingType,
      'username':         username,
      'deviceType':       body.get('deviceType','unknown'),
      'deviceUniqueId':   body.get('deviceUniqueId','unknown'),
      'startTime':        body.get('startTime', ""),
      'endTime':          body.get('endTime', ""),
      'fileName':         fileName,
      'md5':              body.get('md5', ""),
      's3Uri':            f"s3://{bucket}/{key}",
      'status':           'pending_upload',
      'createdAt':        now,
      'expiresAt':        expiresAt
    }
    if recordingType == 'enroll':
      item['speakerType'] = body.get('speakerType','clinician')

    table.put_item(Item=item)

    # 5) Generate presigned URL
    upload_url = s3.generate_presigned_url(
      ClientMethod='put_object',
      Params={'Bucket': bucket, 'Key': key},
      ExpiresIn=300   # 5 minutes
    )

    # 6) Respond with the reservation
    return {
      'statusCode': 201,
      'body': json.dumps({
        'recordingId': recordingId,
        'status':      'pending_upload',
        'uploadUrl':   upload_url,
        'expiresAt':   expiresAt
      })
    }
