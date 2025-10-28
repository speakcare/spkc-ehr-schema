"""
SchemaEngine: comprehensive schema operations engine for conversion, validation, enrichment, and reverse mapping.

Design highlights:
- One engine instance per external "schema language". All tables registered to an engine
  share the same field type mapping and per-type options extractors.
- The engine converts an external table schema (with up to 7 nesting levels) into an
  OpenAI-compatible JSON Schema subset and validates data against it.
- All bottom-level fields are listed in `required`. Optionality is expressed via
  union types that include "null". Objects always set `additionalProperties` to false.
- Supports target field types: string, integer, number, boolean, date, datetime,
  single_select, multiple_select, array, object.
- Uses function registries for schema builders, validators, and reverse formatters (per target type).
- Provides schema enrichment, reverse conversion, and container grouping capabilities.

## Meta-Schema Language Definition

The engine uses a meta-schema language to describe how external schema languages work.
This allows the engine to be truly database-agnostic by understanding any schema structure.

### Meta-Schema Structure:
```json
{
  "schema_name": "<field_name_for_table_name>", // mandatory
  "schema_id": "<field_name_for_table_id>",  // optional
  "schema_version": "<field_name_for_table_version>",  // optional
  
  "container": {
    "container_name": "<name_of_array_field>", // mandatory
    "container_type": "array",  // currently only "array" supported
    "object": {
      "name": "<field_name_for_item_name>",  // optional
      "key": "<field_name_for_item_key>",    // mandatory
      "title": "<field_name_for_item_title>", // optional
      
      // Either "container" (for nested levels) OR "properties" (for bottom level)
      "container": { /* recursive container definition */ },
      
      "properties": {  // ONLY when this is the bottom level
        "properties_name": "<name_of_properties_array>",
        "property": {
          "key": "<field_name_for_property_key>",      // mandatory
          "id": "<field_name_for_local_property_id>",  // optional
          "name": "<field_name_for_property_name>",    // mandatory
          "title": "<field_name_for_property_title>",  // optional
          "type": "<field_name_for_property_type>",    // mandatory
          "options": "<field_name_for_property_options>",  // optional
          
          // Note: For checkbox fields (like "chk" in PointClickCare), no options are provided
          // as they are always yes/no. We use boolean in OpenAI JSON schema (responds with true/false),
          // and later provide reverse conversion function (true->Yes, false->No).
          
          "validation": {  // optional validation rules
            "allowed_types": ["type1", "type2", ...], // mandatory - types to process
            "ignored_types": ["type3", "type4", ...], // optional - types to skip entirely (mutually exclusive with allowed_types)
            "type_constraints": { // mandatory
              // Only need entries for allowed_types, not ignored_types
              "type1": {
                "target_type": "<field_name_for_target_type>", // must be one of the target types supported by the engine - later maybe we will support external types
                "requires_options": <boolean>, // mandatory
                "options_field": "<field_name_for_options_field>",  // optional
                "options_extractor": "<reference to a function that extracts the options>"  // optional
              }, // mandatory
              "type2": {
                "target_type": "<field_name_for_target_type>", // must be one of the target types supported by the engine - later maybe we will support external types
                "requires_options": <boolean>, // mandatory
                "options_field": "<field_name_for_options_field>",  // optional
                "options_extractor": "<reference to a function that extracts the options>"  // optional
              } // mandatory
            }
          }
        }
      }
    }
  }
}
```

### PointClickCare Example:
```json
{
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
                "allowed_types": ["txt", "rad", "radh", "dte", "chk"],
                "type_constraints": {
                  "txt": {
                    "target_type": "string",
                    "requires_options": false
                  },
                  "rad": {
                    "target_type": "single_select",
                    "requires_options": true,
                    "options_field": "responseOptions",
                    "options_extractor": "extract_response_options"
                  },
                  "radh": {
                    "target_type": "single_select",
                    "requires_options": true,
                    "options_field": "responseOptions",
                    "options_extractor": "extract_response_options_horizontal"
                  },
                  "dte": {
                    "target_type": "date",
                    "requires_options": false
                  },
                  "chk": {
                    "target_type": "checkbox",
                    "requires_options": false
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
```

### Usage:
```python
# Initialize engine with meta-schema language definition
engine = SchemaEngine(schema_language_definition)

# Register individual tables using the external schema language
engine.register_table("mds_assessment", "MDS 2.0 Full Assessment", pointclickcare_schema)

# Get OpenAI-compatible JSON schema
json_schema = engine.get_json_schema("mds_assessment")

# Validate data against the schema
is_valid, errors = engine.validate("mds_assessment", data)

# Enrich schema with additional descriptions
engine.enrich_schema("mds_assessment", {"field_key": "Additional context"})

# Register formatters for a formatter set
def default_text_formatter(engine, field_meta, model_value, table_name):
    return {field_meta["key"]: {"type": "text", "value": model_value}}

engine.register_reverse_formatter("default", "txt", default_text_formatter)

# Convert model response using named formatter
result = engine.reverse_map("mds_assessment", model_response, formatter_name="default", group_by_containers=["sections"])
```

### Named Formatter Sets:

Applications can register multiple formatter sets for different output formats:

```python
# Register "default" formatters for PCC aN/bN format
def pcc_radio_formatter(engine, field_meta, model_value, table_name):
    field_schema = field_meta["field_schema"]
    response_options = field_schema.get("responseOptions", [])
    
    for option in response_options:
        if option.get("responseText") == model_value:
            return {field_meta["key"]: {"type": "radio", "value": option.get("responseValue")}}
    
    return {field_meta["key"]: {"type": "radio", "value": model_value}}

engine.register_reverse_formatter("default", "rad", pcc_radio_formatter)

# Register "ui-app" formatters for UI consumption
def ui_radio_formatter(engine, field_meta, model_value, table_name):
    return {field_meta["key"]: {"type": "radio", "value": model_value, "label": model_value}}

engine.register_reverse_formatter("ui-app", "rad", ui_radio_formatter)

# Use different formatters for different purposes
pcc_result = engine.reverse_map("assessment", model, formatter_name="default")
ui_result = engine.reverse_map("assessment", model, formatter_name="ui-app")
```

### Custom Validators:

Validators can access the original field schema to perform complex validation:

```python
def custom_single_select_validator(engine, value, field_metadata):
    '''Validate single select against field-specific options.'''
    # Access the original field schema
    field_schema = field_metadata.get("field_schema", {})
    
    # For Airtable: {"type": "single_select", "options": {"choices": [...]}}
    options = field_schema.get("options", {})
    choices = [c["name"] for c in options.get("choices", [])]
    
    if value not in choices:
        return False, f"Value '{value}' not in allowed choices: {choices}"
    
    return True, ""

# Register the validator (instance-specific, overrides global)
engine.register_validator("single_select", custom_single_select_validator)
```

### Custom Schema Field Builders:

Instance builders can access the complete field schema for complex JSON schema generation:

```python
def checkbox_yes_no_builder(engine, target_type, prop, nullable):
    '''Build Yes/No enum for checkbox fields (PointClickCare style).'''
    # Access field details if needed
    field_name = prop.get("questionText", "Checkbox")
    
    return {
        "type": ["string", "null"] if nullable else "string",
        "enum": ["Yes", "No", None] if nullable else ["Yes", "No"],
        "description": f"{field_name}: Select Yes or No"
    }

# Register the builder (instance-specific, overrides global)
engine.register_schema_field_builder("checkbox", checkbox_yes_no_builder)
```

### Virtual Containers:

Custom builders can create "virtual containers" - properties in the external
schema that expand into nested objects with multiple child properties in the
JSON schema.

To create a virtual container, a builder should return a tuple:
    (json_schema, additional_metadata)

Where:
- json_schema: Standard object schema with child properties
- additional_metadata: List of metadata dicts for each child property

The engine will:
1. Mark the field as a virtual container with flags:
   - "is_virtual_container": True
   - "expanded_children": [list of child property keys]
2. Add child metadata to field_index with proper level_keys
3. Mark children with "is_virtual_container_child": True

Example use case: PCC "gbdy" (grid/table) fields that expand one field
with response options into an object with a property per option.

```python
def virtual_container_builder(engine, target_type, field_schema, nullable):
    '''Build virtual container with child properties.'''
    # Extract options from field schema
    options = field_schema.get("responseOptions", [])
    
    # Build child properties
    child_properties = {}
    child_metadata = []
    
    for idx, option in enumerate(options):
        response_text = option.get("responseText", "")
        response_value = option.get("responseValue", "")
        
        # Add child property
        child_properties[response_text] = {"type": ["string", "null"]}
        
        # Add child metadata
        child_metadata.append({
            "key": field_schema.get("questionKey", ""),
            "name": response_text,
            "target_type": "string",
            "property_key": response_text,
            "field_schema": field_schema,
            "is_virtual_container_child": True,
            "virtual_container_key": field_schema.get("questionKey", ""),
            "response_value": response_value,
            "child_index": idx
        })
    
    # Build container schema
    container_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": child_properties,
        "required": list(child_properties.keys())
    }
    
    return (container_schema, child_metadata)

# Register the virtual container builder
engine.register_schema_field_builder("virtual_container", virtual_container_builder)
```

Notes:
- Max tables per engine instance: 1000 (re-registration allowed; replaces previous
  table with same id and logs info).
- Level keys are captured at every nesting level for reverse conversion.
- All HTML tags are automatically removed from names, titles, and enum options during
  registration to ensure clean data for LLM consumption.
- Options can be simple list[str] or complex (requiring extractor function).
- Validator signature: `(engine, value, field_metadata) -> (is_valid: bool, error: str)`
- Global builder signature: `(engine, target_type, enum_values, nullable) -> Dict[str, Any]`
- Instance builder signature: `(engine, target_type, field_schema, nullable) -> Dict[str, Any]`
- Reverse formatter signature: `(engine, field_meta, model_value, table_name) -> Dict[str, Dict[str, Any]]`
  - field_meta contains: key, name, level_keys, target_type, original_schema_type, field_schema, property_key
  - Returns: dict mapping field key to {"type": <label>, "value": <payload or null>}
  - Formatters are registered by original schema type (e.g., "rad", "cmb", "chk") with precedence over target type defaults
- The engine stores both `key` and `id` for bottom-level fields (for reverse mapping).
- Supports schema enrichment, reverse conversion, and container grouping.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import logging
import re

from sanitize_text import sanitize_for_json

try:
    # Prefer modern validator if available
    import jsonschema
    from jsonschema import Draft202012Validator as DefaultValidator
except Exception:  # pragma: no cover - fallback if version not available
    import jsonschema
    from jsonschema import Draft7Validator as DefaultValidator


logger = logging.getLogger(__name__)


MAX_TABLES_PER_ENGINE = 1000
MAX_NESTING_LEVELS = 7

# Function registries for schema builders and validators
__field_schema_builders_registry: Dict[str, Callable] = {}
__validator_registry: Dict[str, Callable] = {}

def _register_field_schema_builder(internal_type: str):
    """Decorator to register a schema builder function for an internal field type."""
    def decorator(func: Callable):
        __field_schema_builders_registry[internal_type] = func
        return func
    return decorator


def _register_validator(internal_type: str):
    """Decorator to register a validator function for an internal field type."""
    def decorator(func: Callable):
        __validator_registry[internal_type] = func
        return func
    return decorator


def _get_field_schema_builder(internal_type: str) -> Optional[Callable]:
    """Get the schema builder function for an internal field type."""
    return __field_schema_builders_registry.get(internal_type)


def _get_validator(internal_type: str) -> Optional[Callable]:
    """Get the validator function for an internal field type."""
    return __validator_registry.get(internal_type)


class SchemaEngine:
    """Engine for comprehensive schema operations including conversion, validation, enrichment, and reverse mapping."""

    def __init__(self, meta_schema_language: Dict[str, Any]) -> None:
        """
        Initialize a schema engine for one external "schema language".

        Args:
            meta_schema_language: Meta-schema definition describing the external schema language structure.
        """
        # Validate meta-schema language structure
        self.__validate_meta_schema(meta_schema_language)
        
        self.__meta_schema = meta_schema_language
        self.__options_extractor_registry: Dict[str, Callable] = {}
        self.__instance_validator_registry: Dict[str, Callable] = {}
        self.__instance_field_schema_builder_registry: Dict[str, Callable] = {}
        # Named formatter sets: {formatter_name: {original_schema_type: formatter_func}}
        self.__named_formatter_sets: Dict[str, Dict[str, Callable]] = {}

        # Table registry: table_id -> registry record
        self.__tables: Dict[int, Dict[str, Any]] = {}
        self.__last_allocated_id: int = 0
        # Name-to-ID mapping for lookup by name
        self.__table_names: Dict[str, int] = {}

    # ----------------------------- Public API ---------------------------------

    @staticmethod
    def _sanitize_for_json(text: Any) -> Any:
        """
        Remove HTML tags and JSON-breaking characters; pass through non-strings unchanged.
        
        This method delegates to the shared sanitize_for_json function.
        """
        return sanitize_for_json(text)

    def register_options_extractor(self, extractor_name: str, extractor_func: Callable[[Any], List[str]]) -> None:
        """Register an options extractor function."""
        self.__options_extractor_registry[extractor_name] = extractor_func

    def register_validator(self, target_type: str, validator_func: Callable) -> None:
        """Register a custom validator for a target type (instance-specific).
        
        Validator signature: func(engine, value, field_metadata) -> (is_valid: bool, error: str)
        - is_valid: True if valid, False otherwise
        - error: Empty string if valid, error message otherwise
        - field_metadata contains: key, name, level_keys, target_type, field_schema
        
        Instance validators override global validators for this engine instance only.
        
        Args:
            target_type: The target type (e.g., "single_select", "percent", "boolean")
            validator_func: Validation function
            
        Example:
            def my_percent_validator(engine, value, field_metadata):
                if not isinstance(value, (int, float)):
                    return False, "Percent must be a number"
                if not (0 <= value <= 100):
                    return False, f"Percent must be 0-100, got {value}"
                return True, ""
            
            engine.register_validator("percent", my_percent_validator)
        """
        self.__instance_validator_registry[target_type] = validator_func
        logger.debug(f"Registered instance validator for target_type='{target_type}'")

    def register_field_schema_builder(self, target_type: str, builder_func: Callable) -> None:
        """Register a custom JSON schema field builder for a target type (instance-specific).
        
        Builder signature: func(engine, target_type, field_schema, nullable) -> Dict[str, Any]
        - field_schema: The original external field definition (contains type, options, etc.)
        - nullable: Whether the field should allow null values
        - Returns: JSON schema dict for this field
        
        Instance builders override global builders for this engine instance only.
        
        Args:
            target_type: The target type (e.g., "checkbox", "percent")
            builder_func: Schema builder function
            
        Example (PointClickCare checkbox as Yes/No enum):
            def checkbox_yes_no_builder(engine, target_type, field_schema, nullable, property_def, field_schema_data):
                return {
                    "type": ["string", "null"] if nullable else "string",
                    "enum": ["Yes", "No", None] if nullable else ["Yes", "No"],
                    "description": "Select Yes or No"
                }
            
            engine.register_schema_field_builder("checkbox", checkbox_yes_no_builder)
        """
        self.__instance_field_schema_builder_registry[target_type] = builder_func
        logger.debug(f"Registered instance schema field builder for target_type='{target_type}'")

    def register_reverse_formatter(self, formatter_name: str, original_schema_type: str, formatter_func: Callable) -> None:
        """
        Register a reverse formatter for a specific original schema type within a named formatter set.
        
        Args:
            formatter_name: Name of the formatter set (e.g., "default", "ui-app")
            original_schema_type: The original schema type (e.g., "rad", "cmb", "gbdy")
            formatter_func: Formatter function with signature:
                (engine, field_meta, model_value, table_name) -> Dict[str, Dict[str, Any]]
                where field_meta contains: key, name, level_keys, target_type, original_schema_type, field_schema, property_key
                and returns: dict mapping field key to {"type": <label>, "value": <payload or null>}
        """
        if formatter_name not in self.__named_formatter_sets:
            self.__named_formatter_sets[formatter_name] = {}
        
        self.__named_formatter_sets[formatter_name][original_schema_type] = formatter_func
        logger.info(f"Registered reverse formatter for '{original_schema_type}' in formatter set '{formatter_name}'")

    def register_table(self, table_id: Optional[int], external_schema: Dict[str, Any]) -> Tuple[int, str]:
        """Register (or re-register) a table schema.

        Args:
            table_id: Integer table ID. If None, an ID will be automatically allocated.
            external_schema: The external table schema dictionary.

        Returns:
            Tuple of (table_id, table_name).

        Re-registration replaces the previous entry with info logging.
        Enforces a maximum of 1000 tables per engine instance.
        """
        # Allocate ID if not provided
        if table_id is None:
            table_id = self._allocate_table_id()
        
        # Extract table name from external schema using meta-schema
        schema_name_field = self.__meta_schema.get("schema_name")
        table_name =  self._sanitize_for_json(external_schema.get(schema_name_field, "Unknown Table")) if schema_name_field else "Unknown Table"
        
        if table_id in self.__tables:
            # Remove old name mapping if it exists
            old_record = self.__tables[table_id]
            old_name = old_record.get("table_name")
            if old_name and old_name in self.__table_names:
                del self.__table_names[old_name]
            logger.info("Re-registering table_id=%d (table_name=%s); replacing previous schema", table_id, table_name)
        elif len(self.__tables) >= MAX_TABLES_PER_ENGINE:
            raise ValueError(f"Maximum number of tables reached: {MAX_TABLES_PER_ENGINE}")

        json_schema, field_index, container_counts = self._build_table_schema(external_schema, table_name)

        self.__tables[table_id] = {
            "external_schema": external_schema,
            "json_schema": json_schema,
            "field_index": field_index,  # list of {key, id, level_keys}
            "table_name": table_name,
            "container_counts": container_counts,  # dict mapping container_name -> count
        }
        
        # Update name-to-ID mapping
        self.__table_names[table_name] = table_id
        
        return table_id, table_name

    def _allocate_table_id(self) -> int:
        """Allocate the next available table ID."""
        # Start from last allocated ID + 1
        candidate_id = self.__last_allocated_id + 1
        
        # Find next available ID
        while candidate_id in self.__tables:
            candidate_id += 1
        
        self.__last_allocated_id = candidate_id
        return candidate_id

    def _resolve_table_id(self, table_identifier: Union[int, str]) -> int:
        """Resolve table identifier (name or ID) to integer table ID.
        
        Args:
            table_identifier: Either an integer table ID or string table name
            
        Returns:
            Integer table ID
            
        Raises:
            ValueError: If table identifier is not found
        """
        if isinstance(table_identifier, int):
            if table_identifier not in self.__tables:
                raise ValueError(f"Unknown table_id: {table_identifier}")
            return table_identifier
        elif isinstance(table_identifier, str):
            if table_identifier not in self.__table_names:
                raise ValueError(f"Unknown table_name: {table_identifier}")
            return self.__table_names[table_identifier]
        else:
            raise ValueError(f"Table identifier must be int or str, got {type(table_identifier)}")

    def unregister_table(self, table_id: int) -> None:
        """Unregister a table by its ID."""
        if table_id in self.__tables:
            # Clean up name mapping
            table_name = self.__tables[table_id].get("table_name")
            if table_name and table_name in self.__table_names:
                del self.__table_names[table_name]
            # Remove table
            self.__tables.pop(table_id, None)

    def list_tables(self) -> List[int]:
        """List all registered table IDs."""
        return list(self.__tables.keys())

    def get_field_metadata(self, table_identifier: Union[int, str]) -> List[Dict[str, Any]]:
        """Get field metadata for a registered table.
        
        Args:
            table_identifier: Either an integer table ID or string table name
            
        Returns:
            List of field metadata dictionaries
        """
        table_id = self._resolve_table_id(table_identifier)
        rec = self.__tables.get(table_id)
        if not rec:
            raise KeyError(f"Unknown table_id: {table_id}")
        return rec["field_index"]

    def get_container_count(self, table_identifier: Union[int, str], container_name: str) -> int:
        """Get the count of items in a top-level container for a registered table.
        
        Args:
            table_identifier: Either an integer table ID or string table name
            container_name: Name of the top-level container (e.g., "sections")
            
        Returns:
            Count of items in the container, or 0 if container not found
            
        Raises:
            KeyError: If table_identifier not found
        """
        table_id = self._resolve_table_id(table_identifier)
        rec = self.__tables.get(table_id)
        if not rec:
            raise KeyError(f"Unknown table_id: {table_id}")
        
        container_counts = rec.get("container_counts", {})
        return container_counts.get(container_name, 0)

    def clear(self) -> None:
        """Clear all registered tables and reset state."""
        self.__tables.clear()
        self.__table_names.clear()
        self.__last_allocated_id = 0

    def get_json_schema(self, table_identifier: Union[int, str]) -> Dict[str, Any]:
        """Get the JSON schema for a registered table.
        
        Args:
            table_identifier: Either an integer table ID or string table name
            
        Returns:
            JSON schema dictionary
        """
        table_id = self._resolve_table_id(table_identifier)
        rec = self.__tables.get(table_id)
        if not rec:
            raise KeyError(f"Unknown table_id: {table_id}")
        return rec["json_schema"]

    def validate(self, table_identifier: Union[int, str], data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate data against registered JSON schema and custom validators.
        
        Args:
            table_identifier: Either an integer table ID or string table name
            data: Data to validate
        
        Returns:
            Tuple of (is_valid, errors).
            - is_valid: True if all validations pass
            - errors: List of error messages
        """
        table_id = self._resolve_table_id(table_identifier)
        rec = self.__tables.get(table_id)
        if not rec:
            raise KeyError(f"Unknown table_id: {table_id}")
        
        schema = rec["json_schema"]
        field_index = rec["field_index"]
        
        # Step 1: JSON schema validation (structure, types, required fields, enums)
        validator = DefaultValidator(schema)
        errors = [self._format_validation_error(e) for e in validator.iter_errors(data)]
        
        if errors:
            return False, errors
        
        # Step 2: Custom validators (instance overrides global)
        validation_errors = []
        self._apply_custom_validators(data, field_index, validation_errors)
        
        is_valid = len(validation_errors) == 0
        all_errors = errors + validation_errors
        return is_valid, all_errors

    def _apply_custom_validators(self, data: Dict[str, Any], field_index: List[Dict[str, Any]], errors: List[str]) -> None:
        """Apply custom validators to each field (no value transformation)."""
        for field_meta in field_index:
            field_path = self._build_field_path(field_meta)
            value = self._get_nested_value(data, field_path)
            
            if value is None:
                continue  # Skip null values (already validated by JSON schema)
            
            target_type = field_meta.get("target_type")
            if not target_type:
                continue
            
            # Get validator (instance overrides global)
            validator = self.__instance_validator_registry.get(target_type) or _get_validator(target_type)
            
            if validator:
                try:
                    # Instance validators use: (engine, value, field_metadata)
                    # Global validators use: (engine, value)
                    if target_type in self.__instance_validator_registry:
                        is_valid, error_msg = validator(self, value, field_meta)
                    else:
                        is_valid, error_msg = validator(self, value)
                    
                    if not is_valid and error_msg:
                        field_path_str = '.'.join(str(p) for p in field_path)
                        errors.append(f"{field_path_str}: {error_msg}")
                        
                except Exception as e:
                    field_path_str = '.'.join(str(p) for p in field_path)
                    logger.error(f"Validator error for {field_path_str}: {e}")
                    errors.append(f"{field_path_str}: Validator exception: {str(e)}")

    def _build_field_path(self, field_meta: Dict[str, Any]) -> List[str]:
        """Build path to field from metadata (e.g., ['fields', 'Patient Name'])."""
        level_keys = field_meta.get("level_keys", [])
        field_name = field_meta.get("name") or field_meta.get("key")
        return level_keys + [field_name]

    def _get_nested_value(self, data: Dict[str, Any], path: List[str]) -> Any:
        """Get value from nested dictionary using path."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    # --------------------------- Schema building ------------------------------

    # --------- Builder-facing helper APIs (to preserve encapsulation) ---------

    def build_property_node(
        self,
        target_type: str,
        *,
        prop: Optional[Dict[str, Any]] = None,
        enum_values: Optional[List[str]] = None,
        nullable: bool = True,
        property_def: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a property schema node via unified builder invocation (instance over global).
        Note: This helper is intended for builders to construct child field nodes (e.g., primitives)
        and must not participate in virtual-container expansion. We therefore intentionally ignore
        the (property_key_override, virtual_children_metadata) returned by _invoke_schema_builder
        to avoid any recursive expansion here; only the json_schema is returned to the caller.
        """
        _, json_schema, _ = self._invoke_schema_builder(target_type, enum_values, nullable, property_def or {}, prop or {})
        return json_schema

    def create_object_node(self, nullable: bool = False) -> Dict[str, Any]:
        """Create a base object node with additionalProperties=false and empty properties/required."""
        node: Dict[str, Any] = {
            "type": ["object", "null"] if nullable else "object",
            "additionalProperties": False,
            "properties": {},
            "required": [],
        }
        return node

    def add_properties(self, node: Dict[str, Any], properties: Dict[str, Any]) -> None:
        """Merge properties into an object node's properties."""
        node.setdefault("properties", {})
        node["properties"].update(properties)

    def set_required(self, node: Dict[str, Any], required: List[str]) -> None:
        """Set the required list on an object node."""
        node["required"] = required

    def _build_table_schema(self, external_schema: Dict[str, Any], table_name: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, int]]:
        """Build the table JSON schema and collect bottom-level field index.
        
        Returns:
            Tuple of (json_schema, field_index, container_counts)
            container_counts: dict mapping container_name -> count for top-level containers
        """
        if not isinstance(external_schema, dict):
            raise TypeError("external_schema must be a dict")

        table_title = table_name  # Title is the same as name for now

        # Check if this is a flat schema (direct properties) or nested schema (container)
        if "properties" in self.__meta_schema:
            # Flat schema - properties are at the root level
            return self._build_flat_schema(external_schema, table_name, table_title)
        elif "container" in self.__meta_schema:
            # Nested schema - properties are in containers
            return self._build_nested_schema(external_schema, table_name, table_title)
        else:
            raise ValueError("Meta-schema must contain either 'properties' or 'container'")

    def _build_flat_schema(self, external_schema: Dict[str, Any], table_name: str, table_title: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, int]]:
        """Build JSON schema for flat structure (no containers)."""
        properties_def = self.__meta_schema["properties"]
        properties_name = properties_def["properties_name"]
        property_def = properties_def["property"]
        
        # Get the properties array from external schema
        properties_array = external_schema.get(properties_name, [])
        if not isinstance(properties_array, list):
            raise ValueError(f"Expected array at '{properties_name}', got {type(properties_array)}")

        # Use unified property processing with properties_name as level_keys
        item_properties, item_required, field_index = self._process_properties(properties_array, property_def, level_keys=[properties_name])

        # Create root object with properties_name container (same as nested structure)
        root: Dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "title": table_title,  # Add title from schema_name field
            "properties": {
                "table_name": {
                    "type": "string",
                    "const": table_title,
                    "description": "The name of the table"
                },
                properties_name: {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": item_properties,
                    "required": item_required
                }
            },
            "required": ["table_name", properties_name],
        }

        return root, field_index, {}

    def _build_nested_schema(self, external_schema: Dict[str, Any], table_name: str, table_title: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, int]]:
        """Build JSON schema for nested structure (with containers) - object-based approach."""
        container_def = self.__meta_schema["container"]
        container_name = container_def["container_name"]
        
        # Get the container array from external schema
        container_array = external_schema.get(container_name, [])
        if not isinstance(container_array, list):
            raise ValueError(f"Expected array at '{container_name}', got {type(container_array)}")

        # Calculate container count for top-level container
        container_counts = {container_name: len(container_array)}

        # Build the root object schema with object-based container
        root_properties: Dict[str, Any] = {}
        root_required: List[str] = []
        field_index: List[Dict[str, Any]] = []

        # Build object-based container schema (not array-based)
        container_schema, collected_fields = self._build_container_object(container_def["object"], container_array, [container_name])
        field_index.extend(collected_fields)

        root_properties[container_name] = container_schema
        root_required.append(container_name)

        root: Dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "title": table_title,  # Add title from schema_name field
            "properties": {
                "table_name": {
                    "type": "string",
                    "const": table_title,
                    "description": "The name of the table"
                },
                **root_properties
            },
            "required": ["table_name"] + root_required,
        }

        return root, field_index, container_counts

    def _process_properties(self, properties_array: List[Dict[str, Any]], property_def: Dict[str, Any], level_keys: List[str]) -> Tuple[Dict[str, Any], List[str], List[Dict[str, Any]]]:
        """Unified method to process properties array and build field schemas."""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        field_index: List[Dict[str, Any]] = []

        # Process each property
        for prop in properties_array:
            field_key = prop.get(property_def["key"])
            if not field_key:
                raise ValueError(f"Property missing required key '{property_def['key']}'")
            
            # Get field name/title and sanitize (use name if available, fallback to key)
            name_field_key = property_def.get("name", "")
            title_field_key = property_def.get("title", "")
            field_name = self._sanitize_for_json(prop.get(name_field_key, field_key))
            field_title_value = self._sanitize_for_json(prop.get(title_field_key, "") if title_field_key else "")
            
            # Build field schema (returns tuple including optional virtual_children_metadata)
            property_key_override, json_schema, target_type, virtual_children_metadata = self._build_property_schema(prop, property_def)
            
            # Skip this field entirely if builder returned None triplet (empty dict signal)
            if property_key_override is None and json_schema is None and target_type is None:
                continue
            
            # Use override if provided, otherwise use field_name
            property_key = property_key_override if property_key_override else field_name
            
            properties[property_key] = json_schema
            required.append(property_key)
            
            # Get original schema type from property
            type_field = property_def["type"]
            original_schema_type = prop.get(type_field)
            
            # Collect field metadata using meta-schema field names
            field_metadata: Dict[str, Any] = {
                "key": field_key,
                "level_keys": level_keys.copy(),
                "target_type": target_type,
                "original_schema_type": original_schema_type,  # Add original schema type for formatter access
                "field_schema": prop,
                "property_key": property_key,  # Add this for reverse mapping
                # Optional fields captured explicitly (sanitized for name/title)
                "id": prop.get(property_def.get("id", ""), "") if "id" in property_def else "",
                "name": field_name,
                "title": field_title_value,
            }
            
            # Add container key_field if this is a container level
            # Extract container key fields from meta-schema dynamically
            if len(level_keys) > 0:
                key_field = self._extract_container_key_field(level_keys)
                if key_field:
                    field_metadata["key_field"] = key_field
            
            # If builder returned virtual children, mark container
            if virtual_children_metadata:
                field_metadata["is_virtual_container"] = True
                field_metadata["expanded_children"] = [m.get("child_property_name") for m in virtual_children_metadata if m.get("child_property_name")]

            # Append container metadata first (so container appears before children)
            field_index.append(field_metadata)

            # If virtual children present, compose and append child metadata
            if virtual_children_metadata:
                # Compute child level keys (include this container's property key)
                virtual_container_level_keys = level_keys.copy()
                virtual_container_level_keys.append(property_key)
                
                # Derive optional id/title from parent for consistency
                parent_id_value = prop.get(property_def.get("id", ""), "") if "id" in property_def else ""
                parent_title_value = prop.get(property_def.get("title", ""), "") if "title" in property_def else ""
                # Sanitize parent title to ensure no HTML tags propagate to children metadata
                parent_title_value = self._sanitize_for_json(parent_title_value)
                
                for child in virtual_children_metadata:
                    child_name = child.get("child_property_name")
                    if not child_name:
                        continue
                    child_meta: Dict[str, Any] = {
                        "key": field_key,
                        "level_keys": virtual_container_level_keys.copy(),
                        "target_type": child.get("target_type", "string"),
                        "original_schema_type": original_schema_type,  # Inherit original schema type from parent
                        "field_schema": prop,  # reference parent field schema
                        "property_key": child_name,
                        "id": parent_id_value,
                        "name": child_name,
                        "title": parent_title_value,
                        "is_virtual_container_child": True,
                        "virtual_container_key": field_key,
                    }
                    # Merge custom child fields (e.g., response_value, child_index)
                    for k, v in child.items():
                        if k not in {"child_property_name", "target_type"}:
                            child_meta[k] = v
                    field_index.append(child_meta)

        return properties, required, field_index

    def _build_container_object(self, object_def: Dict[str, Any], container_array: List[Dict[str, Any]], level_keys: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build JSON schema for container as object with key.name property names."""
        # Container object with properties for each item
        container_obj: Dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "required": [],
        }

        collected: List[Dict[str, Any]] = []

        # Check if this object has properties (bottom level) or another container (nested level)
        if "properties" in object_def:
            # Bottom level - process properties using unified method
            properties_def = object_def["properties"]
            properties_name = properties_def["properties_name"]
            property_def = properties_def["property"]
            
            # Process each item in the container
            for item in container_array:
                # Get the current level's key and name for property naming
                current_level_key = None
                current_level_name = None
                if "key" in object_def:
                    current_level_key = item.get(object_def["key"])
                if "name" in object_def:
                    current_level_name = self._sanitize_for_json(item.get(object_def["name"]))
                
                # Early exit: Skip items without key
                if not current_level_key:
                    continue
                
                # Early exit: Skip items without properties array
                properties_array = item.get(properties_name, [])
                if not isinstance(properties_array, list):
                    continue
                
                # Create property name using key.name format
                if current_level_name:
                    property_name = f"{current_level_key}.{current_level_name}"
                else:
                    property_name = current_level_key
                
                # Update level keys for property processing
                updated_level_keys = level_keys.copy()
                updated_level_keys.append(property_name)  # Use property_name, not current_level_key
                # Add properties_name to level_keys for consistency
                updated_level_keys.append(properties_name)
                
                # Use unified property processing with updated level keys
                item_properties, item_required, item_field_index = self._process_properties(properties_array, property_def, updated_level_keys)
                
                # Create the item object with explicit properties container
                item_obj = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        properties_name: {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": item_properties,
                            "required": item_required
                        }
                    },
                    "required": [properties_name]
                }
                
                # Add this item as a property to the container
                container_obj["properties"][property_name] = item_obj
                container_obj["required"].append(property_name)
                
                # Collect field metadata
                collected.extend(item_field_index)

        elif "container" in object_def:
            # Nested level - process nested container
            nested_container_def = object_def["container"]
            nested_container_name = nested_container_def["container_name"]
            
            # Process each item in the container
            for item in container_array:
                # Get the current level's key and name for property naming
                current_level_key = None
                current_level_name = None
                if "key" in object_def:
                    current_level_key = item.get(object_def["key"])
                if "name" in object_def:
                    current_level_name = self._sanitize_for_json(item.get(object_def["name"]))
                
                # Create property name using key.name format
                if current_level_key and current_level_name:
                    property_name = f"{current_level_key}.{current_level_name}"
                elif current_level_key:
                    property_name = current_level_key
                else:
                    continue  # Skip items without key
                
                # Update level keys for nested processing
                updated_level_keys = level_keys.copy()
                if current_level_key and current_level_name:
                    updated_level_keys.append(f"{current_level_key}.{current_level_name}")
                elif current_level_key:
                    updated_level_keys.append(current_level_key)
                
                # Get the nested container array from this item
                nested_container_array = item.get(nested_container_name, [])
                if not isinstance(nested_container_array, list):
                    continue
                
                # Build nested container object with updated level keys (include nested_container_name)
                nested_level_keys = updated_level_keys.copy()
                nested_level_keys.append(nested_container_name)
                nested_container_schema, nested_collected = self._build_container_object(
                    nested_container_def["object"], nested_container_array, nested_level_keys
                )
                collected.extend(nested_collected)
                
                # Create the item object with explicit nested container
                item_obj = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        nested_container_name: nested_container_schema
                    },
                    "required": [nested_container_name]
                }
                
                # Add this item as a property to the container
                container_obj["properties"][property_name] = item_obj
                container_obj["required"].append(property_name)

        return container_obj, collected

    def _build_property_schema(self, prop: Dict[str, Any], property_def: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any], str, List[Dict[str, Any]]]:
        """Build JSON schema for a single property.
        
        Returns:
            Tuple of (property_key_override, json_schema, target_type, virtual_children_metadata)
            property_key_override is None when no override is needed
        """
        # Get field type from property
        type_field = property_def["type"]
        field_type = prop.get(type_field)
        if not field_type:
            raise ValueError(f"Property missing required type field '{type_field}'")

        # Get validation rules from meta-schema
        validation = property_def.get("validation", {})
        allowed_types = validation.get("allowed_types", [])
        ignored_types = validation.get("ignored_types", [])
        type_constraints = validation.get("type_constraints", {})

        # Skip ignored types entirely
        if ignored_types and field_type in ignored_types:
            return None, None, None, []

        # Validate field type
        if allowed_types and field_type not in allowed_types:
            raise ValueError(f"Field type '{field_type}' not in allowed types: {allowed_types}")

        # Get type constraint
        type_constraint = type_constraints.get(field_type)
        if not type_constraint:
            raise ValueError(f"No type constraint found for field type '{field_type}'")

        # Get target type
        target_type = type_constraint.get("target_type")
        if not target_type:
            raise ValueError(f"No target_type defined for field type '{field_type}'")

        # Check if options are required
        requires_options = type_constraint.get("requires_options", False)
        options_field = type_constraint.get("options_field")
        options_extractor_name = type_constraint.get("options_extractor")

        # Get options if needed
        enum_values = None
        if requires_options and options_field:
            options = prop.get(options_field)
            if options is None:
                raise ValueError(f"Field type '{field_type}' requires options but none provided")
            
            # Handle simple list[str] options directly
            if isinstance(options, list) and all(isinstance(item, str) for item in options):
                enum_values = [self._sanitize_for_json(v) for v in options]
            elif options_extractor_name:
                # Use extractor function
                extractor_func = self.__options_extractor_registry.get(options_extractor_name)
                if not extractor_func:
                    raise ValueError(f"Extractor function '{options_extractor_name}' not registered")
                enum_values = extractor_func(options)
                if not isinstance(enum_values, list) or not all(isinstance(v, str) for v in enum_values):
                    raise ValueError("Extractor function must return List[str]")
                # Sanitize returned enum strings
                enum_values = [self._sanitize_for_json(v) for v in enum_values]
            else:
                raise ValueError(f"Field type '{field_type}' requires options but no extractor provided")

        # Build schema using unified builder invocation (instance overrides global)
        property_key_override, json_schema, virtual_children_metadata = self._invoke_schema_builder(
            target_type, enum_values, True, property_def, prop
        )
        
        # Check if builder returned empty dict (skip signal)
        if json_schema == {}:
            return None, None, None, []
        
        return property_key_override, json_schema, target_type, virtual_children_metadata

    def _invoke_schema_builder(
        self,
        target_type: str,
        enum_values: Optional[List[str]],
        nullable: bool,
        property_def: Dict[str, Any],
        prop: Dict[str, Any],
    ) -> Tuple[Optional[str], Dict[str, Any], List[Dict[str, Any]]]:
        """Invoke instance or global schema builder and normalize its return.
        Returns (property_key_override, json_schema, virtual_children_metadata).
        """
        # Prefer instance builder
        builder = self.__instance_field_schema_builder_registry.get(target_type)
        is_instance = True
        if not builder:
            builder = _get_field_schema_builder(target_type)
            is_instance = False
        if not builder:
            raise ValueError(f"No schema builder found for target type '{target_type}'")

        try:
            if is_instance:
                result = builder(self, target_type, enum_values, nullable, property_def, prop)
            else:
                result = builder(self, target_type, enum_values, nullable, property_def, prop)

            property_key_override: Optional[str] = None
            virtual_children_metadata: List[Dict[str, Any]] = []

            if isinstance(result, tuple) and len(result) == 2:
                first, second = result
                if isinstance(first, str) and isinstance(second, dict):
                    property_key_override, json_schema = first, second
                elif isinstance(first, dict) and isinstance(second, list):
                    json_schema = first
                    virtual_children_metadata = second
                else:
                    json_schema = first if isinstance(first, dict) else second
            else:
                json_schema = result

            return property_key_override, json_schema, virtual_children_metadata
        except Exception as e:
            who = 'Instance' if is_instance else 'Global'
            logger.error(f"{who} schema builder error for type '{target_type}': {e}")
            raise ValueError(f"{who} schema builder error for type '{target_type}': {e}")

    # ----------------------------- Helpers ------------------------------------

    def __validate_meta_schema(self, meta_schema: Dict[str, Any]) -> None:
        """Validate that the meta-schema language definition conforms to our syntax."""
        if not isinstance(meta_schema, dict):
            raise ValueError("Meta-schema must be a dictionary")
        
        # Check mandatory fields
        if "schema_name" not in meta_schema:
            raise ValueError("Meta-schema must contain 'schema_name' field")
        
        # Check that either 'properties' or 'container' is present (but not both)
        has_properties = "properties" in meta_schema
        has_container = "container" in meta_schema
        
        if not (has_properties or has_container):
            raise ValueError("Meta-schema must contain either 'properties' or 'container'")
        
        if has_properties and has_container:
            raise ValueError("Meta-schema cannot contain both 'properties' and 'container'")
        
        # Validate flat schema structure
        if has_properties:
            self._validate_properties_schema(meta_schema["properties"])
        
        # Validate nested schema structure
        if has_container:
            self._validate_container_schema(meta_schema["container"])
    
    def _validate_properties_schema(self, properties_def: Dict[str, Any]) -> None:
        """Validate the properties definition for flat schemas."""
        if not isinstance(properties_def, dict):
            raise ValueError("Properties definition must be a dictionary")
        
        if "properties_name" not in properties_def:
            raise ValueError("Properties definition must contain 'properties_name'")
        
        if "property" not in properties_def:
            raise ValueError("Properties definition must contain 'property'")
        
        self._validate_property_definition(properties_def["property"])
    
    def _validate_container_schema(self, container_def: Dict[str, Any]) -> None:
        """Validate the container definition for nested schemas."""
        if not isinstance(container_def, dict):
            raise ValueError("Container definition must be a dictionary")
        
        if "container_name" not in container_def:
            raise ValueError("Container definition must contain 'container_name'")
        
        if "object" not in container_def:
            raise ValueError("Container definition must contain 'object'")
        
        self._validate_object_definition(container_def["object"])
    
    def _validate_object_definition(self, object_def: Dict[str, Any]) -> None:
        """Validate an object definition (recursive for nested structures)."""
        if not isinstance(object_def, dict):
            raise ValueError("Object definition must be a dictionary")
        
        # Check that either 'properties' or 'container' is present (but not both)
        has_properties = "properties" in object_def
        has_container = "container" in object_def
        
        if not (has_properties or has_container):
            raise ValueError("Object definition must contain either 'properties' or 'container'")
        
        if has_properties and has_container:
            raise ValueError("Object definition cannot contain both 'properties' and 'container'")
        
        # Validate properties definition
        if has_properties:
            self._validate_properties_schema(object_def["properties"])
        
        # Validate nested container definition
        if has_container:
            self._validate_container_schema(object_def["container"])
    
    def _validate_property_definition(self, property_def: Dict[str, Any]) -> None:
        """Validate a property definition."""
        if not isinstance(property_def, dict):
            raise ValueError("Property definition must be a dictionary")
        
        # Check mandatory fields
        mandatory_fields = ["key", "name", "type"]
        for field in mandatory_fields:
            if field not in property_def:
                raise ValueError(f"Property definition must contain '{field}' field")
        
        # Validate validation rules if present
        if "validation" in property_def:
            validation = property_def["validation"]
            if not isinstance(validation, dict):
                raise ValueError("Validation rules must be a dictionary")
            
            if "allowed_types" not in validation:
                raise ValueError("Validation rules must contain 'allowed_types'")
            
            # Validate ignored_types if present
            if "ignored_types" in validation:
                ignored_types = validation["ignored_types"]
                if not isinstance(ignored_types, list):
                    raise ValueError("'ignored_types' must be a list")
                
                # Ensure mutual exclusion with allowed_types
                allowed_types = validation["allowed_types"]
                overlap = set(allowed_types) & set(ignored_types)
                if overlap:
                    raise ValueError(f"Types cannot be in both 'allowed_types' and 'ignored_types': {overlap}")
            
            if "type_constraints" not in validation:
                raise ValueError("Validation rules must contain 'type_constraints'")
            
            # After validating type_constraints structure, ensure ignored types are not in type_constraints
            if "ignored_types" in validation:
                ignored_types = validation["ignored_types"]
                type_constraints = validation["type_constraints"]
                overlap = set(ignored_types) & set(type_constraints.keys())
                if overlap:
                    raise ValueError(f"Ignored types should not have type_constraints defined: {overlap}")
            
            # Validate type constraints
            type_constraints = validation["type_constraints"]
            if not isinstance(type_constraints, dict):
                raise ValueError("Type constraints must be a dictionary")
            
            for field_type, constraint in type_constraints.items():
                if not isinstance(constraint, dict):
                    raise ValueError(f"Type constraint for '{field_type}' must be a dictionary")
                
                if "target_type" not in constraint:
                    raise ValueError(f"Type constraint for '{field_type}' must contain 'target_type'")
                
                if "requires_options" not in constraint:
                    raise ValueError(f"Type constraint for '{field_type}' must contain 'requires_options'")

    @staticmethod
    def _format_validation_error(err: jsonschema.exceptions.ValidationError) -> str:
        loc = ".".join([str(p) for p in err.path])
        if loc:
            return f"{loc}: {err.message}"
        return err.message

    def enrich_schema(self, table_name: str, enrichment_dict: Dict[str, str]) -> List[str]:
        """
        Enrich schema property descriptions with additional context.
        
        Args:
            table_name: The name of the registered table
            enrichment_dict: Dict mapping field keys to description text
        
        Returns:
            List of field keys that were not found in the schema
        
        Raises:
            ValueError: If table_name not registered
        """
        if table_name not in self.__table_names:
            raise ValueError(f"Table '{table_name}' not registered")
        
        table_id = self.__table_names[table_name]
        schema_data = self.__tables[table_id]
        json_schema = schema_data["json_schema"]
        field_index = schema_data["field_index"]
        
        unmatched_keys: List[str] = []
        
        # For each enrichment entry, find field in index and update description
        for field_key, enrichment_text in enrichment_dict.items():
            # Find field metadata
            field_meta = next((f for f in field_index if f.get("key") == field_key), None)
            if not field_meta:
                logger.warning(f"Field '{field_key}' not found in field index for table '{table_name}'")
                unmatched_keys.append(field_key)
                continue
            
            # Navigate to the property in json_schema using level_keys
            level_keys = field_meta.get("level_keys", [])
            property_key = field_meta.get("property_key")
            
            # Traverse to the property location
            current = json_schema
            for key in level_keys:
                current = current.get("properties", {}).get(key, {})
            
            # Update description
            if property_key and "properties" in current:
                prop_schema = current["properties"].get(property_key, {})
                existing_desc = prop_schema.get("description", "")
                if existing_desc:
                    prop_schema["description"] = f"{existing_desc}\n\n{enrichment_text}"
                else:
                    prop_schema["description"] = enrichment_text
        
        return unmatched_keys

    def reverse_map(
        self,
        table_name: str,
        model_response: Dict[str, Any],
        formatter_name: str = "default",
        group_by_containers: Optional[List[str]] = None,
        properties_key: str = "properties",
        pack_properties_as: str = "object",
        pack_containers_as: str = "array",
        metadata_field_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Map model response back to original external schema format using named formatter set.
        
        Args:
            table_name: The name of the registered table
            model_response: The JSON response from the model
            formatter_name: Name of formatter set to use (default: "default")
            group_by_containers: Optional list of container names to group by
                (e.g., ["sections"] groups answers by section)
            properties_key: Name for the innermost container (default: "properties")
            pack_properties_as: Format for the innermost container - either "object" or "array" (default: "object")
            pack_containers_as: Format for container nesting layers - either "array" or "object" (default: "array")
            metadata_field_overrides: Optional dict to customize metadata field names and values.
                Supports keys: "schema_name", "schema_id", "schema_type".
                Values can be strings (field names) or dicts with "name" and "value" keys.
                Example: {
                    "schema_name": "assessment_title",
                    "schema_id": "assessment_std_id",
                    "schema_type": {"name": "doc_type", "value": "pcc_assessment"}
                }
                Default: None (uses original meta-schema field names)
        
        Returns:
            Dictionary with schema metadata and formatted data:
            {
                <schema_type_field>: <schema_type_value>,  # if schema_type_value is not empty
                <schema_name_field>: <schema_name_value>,
                <schema_id_field>: <schema_id_value>,  # if defined in meta-schema
                "data": [
                    {
                        "properties": {...}  # for flat
                    }
                    # OR for grouped (pack_containers_as="array"):
                    {
                        <container_key>: <container_value>,
                        "properties": {...}
                    }
                    # OR for grouped (pack_containers_as="object"):
                    {
                        <container_key>: {
                            "properties": {...}
                        }
                    }
                ]
                # OR when pack_containers_as="object":
                "data": {
                    <container_key>: {
                        "properties": {...}
                    }
                }
            }
        
        Raises:
            ValueError: If table_name not registered, formatter_name not registered, pack_properties_as is invalid, or pack_containers_as is invalid
        """
        if table_name not in self.__table_names:
            raise ValueError(f"Table '{table_name}' not registered")
        
        # Validate formatter set exists
        if formatter_name not in self.__named_formatter_sets:
            raise ValueError(f"Formatter set '{formatter_name}' is not registered. "
                            f"Available formatter sets: {list(self.__named_formatter_sets.keys())}")
        
        # Validate pack_properties_as parameter
        if pack_properties_as not in ["object", "array"]:
            raise ValueError(f"pack_properties_as must be 'object' or 'array', got '{pack_properties_as}'")
        
        # Validate pack_containers_as parameter
        if pack_containers_as not in ["object", "array"]:
            raise ValueError(f"pack_containers_as must be 'object' or 'array', got '{pack_containers_as}'")
        
        table_id = self.__table_names[table_name]
        schema_data = self.__tables[table_id]
        field_index = schema_data["field_index"]
        external_schema = schema_data["external_schema"]
        
        # Step 1: Format fields as before
        formatted_results = {}
        for field_meta in field_index:
            if field_meta.get("is_virtual_container_child"):
                continue
            
            model_value = self._extract_model_value(model_response, field_meta)
            target_type = field_meta.get("target_type")
            
            if not target_type:
                logger.error(f"Field {field_meta.get('key', 'unknown')} missing target_type")
                formatted_results[field_meta.get("key", "unknown")] = {"type": "unknown", "value": None}
                continue
            
            field_result = self._format_field(field_meta, model_value, table_name, formatter_name)
            
            # Handle both dict (old style) and list (unpacking style) formatters
            if isinstance(field_result, list):
                # Formatter returned list of unpacked fields
                for item in field_result:
                    if isinstance(item, dict):
                        store_key = item.get("_storage_key", item.get("key"))
                        if store_key is not None:
                            # Keep the item intact; array packers will decide displayed key
                            formatted_results[store_key] = item
            elif isinstance(field_result, dict):
                # Formatter returned dict (existing behavior)
                formatted_results.update(field_result)
        
        # Step 2: Structure the data
        if group_by_containers:
            # Group by containers and rename "data" to properties_key
            grouped_data = self._group_by_containers(formatted_results, field_index, group_by_containers, properties_key, pack_properties_as, pack_containers_as)
        else:
            # Flat output: wrap in array with properties_key
            if pack_properties_as == "object":
                grouped_data = [{properties_key: formatted_results}]
            else:  # array
                array_properties = []
                for key, value in formatted_results.items():
                    display_key = (
                        value.get("_display_key")
                        if isinstance(value, dict) and value.get("_display_key") is not None
                        else (value.get("_original_field_key", key) if isinstance(value, dict) else key)
                    )
                    array_item = {"key": display_key}
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if k == "key" or (isinstance(k, str) and k.startswith("_")):
                                continue
                            array_item[k] = v
                    array_properties.append(array_item)
                grouped_data = [{properties_key: array_properties}]
        
        # Step 3: Extract schema metadata with overrides
        result = {}
        
        # Apply field name overrides (default to original meta-schema names)
        if metadata_field_overrides is None:
            metadata_field_overrides = {}
        
        # Handle schema_type (can be string with name or dict with name and value)
        schema_type_config = metadata_field_overrides.get("schema_type")
        if schema_type_config:
            if isinstance(schema_type_config, dict):
                schema_type_field = schema_type_config.get("name", "")
                schema_type_value = schema_type_config.get("value", "")
                if schema_type_field and schema_type_value:
                    result[schema_type_field] = schema_type_value
            elif isinstance(schema_type_config, str):
                # Just field name, no value - don't add
                pass
        
        # Add schema_name if defined
        schema_name_field = self.__meta_schema.get("schema_name")
        if schema_name_field and schema_name_field in external_schema:
            output_field_name = metadata_field_overrides.get("schema_name", schema_name_field)
            # Use override only if it's a non-empty string, otherwise use original
            if isinstance(output_field_name, str) and output_field_name:
                result[output_field_name] = external_schema[schema_name_field]
            elif output_field_name == schema_name_field or not output_field_name:
                # Fall back to original field name if override is empty or not provided
                result[schema_name_field] = external_schema[schema_name_field]
        
        # Add schema_id if defined
        schema_id_field = self.__meta_schema.get("schema_id")
        if schema_id_field and schema_id_field in external_schema:
            output_field_name = metadata_field_overrides.get("schema_id", schema_id_field)
            # Use override only if it's a non-empty string, otherwise use original
            if isinstance(output_field_name, str) and output_field_name:
                result[output_field_name] = external_schema[schema_id_field]
            elif output_field_name == schema_id_field or not output_field_name:
                # Fall back to original field name if override is empty or not provided
                result[schema_id_field] = external_schema[schema_id_field]
        
        # Add the formatted data
        data_name = group_by_containers[0] if group_by_containers  else "data"
        result[data_name] = grouped_data
        
        return result

    def _extract_model_value(self, model_response: Dict[str, Any], field_meta: Dict[str, Any]) -> Any:
        """Extract value from model response using field metadata."""
        level_keys = field_meta.get("level_keys", [])
        property_key = field_meta.get("property_key")
        
        # Traverse nested structure
        current = model_response
        for key in level_keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        
        # Get final property value
        if isinstance(current, dict) and property_key:
            return current.get(property_key)
        return None

    def _extract_container_key_field(self, level_keys: List[str]) -> Optional[str]:
        """
        Extract container key field from meta-schema based on level_keys.
        
        Args:
            level_keys: List of level keys representing the path to this field
            
        Returns:
            The key field name for the appropriate container level, or None if not found
        """
        if not level_keys:
            return None
        
        # Start from the meta-schema container definition
        container_def = self.__meta_schema.get("container")
        if not container_def:
            return None
        
        # Traverse the container hierarchy based on level_keys
        current_def = container_def
        level_index = 0
        
        while level_index < len(level_keys) and "object" in current_def:
            object_def = current_def["object"]
            
            # Check if this level has a key field
            if "key" in object_def:
                # This is a container level with a key field
                return object_def["key"]
            
            # Move to next level if there's a nested container
            if "container" in object_def:
                current_def = object_def["container"]
                level_index += 1
            else:
                # No more nested containers
                break
        
        return None

    def _format_field(self, field_meta: Dict[str, Any], model_value: Any, 
                      table_name: str, formatter_name: str) -> Dict[str, Any]:
        """Format a single field using the named formatter set."""
        original_schema_type = field_meta.get("original_schema_type")
        field_key = field_meta.get("key", "unknown")
        
        # Get formatter set
        formatter_set = self.__named_formatter_sets.get(formatter_name, {})
        
        # Look up formatter by original schema type ONLY
        formatter = formatter_set.get(original_schema_type)
        
        if not formatter:
            logger.error(f"No formatter for original type '{original_schema_type}' "
                        f"in formatter set '{formatter_name}' (field: {field_key})")
            return {}
        
        try:
            return formatter(self, field_meta, model_value, table_name)
        except Exception as e:
            logger.error(f"Error formatting field '{field_key}' with type '{original_schema_type}': {e}")
            return {}

    def _group_by_containers(
        self,
        formatted_results: Dict[str, Dict[str, Any]],
        field_index: List[Dict[str, Any]],
        container_names: List[str],
        properties_key: str = "properties",
        pack_properties_as: str = "object",
        pack_containers_as: str = "array"
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Group formatted results by container hierarchy.
        
        Args:
            formatted_results: Dict mapping field key to {"type": <label>, "value": <payload>}
            field_index: Field metadata index
            container_names: List of container names to group by (e.g., ["sections"])
            properties_key: Name for the innermost container (default: "properties")
            pack_properties_as: Format for the innermost container - either "object" or "array" (default: "object")
            pack_containers_as: Format for container layers - either "array" or "object" (default: "array")
        
        Returns:
            List of dicts when pack_containers_as="array", or Dict when pack_containers_as="object"
        """
        # Build mapping of field keys to their container paths
        key_to_container = {}
        for field_meta in field_index:
            field_key = field_meta.get("key")
            level_keys = field_meta.get("level_keys", [])
            key_field = field_meta.get("key_field")
            
            if not key_field:
                continue
            
            # Extract container path up to the grouping level
            container_path = []
            container_name = self.__meta_schema.get("container", {}).get("container_name")
            
            for i, level_key in enumerate(level_keys):
                # Check if this level matches the container name from meta-schema
                if level_key == container_name and i == 0:
                    # This is the top-level container - extract the actual container key
                    # The next level_key should be the container key (e.g., "A.Admission")
                    if i + 1 < len(level_keys):
                        container_key = level_keys[i + 1].split(".")[0]  # Extract "A" from "A.Admission"
                        container_path.append((container_key, field_meta))
                    break
            
            key_to_container[field_key] = container_path
        
        # Group results by container
        groups = {}
        for field_key, field_result in formatted_results.items():
            # Try to find container path for this field key
            container_path = key_to_container.get(field_key, [])
            
            # If not found, check if the field_result contains original field metadata
            if not container_path and isinstance(field_result, dict) and "_original_field_key" in field_result:
                original_field_key = field_result["_original_field_key"]
                container_path = key_to_container.get(original_field_key, [])
            
            if not container_path:
                # No container, skip or add to root
                continue
            
            # Use the last container in path as grouping key
            container_key, container_meta = container_path[-1]
            
            if container_key not in groups:
                # Create new group with container key field
                groups[container_key] = {
                    "_container_meta": container_meta,
                    "properties": {}
                }
            
            # Store full field_result; we'll strip internal metadata at output assembly time
            groups[container_key]["properties"][field_key] = field_result
        
        # Convert to list/dict and add container key fields
        if pack_containers_as == "array":
            # Existing array logic
            result = []
            for container_key, group_data in groups.items():
                container_meta = group_data["_container_meta"]
                
                # Get container key field name from meta-schema
                # The container's "key" field tells us which property holds the container identifier
                container_key_field = container_meta.get("key_field")  # e.g., "sectionCode"
                
                group = {}
                if container_key_field:
                    group[container_key_field] = container_key
                
                # Format properties based on pack_properties_as
                if pack_properties_as == "object":
                    group[properties_key] = group_data["properties"]
                else:  # array
                    array_properties = []
                    for key, value in group_data["properties"].items():
                        display_key = (
                            value.get("_display_key")
                            if isinstance(value, dict) and value.get("_display_key") is not None
                            else (value.get("_original_field_key", key) if isinstance(value, dict) else key)
                        )
                        array_item = {"key": display_key}
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if k == "key" or (isinstance(k, str) and k.startswith("_")):
                                    continue
                                array_item[k] = v
                        array_properties.append(array_item)
                    group[properties_key] = array_properties
                
                result.append(group)
            
            return result
        else:  # pack_containers_as == "object"
            # New object packing logic
            result = {}
            for container_key, group_data in groups.items():
                # Format properties based on pack_properties_as (same as array case)
                if pack_properties_as == "object":
                    properties_data = group_data["properties"]
                else:  # array
                    array_properties = []
                    for key, value in group_data["properties"].items():
                        display_key = (
                            value.get("_display_key")
                            if isinstance(value, dict) and value.get("_display_key") is not None
                            else (value.get("_original_field_key", key) if isinstance(value, dict) else key)
                        )
                        array_item = {"key": display_key}
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if k == "key" or (isinstance(k, str) and k.startswith("_")):
                                    continue
                                array_item[k] = v
                        array_properties.append(array_item)
                    properties_data = array_properties
                
                # Use container_key as the object key
                result[container_key] = {properties_key: properties_data}
            
            return result


# ----------------------------- Default Schema Builders -----------------------------

@_register_field_schema_builder("string")
def _string_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default string schema builder - always nullable."""
    return {"type": ["string", "null"]}


@_register_field_schema_builder("integer")
def _integer_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default integer schema builder - always nullable."""
    return {"type": ["integer", "null"]}


@_register_field_schema_builder("number")
def _number_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default number schema builder - always nullable."""
    return {"type": ["number", "null"]}

@_register_field_schema_builder("positive_number")
def _positive_number_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default positive number schema builder - always nullable."""
    return {"type": ["number", "null"], "minimum": 0}


@_register_field_schema_builder("positive_integer")
def _positive_integer_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default positive integer schema builder - always nullable, non-negative integers only."""
    return {"type": ["integer", "null"], "minimum": 0}


@_register_field_schema_builder("percent")
def _percent_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Percent schema builder - nullable number constrained to 0..100."""
    return {"type": ["number", "null"], "minimum": 0, "maximum": 100}


@_register_field_schema_builder("boolean")
def _boolean_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default boolean schema builder - always nullable."""
    return {"type": ["boolean", "null"]}


@_register_field_schema_builder("date")
def _date_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default date schema builder - always nullable."""
    return {"type": ["string", "null"], "format": "date", "description": "ISO 8601 date (YYYY-MM-DD)"}


@_register_field_schema_builder("datetime")
def _datetime_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default datetime schema builder - always nullable."""
    return {"type": ["string", "null"], "format": "date-time", "description": "ISO 8601 date-time (YYYY-MM-DDTHH:MM:SSZ)"}


@_register_field_schema_builder("single_select")
def _single_select_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default single_select schema builder - always nullable."""
    base = {"type": ["string", "null"], "description": "Select one of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"}
    if enum_values is not None:
        base["enum"] = enum_values + [None]  # Add None to enum values
    return base


@_register_field_schema_builder("multiple_select")
def _multiple_select_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default multiple_select schema builder - always nullable."""
    base = {
        "type": ["array", "null"],
        "items": {"type": ["string", "null"]},
        "description": "Select one or more of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"
    }
    if enum_values is not None:
        base["items"]["enum"] = enum_values + [None]
    return base

@_register_field_schema_builder("currency")
def _currency_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Currency schema builder - nullable number with hint about precision."""
    # We don't encode precision constraints here; description guides the model.
    return {"type": ["number", "null"], "description": "Currency - must be a number with up to 2 decimal precision"}


@_register_field_schema_builder("array")
def _array_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default array schema builder - always nullable."""
    return {"type": ["array", "null"]}


@_register_field_schema_builder("object")
def _object_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Default object schema builder - always nullable."""
    return {"type": ["object", "null"]}


@_register_field_schema_builder("instructions")
def _instructions_schema_builder(engine: SchemaEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool, property_def: Dict[str, Any], field_schema: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Schema builder for instruction fields - creates const string field for context.
    Returns a tuple (property_key, schema) to override the property key.
    """
    # Extract field names from meta-schema property definition
    id_field = property_def.get("id", "")
    title_field = property_def.get("title", "")
    name_field = property_def.get("name", "")
    
    # Extract actual values from field schema
    id_value = field_schema.get(id_field, "") if id_field else ""
    # Sanitize title and name to strip any HTML tags at ingestion time
    raw_title_value = field_schema.get(title_field, "") if title_field else ""
    raw_name_value = field_schema.get(name_field, "") if name_field else ""
    title_value = engine._sanitize_for_json(raw_title_value)
    name_value = engine._sanitize_for_json(raw_name_value)
    
    # Build property key: "<id>.Instructions" if id exists, else "Instructions"
    if id_value:
        property_key = f"{id_value}.Instructions"
    else:
        property_key = "Instructions"
    
    # Build const value from sanitized title and name with ". " separator
    if title_value and name_value:
        const_value = f"{title_value}. {name_value}"
    elif title_value:
        const_value = title_value
    else:
        const_value = name_value
    
    schema = {
        "type": "string",
        "const": const_value,
        "description": "These are instructions that should be used as context for other properties of the same schema object and adjacent schema objects."
    }
    
    # Return tuple: (property_key_override, schema)
    return (property_key, schema)


# ----------------------------- Default Validators -----------------------------

@_register_validator("date")
def _date_validator(engine: SchemaEngine, value: Any) -> Tuple[bool, str]:
    """Validate ISO date format."""
    if not isinstance(value, str):
        return False, f"Date must be a string, got {type(value)}"
    try:
        from datetime import datetime
        datetime.fromisoformat(value)
        return True, ""
    except ValueError:
        return False, f"Invalid ISO date format: {value}"


@_register_validator("datetime")
def _datetime_validator(engine: SchemaEngine, value: Any) -> Tuple[bool, str]:
    """Validate ISO datetime format."""
    if not isinstance(value, str):
        return False, f"DateTime must be a string, got {type(value)}"
    try:
        from datetime import datetime
        # Replace 'Z' with '+00:00' to use datetime.fromisoformat
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        datetime.fromisoformat(value)
        return True, ""
    except ValueError:
        return False, f"Invalid ISO datetime format: {value}"


@_register_validator("single_select")
def _single_select_validator(engine: SchemaEngine, value: Any) -> Tuple[bool, str]:
    """Validate single_select enum value."""
    # JSON Schema already validates enum membership, so this is just for additional checks
    return True, ""


@_register_validator("multiple_select")
def _multiple_select_validator(engine: SchemaEngine, value: Any) -> Tuple[bool, str]:
    """Validate multiple_select array values."""
    # JSON Schema already validates array and enum membership, so this is just for additional checks
    return True, ""




