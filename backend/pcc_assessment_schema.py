"""
PointClickCare Assessment Schema wrapper for SchemaConverterEngine.

This module provides a convenient wrapper around the SchemaConverterEngine
specifically designed for PointClickCare assessment forms. It handles the
meta-schema language definition, options extraction, and provides a clean
API for working with PCC assessments.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union

from schema_converter_engine import SchemaConverterEngine

logger = logging.getLogger(__name__)

# PointClickCare meta-schema language definition
PCC_META_SCHEMA = {
    "schema_name": "assessmentDescription",
    "schema_id": "templateId", 
    "schema_version": "templateVersion",
    
    "container": {
        "container_name": "sections",
        "container_type": "array",
        "object": {
            "name": "sectionDescription",
            "key": "sectionCode",
            "container": {
                "container_name": "assessmentQuestionGroups",
                "container_type": "array",
                "object": {
                    "name": "groupText",
                    "key": "groupNumber",
                    "title": "groupTitle",
                    "properties": {
                        "properties_name": "questions",
                        "property": {
                            "key": "questionKey",
                            "id": "questionNumber",
                            "name": "questionText",
                            "title": "questionTitle",
                            "type": "questionType",
                            "options": "responseOptions",
                            "validation": {
                                "allowed_types": ["txt", "dte", "dttm", "rad", "radh", "chk", "mcs", "mcsh", "num", "numde", "hck", "cmb", "inst"],
                                "type_constraints": {
                                    "txt": {
                                        "target_type": "string",
                                        "requires_options": False
                                    },
                                    "rad": {
                                        "target_type": "single_select",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
                                    },
                                    "radh": {
                                        "target_type": "single_select",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
                                    },
                                    "dte": {
                                        "target_type": "date",
                                        "requires_options": False
                                    },
                                    "dttm": {
                                        "target_type": "datetime",
                                        "requires_options": False
                                    },
                                    "chk": {
                                        "target_type": "boolean",
                                        "requires_options": False
                                    },
                                    "mcs": {
                                        "target_type": "multiple_select",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
                                    },
                                    "mcsh": {
                                        "target_type": "multiple_select",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
                                    },
                                    "num": {
                                        "target_type": "positive_integer",
                                        "requires_options": False
                                    },
                                    "numde": {
                                        "target_type": "positive_number",
                                        "requires_options": False
                                    },
                                    "hck": {
                                        "target_type": "single_select",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
                                    },
                                    "cmb": {
                                        "target_type": "single_select",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
                                    },
                                    "inst": {
                                        "target_type": "instructions",
                                        "requires_options": False
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


def extract_response_options(options: List[Dict[str, Any]]) -> List[str]:
    """
    Extract response text values from PointClickCare response options.
    
    Args:
        options: List of response option dictionaries with 'responseText' and 'responseValue'
        
    Returns:
        List of response text strings (not response values)
    """
    if not options:
        return []
    
    return [option.get("responseText", "") for option in options if option.get("responseText")]


class PCCAssessmentSchema:
    """
    PointClickCare Assessment Schema wrapper around SchemaConverterEngine.
    
    Provides a convenient API for registering PCC assessments, generating
    JSON schemas, and validating assessment data.
    """
    
    def __init__(self):
        """Initialize the PCC Assessment Schema engine."""
        self.engine = SchemaConverterEngine(PCC_META_SCHEMA)
        
        # Register the options extractor
        self.engine.register_options_extractor("extract_response_options", extract_response_options)
        
        logger.info("PCC Assessment Schema engine initialized")
    
    def register_assessment(self, assessment_id: Optional[int], assessment_schema: Dict[str, Any]) -> Tuple[int, str]:
        """
        Register a PointClickCare assessment schema.
        
        Args:
            assessment_id: Integer assessment ID. If None, an ID will be automatically allocated.
            assessment_schema: The PCC assessment schema dictionary
            
        Returns:
            Tuple of (assessment_id, assessment_name)
        """
        assessment_id, assessment_name = self.engine.register_table(assessment_id, assessment_schema)
        logger.info(f"Registered PCC assessment: id={assessment_id}, name='{assessment_name}'")
        return assessment_id, assessment_name
    
    def get_json_schema(self, assessment_identifier: Union[int, str]) -> Dict[str, Any]:
        """
        Get the JSON schema for a registered assessment.
        
        Args:
            assessment_identifier: Either an integer assessment ID or string assessment name
            
        Returns:
            OpenAI-compatible JSON schema dictionary
        """
        return self.engine.get_json_schema(assessment_identifier)
    
    def validate(self, assessment_identifier: Union[int, str], data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate data against a registered assessment schema.
        
        Args:
            assessment_identifier: Either an integer assessment ID or string assessment name
            data: Data to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        return self.engine.validate(assessment_identifier, data)
    
    def get_field_metadata(self, assessment_identifier: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Get field metadata for a registered assessment.
        
        Args:
            assessment_identifier: Either an integer assessment ID or string assessment name
            
        Returns:
            List of field metadata dictionaries
        """
        return self.engine.get_field_metadata(assessment_identifier)
    
    def list_assessments(self) -> List[int]:
        """
        List all registered assessment IDs.
        
        Returns:
            List of assessment identifiers
        """
        return self.engine.list_tables()
