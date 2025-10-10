"""
SchemaConverterEngine: database-agnostic schema conversion and validation engine.

Design highlights:
- One engine instance per external "schema language". All tables registered to an engine
  share the same field type mapping and per-type options extractors.
- The engine converts an external table schema (with up to 5 nesting levels) into an
  OpenAI-compatible JSON Schema subset and validates data against it.
- All bottom-level fields are listed in `required`. Optionality is expressed via
  union types that include "null". Objects always set `additionalProperties` to false.
- Supports target field types: string, integer, number, boolean, date, datetime,
  singleSelect, multipleSelect, array, object.
- Uses function registries for schema builders and validators (per target type).

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
            "allowed_types": ["type1", "type2", ...], // mandatory
            "type_constraints": { // mandatory
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
                    "target_type": "singleSelect",
                    "requires_options": true,
                    "options_field": "responseOptions",
                    "options_extractor": "extract_response_options"
                  },
                  "radh": {
                    "target_type": "singleSelect",
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
engine = SchemaConverterEngine(schema_language_definition)

# Register individual tables using the external schema language
engine.register_table("mds_assessment", "MDS 2.0 Full Assessment", pointclickcare_schema)

# Get OpenAI-compatible JSON schema
json_schema = engine.get_json_schema("mds_assessment")

# Validate data against the schema
is_valid, errors = engine.validate("mds_assessment", data)
```

Notes:
- Max tables per engine instance: 1000 (re-registration allowed; replaces previous
  table with same id and logs info).
- Level keys are captured at every nesting level for reverse conversion.
- Options can be simple list[str] or complex (requiring extractor function).
- The engine stores both `key` and `id` for bottom-level fields (for reverse mapping).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

try:
    # Prefer modern validator if available
    import jsonschema
    from jsonschema import Draft202012Validator as DefaultValidator
except Exception:  # pragma: no cover - fallback if version not available
    import jsonschema
    from jsonschema import Draft7Validator as DefaultValidator


logger = logging.getLogger(__name__)


MAX_TABLES_PER_ENGINE = 1000
MAX_NESTING_LEVELS = 5

# Function registries for schema builders and validators
_schema_builder_registry: Dict[str, Callable] = {}
_validator_registry: Dict[str, Callable] = {}


def register_schema_builder(internal_type: str):
    """Decorator to register a schema builder function for an internal field type."""
    def decorator(func: Callable):
        _schema_builder_registry[internal_type] = func
        return func
    return decorator


def register_validator(internal_type: str):
    """Decorator to register a validator function for an internal field type."""
    def decorator(func: Callable):
        _validator_registry[internal_type] = func
        return func
    return decorator


def get_schema_builder(internal_type: str) -> Optional[Callable]:
    """Get the schema builder function for an internal field type."""
    return _schema_builder_registry.get(internal_type)


def get_validator(internal_type: str) -> Optional[Callable]:
    """Get the validator function for an internal field type."""
    return _validator_registry.get(internal_type)


class SchemaConverterEngine:
    """Engine that converts external schemas to OpenAI-compatible JSON Schema and validates data."""

    def __init__(self, meta_schema_language: Dict[str, Any]) -> None:
        """
        Initialize a schema conversion engine for one external "schema language".

        Args:
            meta_schema_language: Meta-schema definition describing the external schema language structure.
        """
        # Validate meta-schema language structure
        self._validate_meta_schema(meta_schema_language)
        
        self._meta_schema = meta_schema_language
        self._options_extractor_registry: Dict[str, Callable] = {}

        # Table registry: table_id -> registry record
        self._tables: Dict[str, Dict[str, Any]] = {}

    # ----------------------------- Public API ---------------------------------

    def register_options_extractor(self, extractor_name: str, extractor_func: Callable[[Any], List[str]]) -> None:
        """Register an options extractor function."""
        self._options_extractor_registry[extractor_name] = extractor_func

    def register_table(self, table_id: str, external_schema: Dict[str, Any]) -> None:
        """Register (or re-register) a table schema.

        Re-registration replaces the previous entry with info logging.
        Enforces a maximum of 1000 tables per engine instance.
        """
        if table_id in self._tables:
            logger.info("Re-registering table_id=%s; replacing previous schema", table_id)
        elif len(self._tables) >= MAX_TABLES_PER_ENGINE:
            raise ValueError(f"Maximum number of tables reached: {MAX_TABLES_PER_ENGINE}")

        json_schema, field_index = self._build_table_schema(external_schema)

        self._tables[table_id] = {
            "external_schema": external_schema,
            "json_schema": json_schema,
            "field_index": field_index,  # list of {key, id, level_keys}
        }

    def unregister_table(self, table_id: str) -> None:
        self._tables.pop(table_id, None)

    def list_tables(self) -> List[str]:
        return list(self._tables.keys())

    def clear(self) -> None:
        self._tables.clear()

    def get_json_schema(self, table_id: str) -> Dict[str, Any]:
        rec = self._tables.get(table_id)
        if not rec:
            raise KeyError(f"Unknown table_id: {table_id}")
        return rec["json_schema"]

    def validate(self, table_id: str, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate data against the registered JSON schema.

        Returns (is_valid, errors).
        """
        rec = self._tables.get(table_id)
        if not rec:
            raise KeyError(f"Unknown table_id: {table_id}")
        schema = rec["json_schema"]
        validator = DefaultValidator(schema)
        errors = [self._format_validation_error(e) for e in validator.iter_errors(data)]
        return (len(errors) == 0), errors

    # --------------------------- Schema building ------------------------------

    def _build_table_schema(self, external_schema: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build the table JSON schema and collect bottom-level field index."""
        if not isinstance(external_schema, dict):
            raise TypeError("external_schema must be a dict")

        # Get table metadata from external schema using meta-schema field names
        schema_name_field = self._meta_schema.get("schema_name")
        table_name = external_schema.get(schema_name_field, "Unknown Table") if schema_name_field else "Unknown Table"
        table_title = external_schema.get(schema_name_field, "Unknown Table") if schema_name_field else "Unknown Table"

        # Check if this is a flat schema (direct properties) or nested schema (container)
        if "properties" in self._meta_schema:
            # Flat schema - properties are at the root level
            return self._build_flat_schema(external_schema, table_name, table_title)
        elif "container" in self._meta_schema:
            # Nested schema - properties are in containers
            return self._build_nested_schema(external_schema, table_name, table_title)
        else:
            raise ValueError("Meta-schema must contain either 'properties' or 'container'")

    def _build_flat_schema(self, external_schema: Dict[str, Any], table_name: str, table_title: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build JSON schema for flat structure (no containers)."""
        properties_def = self._meta_schema["properties"]
        properties_name = properties_def["properties_name"]
        property_def = properties_def["property"]
        
        # Get the properties array from external schema
        properties_array = external_schema.get(properties_name, [])
        if not isinstance(properties_array, list):
            raise ValueError(f"Expected array at '{properties_name}', got {type(properties_array)}")

        # Use unified property processing
        item_properties, field_index = self._process_properties(properties_array, property_def, [])

        # Create root object with properties_name container (same as nested structure)
        root: Dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "title": table_title,  # Add title from schema_name field
            "properties": {
                properties_name: {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": item_properties,
                    "required": list(item_properties.keys())
                }
            },
            "required": [properties_name],
        }

        return root, field_index

    def _build_nested_schema(self, external_schema: Dict[str, Any], table_name: str, table_title: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Build JSON schema for nested structure (with containers) - object-based approach."""
        container_def = self._meta_schema["container"]
        container_name = container_def["container_name"]
        
        # Get the container array from external schema
        container_array = external_schema.get(container_name, [])
        if not isinstance(container_array, list):
            raise ValueError(f"Expected array at '{container_name}', got {type(container_array)}")

        # Build the root object schema with object-based container
        root_properties: Dict[str, Any] = {}
        root_required: List[str] = []
        field_index: List[Dict[str, Any]] = []

        # Build object-based container schema (not array-based)
        container_schema, collected_fields = self._build_container_object(container_def["object"], container_array, [])
        field_index.extend(collected_fields)

        root_properties[container_name] = container_schema
        root_required.append(container_name)

        root: Dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "title": table_title,  # Add title from schema_name field
            "properties": root_properties,
            "required": root_required,
        }

        return root, field_index

    def _process_properties(self, properties_array: List[Dict[str, Any]], property_def: Dict[str, Any], level_keys: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Unified method to process properties array and build field schemas."""
        properties: Dict[str, Any] = {}
        field_index: List[Dict[str, Any]] = []

        # Process each property
        for prop in properties_array:
            field_key = prop.get(property_def["key"])
            if not field_key:
                raise ValueError(f"Property missing required key '{property_def['key']}'")
            
            # Get field name for JSON schema property name (use name if available, fallback to key)
            field_name = prop.get(property_def.get("name", ""), field_key)
            
            # Build field schema
            field_schema = self._build_property_schema(prop, property_def)
            properties[field_name] = field_schema
            
            # Collect field metadata using meta-schema field names
            field_metadata = {
                "key": field_key,
                "level_keys": level_keys.copy(),
                # Add optional fields if they exist in meta-schema using dictionary comprehension
                **{k: prop.get(property_def[k], "") for k in ["id", "name", "title"] if k in property_def}
            }
                
            field_index.append(field_metadata)

        return properties, field_index

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
                    current_level_name = item.get(object_def["name"])
                
                # Create property name using key.name format
                if current_level_key and current_level_name:
                    property_name = f"{current_level_key}.{current_level_name}"
                elif current_level_key:
                    property_name = current_level_key
                else:
                    continue  # Skip items without key
                
                # Update level keys for property processing
                updated_level_keys = level_keys.copy()
                if current_level_key:
                    updated_level_keys.append(current_level_key)
                
                # Get the properties array from this item
                properties_array = item.get(properties_name, [])
                if not isinstance(properties_array, list):
                    continue
                
                # Use unified property processing with updated level keys
                item_properties, item_field_index = self._process_properties(properties_array, property_def, updated_level_keys)
                
                # Create the item object with explicit properties container
                item_obj = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        properties_name: {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": item_properties,
                            "required": list(item_properties.keys())
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
                    current_level_name = item.get(object_def["name"])
                
                # Create property name using key.name format
                if current_level_key and current_level_name:
                    property_name = f"{current_level_key}.{current_level_name}"
                elif current_level_key:
                    property_name = current_level_key
                else:
                    continue  # Skip items without key
                
                # Update level keys for nested processing
                updated_level_keys = level_keys.copy()
                if current_level_key:
                    updated_level_keys.append(current_level_key)
                
                # Get the nested container array from this item
                nested_container_array = item.get(nested_container_name, [])
                if not isinstance(nested_container_array, list):
                    continue
                
                # Build nested container object with updated level keys
                nested_container_schema, nested_collected = self._build_container_object(
                    nested_container_def["object"], nested_container_array, updated_level_keys
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

    def _build_property_schema(self, prop: Dict[str, Any], property_def: Dict[str, Any]) -> Dict[str, Any]:
        """Build JSON schema for a single property."""
        # Get field type from property
        type_field = property_def["type"]
        field_type = prop.get(type_field)
        if not field_type:
            raise ValueError(f"Property missing required type field '{type_field}'")

        # Get validation rules from meta-schema
        validation = property_def.get("validation", {})
        allowed_types = validation.get("allowed_types", [])
        type_constraints = validation.get("type_constraints", {})

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
                enum_values = options
            elif options_extractor_name:
                # Use extractor function
                extractor_func = self._options_extractor_registry.get(options_extractor_name)
                if not extractor_func:
                    raise ValueError(f"Extractor function '{options_extractor_name}' not registered")
                enum_values = extractor_func(options)
                if not isinstance(enum_values, list) or not all(isinstance(v, str) for v in enum_values):
                    raise ValueError("Extractor function must return List[str]")
            else:
                raise ValueError(f"Field type '{field_type}' requires options but no extractor provided")

        # Build schema using registry
        schema_builder = get_schema_builder(target_type)
        if schema_builder:
            try:
                return schema_builder(self, target_type, enum_values, True)  # Always nullable
            except Exception as e:
                logger.error(f"Schema builder error for type '{target_type}': {e}")
                raise ValueError(f"Schema builder error for type '{target_type}': {e}")
        else:
            raise ValueError(f"No schema builder found for target type '{target_type}'")

    # ----------------------------- Helpers ------------------------------------

    def _validate_meta_schema(self, meta_schema: Dict[str, Any]) -> None:
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
            
            if "type_constraints" not in validation:
                raise ValueError("Validation rules must contain 'type_constraints'")
            
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


# ----------------------------- Default Schema Builders -----------------------------

@register_schema_builder("string")
def _string_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default string schema builder - always nullable."""
    return {"type": ["string", "null"]}


@register_schema_builder("integer")
def _integer_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default integer schema builder - always nullable."""
    return {"type": ["integer", "null"]}


@register_schema_builder("number")
def _number_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default number schema builder - always nullable."""
    return {"type": ["number", "null"]}

@register_schema_builder("percent")
def _percent_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Percent schema builder - nullable number constrained to 0..100."""
    return {"type": ["number", "null"], "minimum": 0, "maximum": 100}


@register_schema_builder("boolean")
def _boolean_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default boolean schema builder - always nullable."""
    return {"type": ["boolean", "null"]}


@register_schema_builder("date")
def _date_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default date schema builder - always nullable."""
    return {"type": ["string", "null"], "format": "date", "description": "ISO 8601 date (YYYY-MM-DD)"}


@register_schema_builder("datetime")
def _datetime_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default datetime schema builder - always nullable."""
    return {"type": ["string", "null"], "format": "date-time", "description": "ISO 8601 date-time (YYYY-MM-DDTHH:MM:SSZ)"}


@register_schema_builder("singleSelect")
def _single_select_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default singleSelect schema builder - always nullable."""
    base = {"type": ["string", "null"], "description": "Select one of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"}
    if enum_values is not None:
        base["enum"] = enum_values
    return base


@register_schema_builder("multipleSelect")
def _multiple_select_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default multipleSelect schema builder - always nullable."""
    base = {
        "type": ["array", "null"],
        "items": {"type": "string"},
        "description": "Select one or more of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"
    }
    if enum_values is not None:
        base["items"]["enum"] = enum_values
    return base

@register_schema_builder("currency")
def _currency_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Currency schema builder - nullable number with hint about precision."""
    # We don't encode precision constraints here; description guides the model.
    return {"type": ["number", "null"], "description": "Currency - must be a number with up to 2 decimal precision"}


@register_schema_builder("array")
def _array_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default array schema builder - always nullable."""
    return {"type": ["array", "null"]}


@register_schema_builder("object")
def _object_schema_builder(engine: SchemaConverterEngine, target_type: str, enum_values: Optional[List[str]], nullable: bool) -> Dict[str, Any]:
    """Default object schema builder - always nullable."""
    return {"type": ["object", "null"]}


# ----------------------------- Default Validators -----------------------------

@register_validator("date")
def _date_validator(engine: SchemaConverterEngine, value: Any) -> Tuple[bool, str]:
    """Validate ISO date format."""
    if not isinstance(value, str):
        return False, f"Date must be a string, got {type(value)}"
    try:
        from datetime import datetime
        datetime.fromisoformat(value)
        return True, ""
    except ValueError:
        return False, f"Invalid ISO date format: {value}"


@register_validator("datetime")
def _datetime_validator(engine: SchemaConverterEngine, value: Any) -> Tuple[bool, str]:
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


@register_validator("singleSelect")
def _single_select_validator(engine: SchemaConverterEngine, value: Any) -> Tuple[bool, str]:
    """Validate singleSelect enum value."""
    # JSON Schema already validates enum membership, so this is just for additional checks
    return True, ""


@register_validator("multipleSelect")
def _multiple_select_validator(engine: SchemaConverterEngine, value: Any) -> Tuple[bool, str]:
    """Validate multipleSelect array values."""
    # JSON Schema already validates array and enum membership, so this is just for additional checks
    return True, ""


