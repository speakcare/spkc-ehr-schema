"""
PointClickCare Assessment Schema wrapper for SchemaConverterEngine.

This module provides a convenient wrapper around the SchemaConverterEngine
specifically designed for PointClickCare assessment forms. It handles the
meta-schema language definition, options extraction, and provides a clean
API for working with PCC assessments.
"""

import logging
import json
import os
from copy import deepcopy
from typing import Dict, Any, List, Optional, Tuple, Union

from schema_engine.schema_engine import SchemaEngine
from schema_engine.csv_to_dict import (
    read_key_value_csv_path,
    read_key_value_csv_s3,
)

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
                                        "target_type": "object_array",
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


def merge_update(current: Dict[str, Any], update: Dict[str, Any], updated_object_name: str) -> Dict[str, Any]:
    """
    Merge a partial update into the current assessment data without mutating inputs.

    Args:
        current: The full assessment data dictionary.
        update: The partial update dictionary to merge.
        updated_object_name: The key of the nested object that contains updated properties.

    Returns:
        A new dictionary with the merged assessment data.

    Raises:
        TypeError: If current or update is not a dictionary.
        ValueError: If updated_object_name is empty.
    """
    if not isinstance(current, dict):
        raise TypeError("current must be a dictionary.")
    if not isinstance(update, dict):
        raise TypeError("update must be a dictionary.")
    if not isinstance(updated_object_name, str) or not updated_object_name:
        raise ValueError("updated_object_name must be a non-empty string.")

    merged: Dict[str, Any] = deepcopy(current)

    if updated_object_name not in update:
        return merged

    if updated_object_name not in merged or not isinstance(merged.get(updated_object_name), dict):
        merged[updated_object_name] = deepcopy(update[updated_object_name])
        return merged

    updated_container = update.get(updated_object_name)
    if not isinstance(updated_container, dict):
        return merged

    target_container: Dict[str, Any] = merged.setdefault(updated_object_name, {})
    for nested_key, nested_value in updated_container.items():
        target_container[nested_key] = deepcopy(nested_value)

    return merged


def get_section_state(formatted_json: Dict[str, Any], section_name: str) -> Optional[str]:
    """
    Get the state of a specific section from the formatted JSON output.
    
    Args:
        formatted_json: The formatted JSON output from reverse_map
        section_name: The section name/key (e.g., "Cust_1")
        
    Returns:
        The state of the section, or None if section not found
    """
    if not isinstance(formatted_json, dict):
        return None
    
    sections = formatted_json.get("sections")
    if not isinstance(sections, dict):
        return None
    
    section_data = sections.get(section_name)
    if not isinstance(section_data, dict):
        return None
    
    return section_data.get("state")


def get_all_section_states(formatted_json: Dict[str, Any]) -> List[str]:
    """
    Get all section states as an array in the order sections appear.
    
    Args:
        formatted_json: The formatted JSON output from reverse_map
        
    Returns:
        List of section states. Returns "draft" as default if state is missing.
    """
    if not isinstance(formatted_json, dict):
        return []
    
    sections = formatted_json.get("sections")
    if not isinstance(sections, dict):
        return []
    
    states = []
    for section_key in sorted(sections.keys()):  # Sort for consistent ordering
        section_data = sections[section_key]
        if isinstance(section_data, dict):
            state = section_data.get("state", "draft")  # Default to "draft" if missing
            states.append(state)
    
    return states


