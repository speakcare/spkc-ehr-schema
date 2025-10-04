# models.py
from pydantic import BaseModel, Field
from typing import Literal
import json

class ShiftStartData(BaseModel):
    """Model for shift start data extracted from audio transcription"""
    fullName: str = Field(description="The full name of the nurse, first and last name if found in the text")
    shift: Literal["morning", "evening", "night"] = Field(description="One of morning, evening, night")
    corridor: str = Field(description="The corridor name")

    @classmethod
    def get_json_schema(cls) -> dict:
        """Generate JSON schema for OpenAI API"""
        schema = cls.model_json_schema()
        return {
            "name": "speakcare_transcription",
            "schema": schema,
            "strict": True
        }

    def validate_extraction(self) -> tuple[bool, str]:
        """Validate that all required fields are present and valid"""
        try:
            # Check if fullName is not empty
            if not self.fullName or not self.fullName.strip():
                return False, "Full name is missing or empty"
            
            # Check if corridor is not empty
            if not self.corridor or not self.corridor.strip():
                return False, "Corridor name is missing or empty"
            
            # Shift is already validated by the Literal type
            return True, "All fields are valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
