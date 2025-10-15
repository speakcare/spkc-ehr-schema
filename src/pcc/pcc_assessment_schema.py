"""
PointClickCare Assessment Schema wrapper for SchemaConverterEngine.

This module provides a convenient wrapper around the SchemaConverterEngine
specifically designed for PointClickCare assessment forms. It handles the
meta-schema language definition, options extraction, and provides a clean
API for working with PCC assessments.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schema_engine import SchemaEngine

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
                                "allowed_types": ["txt", "dte", "dttm", "rad", "radh", "chk", "mcs", "mcsh", "num", "numde", "hck", "cmb", "inst", "diag", "gbdy"],
                                "ignored_types": ["bp", "he", "o2", "pnl", "pulse", "resp", "temp", "we", "cp"],
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
                                        "target_type": "chk",
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
                                    },
                                    "diag": {
                                        "target_type": "string",
                                        "requires_options": False
                                    },
                                    "gbdy": {
                                        "target_type": "virtual_container",
                                        "requires_options": True,
                                        "options_field": "responseOptions",
                                        "options_extractor": "extract_response_options"
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
        self.engine = SchemaEngine(PCC_META_SCHEMA)
        
        # Register the options extractor
        self.engine.register_options_extractor("extract_response_options", extract_response_options)
        
        # Register virtual container builder for gbdy fields
        def pcc_virtual_container_builder(engine: SchemaEngine, target_type: str, enum_values: List[str], nullable: bool, property_def: Dict[str, Any], prop: Dict[str, Any]):
            # Build children from responseOptions
            options = prop.get("responseOptions", []) or []
            child_names: List[str] = []
            properties: Dict[str, Any] = {}
            virtual_children_metadata: List[Dict[str, Any]] = []
            for idx, opt in enumerate(options):
                name = opt.get("responseText")
                if not name:
                    continue
                child_names.append(name)
                # Build each child as nullable string via engine helper
                properties[name] = engine.build_property_node("string", prop=prop, nullable=True)
                virtual_children_metadata.append({
                    "child_property_name": name,
                    "child_index": idx,
                    "response_value": opt.get("responseValue")
                })
            # Create container object (non-nullable)
            container = engine.create_object_node(nullable=False)
            engine.add_properties(container, properties)
            engine.set_required(container, child_names)
            return (container, virtual_children_metadata)
        
        self.engine.register_field_schema_builder("virtual_container", pcc_virtual_container_builder)
        
        # Register PCC-specific reverse formatters
        def pcc_chk_schema_builder(engine: SchemaEngine, target_type: str, enum_values: List[str], nullable: bool, property_def: Dict[str, Any], prop: Dict[str, Any]):
            """Schema builder for PCC checkbox - creates boolean JSON schema."""
            return engine.build_property_node("boolean", nullable=nullable)
        
        def pcc_chk_reverse_formatter(engine, field_meta, model_value, table_name):
            """Reverse formatter for PCC checkbox - converts boolean to 1/None."""
            value = 1 if model_value else None
            return {field_meta["key"]: {"type": "checkbox", "value": value}}
        
        def pcc_radio_formatter(engine, field_meta, model_value, table_name):
            """Format radio buttons - extract responseValue from responseOptions."""
            if model_value is None:
                return {field_meta["key"]: {"type": "radio", "value": None}}
            
            field_schema = field_meta["field_schema"]
            response_options = field_schema.get("responseOptions", [])
            
            for option in response_options:
                if option.get("responseText") == model_value:
                    return {field_meta["key"]: {"type": "radio", "value": option.get("responseValue")}}
            
            return {field_meta["key"]: {"type": "radio", "value": model_value}}
        
        def pcc_combo_formatter(engine, field_meta, model_value, table_name):
            """Format combo boxes - extract responseValue from responseOptions."""
            if model_value is None:
                return {field_meta["key"]: {"type": "combo", "value": None}}
            
            field_schema = field_meta["field_schema"]
            response_options = field_schema.get("responseOptions", [])
            
            for option in response_options:
                if option.get("responseText") == model_value:
                    return {field_meta["key"]: {"type": "combo", "value": option.get("responseValue")}}
            
            return {field_meta["key"]: {"type": "combo", "value": model_value}}
        
        def pcc_multi_select_formatter(engine, field_meta, model_value, table_name):
            """Format multi select - return list of responseValues."""
            if not model_value or not isinstance(model_value, list):
                return {field_meta["key"]: {"type": "multi", "value": None}}
            
            field_schema = field_meta["field_schema"]
            response_options = field_schema.get("responseOptions", [])
            results = []
            
            for selected_text in model_value:
                for option in response_options:
                    if option.get("responseText") == selected_text:
                        results.append(option.get("responseValue"))
                        break
            
            return {field_meta["key"]: {"type": "multi", "value": results if results else None}}
        
        def pcc_virtual_container_formatter(engine, field_meta, model_value, table_name):
            """
            Format virtual container (gbdy type).
            Expands to multiple a#_key/b#_key pairs.
            """
            if not model_value or not isinstance(model_value, dict):
                return {field_meta["key"]: {"type": "table", "value": None}}
            
            parent_key = field_meta["key"]
            length_limit = field_meta.get("field_schema", {}).get("length", 999)
            
            # Get expanded children metadata (contains child_index and response_value)
            # Use the public API to get field metadata
            field_index = engine.get_field_metadata(table_name)
            virtual_container_key = field_meta["key"]
            
            # Find child metadata entries
            children = [
                f for f in field_index
                if f.get("is_virtual_container_child") and f.get("virtual_container_key") == virtual_container_key
            ]
            
            results = []
            idx = 0
            
            for child_meta in children:
                if idx >= length_limit:
                    break
                
                child_name = child_meta.get("property_key")
                child_value = model_value.get(child_name)
                
                # Skip null values
                if child_value is None:
                    continue
                
                response_value = child_meta.get("response_value")
                results.append({f"a{idx}_{parent_key}": response_value, f"b{idx}_{parent_key}": child_value})
                idx += 1
            
            return {field_meta["key"]: {"type": "table", "value": results if results else None}}
        
        # Register builders and formatters by original schema type
        self.engine.register_field_schema_builder("chk", pcc_chk_schema_builder)
        self.engine.register_reverse_formatter("chk", pcc_chk_reverse_formatter)
        self.engine.register_reverse_formatter("rad", pcc_radio_formatter)
        self.engine.register_reverse_formatter("radh", pcc_radio_formatter)
        self.engine.register_reverse_formatter("cmb", pcc_combo_formatter)
        self.engine.register_reverse_formatter("mcs", pcc_multi_select_formatter)
        self.engine.register_reverse_formatter("mcsh", pcc_multi_select_formatter)
        self.engine.register_reverse_formatter("gbdy", pcc_virtual_container_formatter)
    
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
