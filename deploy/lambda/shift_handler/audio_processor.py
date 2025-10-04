# audio_processor.py
import os
import tempfile
from typing import Tuple, Optional
from openai import OpenAI
from models import ShiftStartData
import json

class AudioProcessor:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.stt_model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
        self.chat_model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano-2025-04-14")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", "4096"))
        self.max_audio_size = int(os.getenv("MAX_AUDIO_SIZE_BYTES", "102400"))  # 100KB default

    def validate_audio(self, audio_data: bytes) -> Tuple[bool, str]:
        """Validate audio file size and basic format"""
        if len(audio_data) > self.max_audio_size:
            return False, f"Audio file too large. Maximum size: {self.max_audio_size} bytes"
        
        if len(audio_data) < 100:  # Minimum reasonable size
            return False, "Audio file too small or corrupted"
        
        return True, "Audio file is valid"

    def transcribe_audio(self, audio_data: bytes) -> Tuple[bool, str, Optional[str]]:
        """Transcribe audio using OpenAI Whisper"""
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                # Transcribe using OpenAI Whisper
                with open(temp_file.name, "rb") as audio_file:
                    transcription = self.openai_client.audio.transcriptions.create(
                        model=self.stt_model,
                        file=audio_file
                    )
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
                return True, "Transcription successful", transcription.text
                
        except Exception as e:
            return False, f"Transcription failed: {str(e)}", None

    def extract_shift_data(self, transcription_text: str) -> Tuple[bool, str, Optional[ShiftStartData]]:
        """Extract shift start data from transcription using OpenAI Chat Completion"""
        try:
            system_prompt = "You are a text-based sign-in agent. You are provided with a text and your job is to extract sign-in features from the text."
            user_prompt = f"Here is the text from the user: '{transcription_text}'\n\nExtract the nurse's full name, shift type (morning/evening/night), and corridor name from this text."
            
            # Get JSON schema from Pydantic model
            json_schema = ShiftStartData.get_json_schema()
            
            chat_completion_args = {
                "model": self.chat_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.temperature,
                "max_completion_tokens": self.max_tokens,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": json_schema
                }
            }
            
            completion_response = self.openai_client.chat.completions.create(**chat_completion_args)
            response_content = completion_response.choices[0].message.content.strip()
            
            # Parse and validate the response
            try:
                response_data = json.loads(response_content)
                shift_data = ShiftStartData(**response_data)
                
                # Validate the extracted data
                is_valid, validation_message = shift_data.validate_extraction()
                if not is_valid:
                    return False, f"Extraction validation failed: {validation_message}", None
                
                return True, "Extraction successful", shift_data
                
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON response: {str(e)}", None
            except Exception as e:
                return False, f"Data validation failed: {str(e)}", None
                
        except Exception as e:
            return False, f"Extraction failed: {str(e)}", None
