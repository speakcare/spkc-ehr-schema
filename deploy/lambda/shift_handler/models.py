# models.py
from pydantic import BaseModel, Field
from typing import List, Optional
import json

class ShiftStartData(BaseModel):
    """Model for shift start data extracted from audio transcription"""
    fullName: Optional[str] = Field(description="The full name of the nurse, first and last name if found in the text or null if unknown")
    shift: Optional[str] = Field(description="Shift name chosen from allowed list or null if unknown")
    corridor: Optional[str] = Field(description="Corridor name chosen from allowed list or null if unknown")

    @classmethod
    def get_json_schema(cls, allowed_shifts: List[str], allowed_corridors: List[str]) -> dict:
        """Generate JSON schema for OpenAI API with dynamic enums provided by caller"""
        schema = cls.model_json_schema()
        # Inject dynamic enums for shift and corridor
        if isinstance(schema, dict):
            schema.setdefault("additionalProperties", False)
            props = schema.get("properties", {})
            # Allow nulls in all three fields for LLM output, but we'll validate later
            for key in ("fullName", "shift", "corridor"):
                if key in props:
                    # Ensure type allows nulls
                    field_type = props[key].get("type")
                    if isinstance(field_type, list):
                        if "null" not in field_type:
                            props[key]["type"].append("null")
                    else:
                        props[key]["type"] = [field_type, "null"] if field_type else ["string", "null"]
            if "shift" in props:
                props["shift"]["enum"] = allowed_shifts
            if "corridor" in props:
                props["corridor"]["enum"] = allowed_corridors
        return {
            "name": "speakcare_transcription",
            "schema": schema,
            "strict": True
        }

    @classmethod
    def get_json_schema_v2(cls, allowed_shifts: List[str], allowed_corridors: List[str], nurse_names: List[str]) -> dict:
        """Generate JSON schema using array-with-nested-enum structure (alternative approach)"""
        schema = cls.model_json_schema()
        if isinstance(schema, dict):
            schema.setdefault("additionalProperties", False)
            props = schema.get("properties", {})
            
            # Transform shift and corridor to array-with-nested-enum structure
            for field_name, allowed_values in [("shift", allowed_shifts), ("corridor", allowed_corridors)]:
                if field_name in props:
                    props[field_name] = {
                        "type": ["array", "null"],
                        "items": {
                            "type": ["string", "null"],
                            "enum": allowed_values
                        },
                        "description": f"(required): Select one or more of the valid enum options if and only if the prompt text exactly matches that value. If you are not sure, select null"
                    }
            
            # Update fullName to use nurse names list with best match description
            if "fullName" in props:
                props["fullName"] = {
                    "type": ["array", "null"],
                    "items": {
                        "type": ["string", "null"],
                        "enum": nurse_names
                    },
                    "description": f'''(required): Find the best matching nurse name from the provided list that most closely matches the spoken name in the text. 
                                       The selected name must truly resemble the name that was spoken, it cannot be a partial match, must sound phonetically exactly like the name that was spoken. 
                                       If no good match is found, select null'''
                }
        
        return {
            "name": "speakcare_transcription",
            "schema": schema,
            "strict": True
        }

    def validate_extraction(self, allowed_shifts: List[str], allowed_corridors: List[str]) -> tuple[bool, str]:
        """Validate that all required fields are present and valid using provided allowed lists"""
        try:
            # Check if fullName is not empty
            if self.fullName is None or not self.fullName.strip():
                return False, "Full name is missing or empty"

            # Validate against dynamic lists
            if self.shift is None:
                return False, "Shift is missing"
            if self.shift not in allowed_shifts:
                return False, f"Shift '{self.shift}' is not one of: {', '.join(allowed_shifts)}"

            if self.corridor is None or not self.corridor.strip():
                return False, "Corridor name is missing or empty"
            if self.corridor not in allowed_corridors:
                return False, f"Corridor '{self.corridor}' is not one of: {', '.join(allowed_corridors)}"

            return True, "All fields are valid"

        except Exception as e:
            return False, f"Validation error: {str(e)}"
