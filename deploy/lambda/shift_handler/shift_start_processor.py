# audio_processor.py
import os
import tempfile
from typing import Tuple, Optional
from openai import OpenAI
from models import ShiftStartData
import json

class ShiftStartProcessor:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.stt_model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
        # Force Whisper output language (default English) and optional translation
        self.stt_language = os.getenv("OPENAI_STT_LANGUAGE", "en")
        self.stt_translate = os.getenv("OPENAI_STT_TRANSLATE_TO_EN", "true").lower() in ("1", "true", "yes")
        self.chat_model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano-2025-04-14")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", "4096"))
        # Prefer new variable name; fall back to old for backward compatibility
        self.max_audio_size = int(os.getenv("MAX_SIGN_IN_AUDIO_SIZE_BYTES", 512000))

    def validate_audio(self, audio_data: bytes) -> Tuple[bool, str]:
        """Validate audio file size and basic format"""
        if len(audio_data) > self.max_audio_size:
            return False, f"Sign-in audio too large. Maximum size: {self.max_audio_size} bytes"
        
        if len(audio_data) < 100:  # Minimum reasonable size
            return False, "Audio file too small or corrupted"
        
        return True, "Audio file is valid"

    def transcribe_audio(self, audio_data: bytes, filename: str = None) -> Tuple[bool, str, Optional[str]]:
        """Transcribe audio using OpenAI Whisper"""
        try:
            # Determine file extension from filename or default to .wav
            if filename and '.' in filename:
                file_extension = '.' + filename.split('.')[-1].lower()
                # Validate extension is a supported audio format
                supported_extensions = ['.mp3', '.m4a', '.wav', '.webm', '.ogg', '.flac']
                if file_extension not in supported_extensions:
                    file_extension = '.wav'  # Default fallback
            else:
                file_extension = '.wav'  # Default fallback
            
            # Create temporary file for audio with correct extension
            with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                # Transcribe using OpenAI Whisper
                with open(temp_file.name, "rb") as audio_file:
                    if self.stt_translate:
                        # Use translations API to force English output
                        transcription = self.openai_client.audio.translations.create(
                            model=self.stt_model,
                            file=audio_file
                        )
                    else:
                        # Standard transcription; pass language hint when provided
                        transcription = self.openai_client.audio.transcriptions.create(
                            model=self.stt_model,
                            file=audio_file,
                            language=self.stt_language
                        )
                
                # Pretty-print the STT result text
                try:
                    print("Whisper transcription text:\n" + json.dumps(transcription.text, ensure_ascii=False, indent=4))
                except Exception:
                    pass

                # Clean up temp file
                os.unlink(temp_file.name)
                
                return True, "Transcription successful", transcription.text
                
        except Exception as e:
            return False, f"Transcription failed: {str(e)}", None

    def extract_shift_data(self, transcription_text: str, allowed_shifts: list[str], allowed_corridors: list[str], nurse_names: list[str]) -> Tuple[bool, str, Optional[ShiftStartData]]:
        """Extract shift start data from transcription using OpenAI Chat Completion"""
        try:
            system_prompt = "You are a text-based sign-in agent. You are provided with a text and your job is to extract sign-in features from the text."
            user_prompt = f'''Here is the text from the user: '{transcription_text}'\n\nExtract the nurse's full name, shift name and corridor name from this text.
                               The nurse name must be the best match from: {nurse_names}
                               The shift name must be one of the following: {allowed_shifts} and the corridor name must be one of the following: {allowed_corridors}.
                               Do not guess. You must only choose a value if-and-only-if the exact option text (case-insensitive) appears in the user's text. Otherwise set it to null.
                               For the nurse name, find the best matching name from the provided list that most closely matches what was spoken, but only if the name really resembles the name that was spoken.'''

                            #    Example:
                            #    if the text is: "I'm going to take the evening shift in Corridor 67B."
                            #    and the allowed corridors are: ["Corridor 1", "Corridor 2", "Corridor 3"]
                            #    the correct output is: corridor=null (because none of the allowed corridors appear in the text).'''
            
            # Get JSON schema from Pydantic model using dynamic enums (v2 with array structure)
            json_schema = ShiftStartData.get_json_schema_v2(allowed_shifts, allowed_corridors, nurse_names)
            
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
            
            try:
                printable_args = {
                    "model": self.chat_model,
                    "messages": chat_completion_args["messages"],
                    "temperature": self.temperature,
                    "max_completion_tokens": self.max_tokens,
                    "response_format": json_schema,
                }
                print("OpenAI chat.completions args:\n" + json.dumps(printable_args, ensure_ascii=False, indent=4))
            except Exception:
                pass
            completion_response = self.openai_client.chat.completions.create(**chat_completion_args)
            response_content = completion_response.choices[0].message.content.strip()
            
            # Parse and validate the response
            try:
                response_data = json.loads(response_content)
                
                # Print LLM raw response before normalization
                try:
                    print("LLM raw response:\n" + json.dumps(response_data, ensure_ascii=False, indent=4))
                except Exception:
                    pass
                
                # Normalize array fields from schema v2 into single-value strings
                for key in ("fullName", "shift", "corridor"):
                    val = response_data.get(key)
                    if isinstance(val, list):
                        response_data[key] = (val[0] if val and isinstance(val[0], str) and val[0].strip() else None)
                
                shift_data = ShiftStartData(**response_data)
                
                # Post-check: prevent choosing allowed options that don't actually appear in text
                tx_lower = transcription_text.lower()
                if shift_data.shift is not None and shift_data.shift.lower() not in tx_lower:
                    shift_data.shift = None
                if shift_data.corridor is not None and shift_data.corridor.lower() not in tx_lower:
                    shift_data.corridor = None
                
                # Validate the extracted data
                is_valid, validation_message = shift_data.validate_extraction(allowed_shifts, allowed_corridors)
                if not is_valid:
                    try:
                        print("LLM raw response before post-check:\n" + json.dumps(response_data, ensure_ascii=False, indent=4))
                        print("Post-check adjusted response:\n" + json.dumps(shift_data.model_dump(), ensure_ascii=False, indent=4))
                        print("Validation failed with message:\n" + validation_message)
                        print("Allowed shifts:\n" + json.dumps(allowed_shifts, ensure_ascii=False, indent=4))
                        print("Allowed corridors:\n" + json.dumps(allowed_corridors, ensure_ascii=False, indent=4))
                    except Exception:
                        pass
                    return False, f"Extraction validation failed: {validation_message}", None
                
                return True, "Extraction successful", shift_data
                
            except json.JSONDecodeError as e:
                try:
                    print("Invalid JSON from LLM. Raw content:\n" + response_content)
                except Exception:
                    pass
                return False, f"Invalid JSON response: {str(e)}", None
            except Exception as e:
                return False, f"Data validation failed: {str(e)}", None
                
        except Exception as e:
            return False, f"Extraction failed: {str(e)}", None