class PCCAssessmentSchema:
    """
    PointClickCare Assessment Schema wrapper around SchemaConverterEngine.
    
    Provides a convenient API for registering PCC assessments, generating
    JSON schemas, and validating assessment data.
    """
    
    # Define the 4 assessment templates with their templateId values
    TEMPLATES = [
        {
            "filename": "MHCS_IDT_5_Day_Section_GG.json",
            "template_id": 21242733,
            "name": "MHCS IDT 5 Day Section GG"
        },
        {
            "filename": "MHCS_Nursing_Admission_Assessment_-_V_5.json", 
            "template_id": 21244981,
            "name": "MHCS Nursing Admission Assessment - V 5"
        },
        {
            "filename": "MHCS_Nursing_Daily_Skilled_Note.json",
            "template_id": 21242741,
            "name": "MHCS Nursing Daily Skilled Note"
        },
        {
            "filename": "MHCS_Nursing_Weekly_Skin_Check.json",
            "template_id": 21244831,
            "name": "MHCS Nursing Weekly Skin Check"
        }
    ]
    
    def __init__(self):
        """Initialize the PCC Assessment Schema engine."""
        self.engine = SchemaEngine(PCC_META_SCHEMA, use_id_in_property_name=True)
        
        # Register the options extractor
        self.engine.register_options_extractor("extract_response_options", extract_response_options)
        
        # Register object_array builder for gbdy fields
        def pcc_object_array_schema_builder(engine: SchemaEngine, target_type: str, enum_values: List[str], nullable: bool, property_def: Dict[str, Any], prop: Dict[str, Any]):
            """Build JSON schema for object array (table) fields."""
            max_items = prop.get("length", 20)  # Default to 20 if not specified
            
            schema = {
                "type": "array",
                "description": "An array of objects that describe table entries. The 'entry' property is an enum selected for that entry, and the 'description' property is the description relevant for that enum.\nYou must only select enum entries and their descriptions if you are sure you found a clear reference to them in the provided transcript",
                "maxItems": max_items,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "entry": {
                            "type": "string",
                            "enum": enum_values or []
                        },
                        "description": {
                            "type": "string"
                        }
                    },
                    "required": ["entry", "description"]
                }
            }
            
            return schema
        
        self.engine.register_field_schema_builder("object_array", pcc_object_array_schema_builder)
        
        # Register PCC-specific reverse formatters
        def pcc_chk_schema_builder(engine: SchemaEngine, target_type: str, enum_values: List[str], nullable: bool, property_def: Dict[str, Any], prop: Dict[str, Any]):
            """Schema builder for PCC checkbox - creates boolean JSON schema."""
            return engine.build_property_node("boolean", nullable=nullable)
        
        def pcc_chk_reverse_formatter(engine, field_meta, model_value, table_name):
            """Reverse formatter for PCC checkbox - converts boolean to 1/None."""
            value = "1" if model_value else "null"
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
        
        def pcc_object_array_reverse_formatter(engine, field_meta, model_value, table_name):
            """Format object array (table) fields for PCC output."""
            if not model_value or not isinstance(model_value, list):
                return {}
            
            field_key = field_meta.get("key", "unknown")
            field_schema = field_meta.get("field_schema", {})
            response_options = field_schema.get("responseOptions", [])
            
            # Build a map from responseText to responseValue
            text_to_value = {opt["responseText"]: opt["responseValue"] for opt in response_options}
            
            # Convert array format to PCC aN/bN format
            table_rows = []
            for idx, item in enumerate(model_value):
                entry_text = item.get("entry", "")
                description_text = item.get("description", "")
                
                # Look up the responseValue for this entry
                entry_value = text_to_value.get(entry_text, "")
                
                row = {
                    f"a{idx}_{field_key}": entry_value,
                    f"b{idx}_{field_key}": description_text
                }
                table_rows.append(row)
            
            return {field_meta["key"]: {
                "type": "table",
                "value": table_rows
            }}
        
        def pcc_instructions_reverse_formatter(engine, field_meta, model_value, table_name):
            """Omit instruction fields from reverse output (PCC-specific need)."""
            return {}
        
        # Additional formatters for missing PCC field types
        def pcc_text_formatter(engine, field_meta, model_value, table_name):
            """Format text fields."""
            return {field_meta["key"]: {"type": "text", "value": model_value}}

        def pcc_date_formatter(engine, field_meta, model_value, table_name):
            """Format date fields."""
            return {field_meta["key"]: {"type": "date", "value": model_value}}

        def pcc_datetime_formatter(engine, field_meta, model_value, table_name):
            """Format datetime fields."""
            return {field_meta["key"]: {"type": "datetime", "value": model_value}}

        def pcc_number_formatter(engine, field_meta, model_value, table_name):
            """Format number fields."""
            return {field_meta["key"]: {"type": "number", "value": model_value}}

        def pcc_diagnosis_formatter(engine, field_meta, model_value, table_name):
            """Format diagnosis fields."""
            return {field_meta["key"]: {"type": "text", "value": model_value}}

        def pcc_hck_formatter(engine, field_meta, model_value, table_name):
            """Format hck (horizontal checkbox) fields."""
            # Similar to radio formatter
            if model_value is None:
                return {field_meta["key"]: {"type": "hck", "value": None}}
            
            field_schema = field_meta["field_schema"]
            response_options = field_schema.get("responseOptions", [])
            
            for option in response_options:
                if option.get("responseText") == model_value:
                    return {field_meta["key"]: {"type": "hck", "value": option.get("responseValue")}}
            
            return {field_meta["key"]: {"type": "hck", "value": model_value}}
        
        # Register builders and formatters by original schema type
        self.engine.register_field_schema_builder("chk", pcc_chk_schema_builder)
        self.engine.register_reverse_formatter("default", "chk", pcc_chk_reverse_formatter)
        self.engine.register_reverse_formatter("default", "rad", pcc_radio_formatter)
        self.engine.register_reverse_formatter("default", "radh", pcc_radio_formatter)
        self.engine.register_reverse_formatter("default", "cmb", pcc_combo_formatter)
        self.engine.register_reverse_formatter("default", "mcs", pcc_multi_select_formatter)
        self.engine.register_reverse_formatter("default", "mcsh", pcc_multi_select_formatter)
        self.engine.register_reverse_formatter("default", "gbdy", pcc_object_array_reverse_formatter)
        self.engine.register_reverse_formatter("default", "inst", pcc_instructions_reverse_formatter)
        
        # Register formatters for all PCC field types
        self.engine.register_reverse_formatter("default", "txt", pcc_text_formatter)
        self.engine.register_reverse_formatter("default", "dte", pcc_date_formatter)
        self.engine.register_reverse_formatter("default", "dttm", pcc_datetime_formatter)
        self.engine.register_reverse_formatter("default", "num", pcc_number_formatter)
        self.engine.register_reverse_formatter("default", "numde", pcc_number_formatter)
        self.engine.register_reverse_formatter("default", "diag", pcc_diagnosis_formatter)
        self.engine.register_reverse_formatter("default", "hck", pcc_hck_formatter)
        
        # PCC-UI formatters with unpacking capabilities
        def get_html_type(original_type, field_schema=None):
            """Determine HTML input type based on PCC field type and characteristics."""
            match original_type:
                case "rad" | "radh" | "hck":
                    return "radio_buttons"
                case "cmb":
                    return "combobox"
                case "chk":
                    return "checkbox_single"
                case "mcs" | "mcsh":
                    return "checkbox_multi"
                case "txt" | "diag":
                    length = field_schema.get("length", 0) if field_schema else 0
                    return "textarea_singleline" if length <= 50 else "textarea_multiline"
                case "dte" | "dttm":
                    return "text"
                case "num" | "numde":
                    return "textarea_singleline"
                case "gbdy_entry":
                    return "combobox"
                case "gbdy_description":
                    return "textarea_singleline"
                case _:
                    return "text"  # Default fallback
        
        def pcc_ui_basic_formatter(engine, field_meta, model_value, table_name):
            """Format basic fields with original type."""
            original_type = field_meta["original_schema_type"]
            field_schema = field_meta.get("field_schema", {})
            
            return [{
                "key": field_meta["key"],
                "type": original_type,
                "html_type": get_html_type(original_type, field_schema),
                "value": model_value
            }]
        
        def pcc_ui_number_formatter(engine, field_meta, model_value, table_name):
            """Format number fields - convert to string for UI."""
            original_type = field_meta["original_schema_type"]
            field_schema = field_meta.get("field_schema", {})
            
            # Convert numeric values to strings
            if model_value is not None:
                model_value = str(model_value)
            
            return [{
                "key": field_meta["key"],
                "type": original_type,
                "html_type": get_html_type(original_type, field_schema),
                "value": model_value
            }]
        
        def pcc_ui_single_select_formatter(engine, field_meta, model_value, table_name):
            """Format single select - extract responseValue."""
            original_type = field_meta["original_schema_type"]
            field_schema = field_meta.get("field_schema", {})
            
            if model_value is None:
                return [{
                    "key": field_meta["key"],
                    "type": original_type,
                    "html_type": get_html_type(original_type, field_schema),
                    "value": None
                }]
            
            response_options = field_schema.get("responseOptions", [])
            
            response_value = model_value
            for option in response_options:
                # Sanitize the responseText to match the sanitized model_value
                sanitized_response_text = engine._sanitize_for_json(option.get("responseText", ""))
                if sanitized_response_text == model_value:
                    response_value = option.get("responseValue")
                    break
            
            return [{
                "key": field_meta["key"],
                "type": original_type,
                "html_type": get_html_type(original_type, field_schema),
                "value": response_value
            }]
        
        def pcc_ui_multi_select_formatter(engine, field_meta, model_value, table_name):
            """Format multi-select - UNPACK into separate fields."""
            original_type = field_meta["original_schema_type"]
            field_schema = field_meta.get("field_schema", {})
            base_key = field_meta["key"]
            
            # Handle None/null values - return field with None value
            if model_value is None:
                return [{
                    "key": base_key,
                    "type": original_type,
                    "html_type": get_html_type(original_type, field_schema),
                    "value": None
                }]
            
            # Handle non-list values (shouldn't happen, but be safe)
            if not isinstance(model_value, list):
                return [{
                    "key": base_key,
                    "type": original_type,
                    "html_type": get_html_type(original_type, field_schema),
                    "value": None
                }]
            
            # Process list values (existing unpacking logic)
            response_options = field_schema.get("responseOptions", [])
            
            results = []
            for i, selected_text in enumerate(model_value):
                response_value = selected_text
                for option in response_options:
                    # Sanitize the responseText to match the sanitized model_value
                    sanitized_response_text = engine._sanitize_for_json(option.get("responseText", ""))
                    if sanitized_response_text == selected_text:
                        response_value = option.get("responseValue")
                        break
                
                results.append({
                    "key": base_key,
                    "type": original_type,
                    "html_type": get_html_type(original_type, field_schema),
                    "value": response_value,
                    "_original_field_key": base_key,
                    # Provide unique storage key so engine can store without collision
                    "_storage_key": f"{base_key}__{i}"
                })
            
            return results
        
        def pcc_ui_object_array_formatter(engine, field_meta, model_value, table_name):
            """Format object array - UNPACK into aN/bN pairs."""
            if not model_value or not isinstance(model_value, list):
                return []
            
            field_schema = field_meta["field_schema"]
            response_options = field_schema.get("responseOptions", [])
            base_key = field_meta["key"]
            original_type = field_meta["original_schema_type"]
            
            # Create mapping using sanitized responseText
            text_to_value = {engine._sanitize_for_json(opt["responseText"]): opt["responseValue"] for opt in response_options}
            
            results = []
            for idx, item in enumerate(model_value):
                entry_text = item.get("entry", "")
                description_text = item.get("description", "")
                entry_value = text_to_value.get(entry_text, "")
                
                results.append({
                    "key": base_key,
                    "type": original_type,
                    "html_type": get_html_type(f"{original_type}_entry", field_schema),
                    "value": entry_value,
                    "_original_field_key": base_key,
                    "_storage_key": f"a{idx}_{base_key}",
                    "_display_key": f"a{idx}_{base_key}"
                })
                
                results.append({
                    "key": base_key,
                    "type": original_type,
                    "html_type": get_html_type(f"{original_type}_description", field_schema),
                    "value": description_text,
                    "_original_field_key": base_key,
                    "_storage_key": f"b{idx}_{base_key}",
                    "_display_key": f"b{idx}_{base_key}"
                })
            
            return results
        
        def pcc_ui_checkbox_formatter(engine, field_meta, model_value, table_name):
            """Format checkbox - convert true/false to "1"/"null"."""
            original_type = field_meta["original_schema_type"]
            field_schema = field_meta.get("field_schema", {})
            
            # Convert boolean to PCC format: true -> "1", false -> "null"
            if model_value is True:
                value = "1"
            elif model_value is False:
                value = "null"
            else:
                value = model_value  # Keep as-is if not boolean
            
            return [{
                "key": field_meta["key"],
                "type": original_type,
                "html_type": get_html_type(original_type, field_schema),
                "value": value
            }]
        
        def pcc_ui_instructions_formatter(engine, field_meta, model_value, table_name):
            """Omit instruction fields."""
            return []
        
        # Register pcc-ui formatter set with specialized unpacking
        self.engine.register_reverse_formatter("pcc-ui", "txt", pcc_ui_basic_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "num", pcc_ui_number_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "numde", pcc_ui_number_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "dte", pcc_ui_basic_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "dttm", pcc_ui_basic_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "chk", pcc_ui_checkbox_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "diag", pcc_ui_basic_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "hck", pcc_ui_basic_formatter)

        self.engine.register_reverse_formatter("pcc-ui", "rad", pcc_ui_single_select_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "radh", pcc_ui_single_select_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "cmb", pcc_ui_single_select_formatter)

        self.engine.register_reverse_formatter("pcc-ui", "mcs", pcc_ui_multi_select_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "mcsh", pcc_ui_multi_select_formatter)

        self.engine.register_reverse_formatter("pcc-ui", "gbdy", pcc_ui_object_array_formatter)
        self.engine.register_reverse_formatter("pcc-ui", "inst", pcc_ui_instructions_formatter)
        
        # Load and register the 4 assessment templates
        self._load_and_register_templates()
    
    def _load_and_register_templates(self):
        """Load and register the 4 assessment templates from JSON files."""
        templates_dir = os.path.join(os.path.dirname(__file__), "assmnt_templates")
        
        for template in self.TEMPLATES:
            try:
                file_path = os.path.join(templates_dir, template["filename"])
                with open(file_path, 'r', encoding='utf-8') as f:
                    assessment_schema = json.load(f)
                
                # Register the assessment using its templateId
                assessment_id, assessment_name = self.register_assessment(template["template_id"], assessment_schema)
                logger.info(f"Successfully registered template: {template['name']} (ID: {assessment_id})")
                
            except Exception as e:
                logger.error(f"Failed to load template {template['filename']}: {e}")
                raise
    
    @staticmethod
    def get_assessment_templates_ids() -> List[Dict[str, Any]]:
        """
        Get a list of supported assessment templates with their IDs and names.
        
        Returns:
            List of dictionaries, each containing:
            - template_id: The template ID (integer)
            - name: The template name (string)
        """
        return [
            {
                "template_id": template["template_id"],
                "name": template["name"]
            }
            for template in PCCAssessmentSchema.TEMPLATES
        ]
    
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
    
    def get_num_sections(self, assessment_identifier: Union[int, str]) -> int:
        """
        Get the number of sections in a registered assessment.
        
        Args:
            assessment_identifier: Either an integer assessment ID or string assessment name
            
        Returns:
            Number of sections in the assessment
            
        Raises:
            KeyError: If assessment_identifier not found
        """
        return self.engine.get_container_count(assessment_identifier, "sections")
    
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
    
    def reverse_map(self, assessment_identifier: Union[int, str], model_response: Dict[str, Any], 
                   formatter_name: str = "pcc-ui", group_by_containers: Optional[List[str]] = None,
                   properties_key: str = "fields", pack_properties_as: str = "array",
                   pack_containers_as: str = "object",
                   metadata_field_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Reverse map a model response back to the original external schema format.
        
        Args:
            assessment_identifier: Either an integer assessment ID or string assessment name
            model_response: The model response data to reverse map
            formatter_name: Name of the formatter set to use (default: "pcc-ui")
            group_by_containers: List of container names to group by (default: ["sections"])
            properties_key: Name for the innermost properties container (default: "fields")
            pack_properties_as: Format for properties - "object" or "array" (default: "array")
            pack_containers_as: Format for container layers - "array" or "object" (default: "object")
            metadata_field_overrides: Optional dict to customize metadata field names.
                Example: {
                    "schema_name": "assessment_title",
                    "schema_id": "assessment_std_id",
                    "schema_type": {"name": "doc_type", "value": "pcc_assessment"}
                }
                Default: None (uses PCC defaults with doc_type=pcc_assessment)
            
        Returns:
            Dictionary with reverse mapped data in the specified format
        """
        # Default to grouping by sections for PCC assessments
        if group_by_containers is None:
            group_by_containers = ["sections"]
        
        # Apply PCC-specific default field name overrides if not provided
        if metadata_field_overrides is None:
            metadata_field_overrides = {
                "schema_name": "assessment_title",
                "schema_id": "assessment_std_id",
                "schema_type": {"name": "doc_type", "value": "pcc_assessment"}
            }
        
        # Resolve assessment identifier to table name
        table_id = self.engine.resolve_table_id(assessment_identifier)
        table_data = self.engine._SchemaEngine__tables[table_id]
        table_name = table_data["table_name"]
            
        result = self.engine.reverse_map(
            table_name, 
            model_response, 
            formatter_name=formatter_name,
            group_by_containers=group_by_containers,
            properties_key=properties_key,
            pack_properties_as=pack_properties_as,
            pack_containers_as=pack_containers_as,
            metadata_field_overrides=metadata_field_overrides
        )
        
        # Post-process to add state field to each section
        if "sections" in result and isinstance(result["sections"], dict):
            for section_key, section_data in result["sections"].items():
                if isinstance(section_data, dict) and "state" not in section_data:
                    section_data["state"] = "draft"
        
        return result

    def list_assessments_info(self) -> List[Dict[str, Any]]:
        """
        Return a list of registered assessments with their id and name.
        
        Returns:
            A list of dictionaries in the form: [{"id": <int>, "name": <str>}]
        """
        assessments_info: List[Dict[str, Any]] = []
        for assessment_id in self.engine.list_tables():
            schema = self.engine.get_json_schema(assessment_id)
            name = schema.get("title", str(assessment_id))
            assessments_info.append({"id": assessment_id, "name": name})
        return assessments_info

    def enrich_assessment_from_csv(
        self,
        assessment_identifier: Union[int, str],
        *,
        csv_path: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None,
        key_col: str,
        value_col: str,
        key_prefix: Optional[str] = "Cust",
        sanitize_values: bool = True,
        skip_blank_keys: bool = True,
        strip_whitespace: bool = False,
        case_insensitive: bool = False,
        on_duplicate: str = "concat",
        skip_first_row: bool = False,
    ) -> List[str]:
        """
        Convenience wrapper: read enrichment CSV (local path or S3) and enrich assessment schema.

        Exactly one of (csv_path) or (s3_bucket and s3_key) must be provided.

        Args:
            assessment_identifier: Assessment ID or name to enrich
            csv_path: Local filesystem path to the CSV file
            s3_bucket: S3 bucket name (if reading from S3)
            s3_key: S3 object key (if reading from S3)
            key_col: CSV column used for keys (required)
            value_col: CSV column used for values (required)
            key_prefix: If provided, prefix keys with "{key_prefix}_" unless already present (default: "Cust")
            sanitize_values: Sanitize values by removing HTML/JSON-breaking chars (default: True)
            skip_blank_keys: Skip empty/blank keys (default: True)
            strip_whitespace: Strip leading/trailing whitespace from keys/values (default: False)
            case_insensitive: Case-insensitive header matching (default: False)
            on_duplicate: Duplicate handling policy: "last" | "first" | "error" | "concat" (default: "concat")
            skip_first_row: If True, skip the first row before reading headers (default: False)

        Returns:
            List of unmatched keys returned by engine.enrich_schema.
        """
        if csv_path is None and not (s3_bucket and s3_key):
            raise ValueError("Provide either csv_path or (s3_bucket and s3_key)")
        if csv_path is not None and (s3_bucket or s3_key):
            raise ValueError("Provide only one source: csv_path or s3_bucket+s3_key, not both")

        # Build enrichment dict from CSV
        if csv_path:
            enrichment_dict = read_key_value_csv_path(
                csv_path,
                key_col=key_col,
                value_col=value_col,
                key_prefix=key_prefix,
                sanitize_values=sanitize_values,
                skip_blank_keys=skip_blank_keys,
                strip_whitespace=strip_whitespace,
                case_insensitive=case_insensitive,
                on_duplicate=on_duplicate,
                skip_first_row=skip_first_row,
            )
        else:
            enrichment_dict = read_key_value_csv_s3(
                bucket=s3_bucket or "",
                key=s3_key or "",
                key_col=key_col,
                value_col=value_col,
                key_prefix=key_prefix,
                sanitize_values=sanitize_values,
                skip_blank_keys=skip_blank_keys,
                strip_whitespace=strip_whitespace,
                case_insensitive=case_insensitive,
                on_duplicate=on_duplicate,
                skip_first_row=skip_first_row,
            )

        # Apply enrichment and return unmatched keys (engine resolves ID or name)
        return self.engine.enrich_schema(assessment_identifier, enrichment_dict)

    def is_valid_assessment_identifier(self, assessment_identifier: Union[int, str]) -> bool:
        """
        Check if the assessment identifier is valid.
        
        Args:
            assessment_identifier: Either an integer assessment ID or string assessment name
            
        Returns:
            True if the assessment identifier is valid, False otherwise
        """
        return self.engine.resolve_table_id(assessment_identifier) is not None
    
