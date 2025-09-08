#!/usr/bin/env python3

import sys
from pathlib import Path
import json
import os

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from speakcare_charting import create_chart_completion
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv
from boto3_session import Boto3Session

# Load environment
SpeakcareEnv.load_env()

logger = SpeakcareLogger(__name__)


def test_patient_name_extraction(s3_json_transcript_path: str, table_name: str = 'MHCS.Neurological_Evaluation'):
    """
    Test patient name extraction following the exact speakcare_process.py flow:
    1. Read the original JSON transcript from S3 (AWS Transcribe output)
    2. Convert it to diarized text format (all speakers as Unknown, like real system)
    3. Send diarized transcript to chart completion to extract patient name
    """
    try:
        logger.info(f"Testing patient name extraction:")
        logger.info(f"  S3 JSON transcript: {s3_json_transcript_path}")
        logger.info(f"  Table: {table_name}")
        
        # Read JSON transcript from S3 and convert to diarized format
        boto3Session = Boto3Session.get_single_instance()
        json_content = boto3Session.get_s3_or_local_file_content(s3_json_transcript_path)
        
        if not json_content:
            raise Exception(f"Failed to read JSON transcript from S3: {s3_json_transcript_path}")
            
        transcript_data = json.loads(json_content)
        
        diarized_transcript_content = convert_json_to_diarized_text(transcript_data)
        logger.info(f"Diarized transcript length: {len(diarized_transcript_content)} characters")
        
        # Upload diarized transcript to S3 (simulating what real system does)
        test_s3_key = f"tests/test_diarized_transcript_{os.getpid()}.txt"
        
        try:
            # Upload to S3 (same as real diarization process)
            boto3Session.s3_put_object(key=test_s3_key, body=diarized_transcript_content)
            logger.info(f"Uploaded test diarized transcript to S3: {test_s3_key}")
            
            # Read from S3 (same as speakcare_process.py line 113)
            diarized_transcript = boto3Session.get_s3_or_local_file_content(test_s3_key)
            
            if not diarized_transcript:
                raise Exception("Failed to read diarized transcript from S3")
            
            # Call chart completion (same as speakcare_process.py line 128)
            logger.info("Calling create_chart_completion...")
            response_dict = create_chart_completion(transcript=diarized_transcript, emr_table_name=table_name)
            
            if response_dict:
                patient_name = response_dict.get('patient_name', 'NOT FOUND')
                
                print(f"\n=== PATIENT NAME EXTRACTION RESULTS ===")
                print(f"Patient name found: '{patient_name}'")
                print(f"Table name: {table_name}")
                print(f"S3 key: {test_s3_key}")
                
                return patient_name
            else:
                print("ERROR: No response dict returned from create_chart_completion")
                return None
                
        finally:
            # Cleanup S3 test file
            try:
                boto3Session.s3_delete_object(test_s3_key)
                logger.info(f"Cleaned up S3 test file: {test_s3_key}")
            except Exception as cleanup_error:
                logger.warning(f"Could not cleanup S3 test file {test_s3_key}: {cleanup_error}")
            
    except Exception as e:
        logger.log_exception("Error in patient name extraction test", e)
        print(f"ERROR: {e}")
        return None

def convert_json_to_diarized_text(transcript_data):
    """
    Convert AWS Transcribe JSON to diarized text format matching the real system output.
    Real system: All speakers are 'Unknown' role, with spk_0, spk_1, etc. speaker labels.
    """
    try:
        # Handle AWS Transcribe format
        if isinstance(transcript_data, dict) and 'results' in transcript_data:
            speaker_labels = transcript_data['results'].get('speaker_labels', {})
            items = transcript_data['results'].get('items', [])
            
            if speaker_labels and items:
                segments = speaker_labels.get('segments', [])
                diarized_lines = []
                
                for segment in segments:
                    speaker_label = segment.get('speaker_label', 'spk_0')
                    start_time = float(segment.get('start_time', 0))
                    end_time = float(segment.get('end_time', start_time + 5))
                    
                    # Build segment text from items in time range
                    segment_text = ""
                    for item in items:
                        if 'start_time' in item and 'end_time' in item:
                            try:
                                item_start = float(item['start_time'])
                                item_end = float(item['end_time'])
                                if start_time <= item_start <= end_time:
                                    alternatives = item.get('alternatives', [])
                                    if alternatives and 'content' in alternatives[0]:
                                        content = alternatives[0]['content']
                                        if item.get('type') == 'punctuation':
                                            segment_text += content
                                        else:
                                            segment_text += content + " "
                            except (ValueError, KeyError):
                                continue
                    
                    segment_text = segment_text.strip()
                    if segment_text:  # Include all segments, not just filtered ones
                        formatted_time = f"{int(start_time//60):02d}:{int(start_time%60):02d}:{int((start_time%1)*100):02d}"
                        # All speakers are Unknown in real system
                        diarized_lines.append(f"{formatted_time} speaker:{speaker_label} role:Unknown: {segment_text}")
                
                return '\n'.join(diarized_lines)
            
            # Fallback: use transcript text if no speaker segments
            elif 'transcripts' in transcript_data['results']:
                transcript_text = transcript_data['results']['transcripts'][0]['transcript']
                # Create simple mock diarization
                return f"00:00:00 speaker:spk_0 role:Unknown: {transcript_text}"
        
        # Fallback for other formats
        return f"00:00:00 speaker:spk_0 role:Unknown: {str(transcript_data)[:500]}"
        
    except Exception as e:
        logger.error(f"Error converting JSON to diarized text: {e}")
        return "00:00:00 speaker:spk_0 role:Unknown: Error processing transcript"




def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test patient name extraction from AWS Transcribe JSON in S3')
    parser.add_argument('s3_json_transcript_path', help='S3 path to the AWS Transcribe JSON transcript file (e.g., s3://bucket/transcriptions/file.json)')
    parser.add_argument('--table', default='MHCS.Neurological_Evaluation', 
                       help='EMR table name (default: MHCS.Neurological_Evaluation)')
    
    args = parser.parse_args()
    
    # Test patient name extraction
    patient_name = test_patient_name_extraction(args.s3_json_transcript_path, args.table)
    
    if patient_name:
        print(f"\n✅ SUCCESS: Found patient name '{patient_name}'")
    else:
        print(f"\n❌ FAILED: Could not extract patient name")


if __name__ == "__main__":
    main()
