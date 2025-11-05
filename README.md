# SPKC EHR Schema Engine

A comprehensive schema operations engine for conversion, validation, enrichment, and reverse mapping of external schema languages to OpenAI-compatible JSON Schema.

## Overview

The SPKC EHR Schema Engine provides a generic, database-agnostic solution for converting external schema languages (like PointClickCare assessments) into OpenAI-compatible JSON Schema format. It supports schema validation, enrichment, reverse conversion, and container grouping.

## Key Features

- **Generic Schema Conversion**: Convert any external schema language to OpenAI-compatible JSON Schema
- **Meta-Schema Language**: Define how external schemas work using a meta-schema language
- **Schema Validation**: Validate data against generated schemas with custom validators
- **Schema Enrichment**: Add contextual descriptions to schema properties from CSV files
- **CSV to Dict Utilities**: Convert CSV model instructions into enrichment dictionaries
- **Reverse Conversion**: Map AI model responses back to original external schema format
- **Container Grouping**: Group responses by hierarchical containers
- **Virtual Containers**: Expand single fields into nested objects with multiple properties
- **HTML Sanitization**: Automatic cleaning of HTML tags from text fields
- **Extensible Architecture**: Register custom builders, validators, and formatters

## Architecture

### Core Components

- **SchemaEngine**: Main engine class for schema operations
- **Meta-Schema Language**: Definition language for describing external schema structures
- **Schema Builders**: Functions that create JSON schema fragments for specific target types
- **Validators**: Functions that validate data against field-specific rules
- **Reverse Formatters**: Functions that convert AI responses back to original format
- **Options Extractors**: Functions that extract enum options from complex structures

### Target Types Supported

- `string`, `text` - Text fields
- `integer`, `number` - Numeric fields
- `positive_integer`, `positive_number` - Non-negative numeric fields
- `boolean` - Boolean fields
- `date`, `datetime` - Date/time fields with ISO format validation
- `single_select`, `multiple_select` - Enum-based selection fields
- `instructions` - Contextual instruction fields
- `virtual_container` - Expandable container fields
- `array`, `object` - Complex data structures

## Directory Structure

```
spkc-ehr-schema/
├── src/
│   ├── schema_engine.py              # Core engine implementation
│   └── pcc/
│       ├── pcc_assessment_schema.py  # PointClickCare wrapper
│       └── assmnt_templates/         # PCC assessment templates
├── tests/
│   ├── schema_engine_test.py         # Core engine tests
│   └── pcc/
│       └── pcc_assessment_schema_test.py  # PCC wrapper tests
└── README.md
```

## Quick Start

### Basic Usage

```python
from schema_engine.schema_engine import SchemaEngine

# Define meta-schema for your external schema language
meta_schema = {
    "schema_name": "tableName",
    "container": {
        "container_name": "sections",
        "container_type": "array",
        "object": {
            "name": "sectionName",
            "key": "sectionId",
            "properties": {
                "properties_name": "fields",
                "property": {
                    "key": "fieldKey",
                    "name": "fieldName",
                    "type": "fieldType",
                    "validation": {
                        "allowed_types": ["string", "number"],
                        "type_constraints": {
                            "string": {"target_type": "string", "requires_options": False},
                            "number": {"target_type": "number", "requires_options": False}
                        }
                    }
                }
            }
        }
    }
}

# Initialize engine
engine = SchemaEngine(meta_schema)

# Register a table
table_id, table_name = engine.register_table(None, external_schema)

# Get JSON schema
json_schema = engine.get_json_schema(table_id)

# Validate data
is_valid, errors = engine.validate(table_id, data)

# Convert model response back to original format
result = engine.reverse_map(table_name, model_response)
```

### Schema Enrichment from CSV

The engine supports enriching schema descriptions with contextual information from CSV files using the `csv_to_dict` utility:

```python
from schema_engine.schema_engine import SchemaEngine
from schema_engine.csv_to_dict import read_key_value_csv_path

# Initialize engine and register your schema
engine = SchemaEngine(meta_schema)
table_id, table_name = engine.register_table(table_name, external_schema)

# Load enrichment data from CSV file
enrichment_dict = read_key_value_csv_path(
    csv_path="model_instructions.csv",
    key_col="Key",                    # Column name for field keys
    value_col="Guidelines",           # Column name for enrichment text
    key_prefix="Cust",                 # Optional: prefix all keys with "Cust_"
    sanitize_values=True,              # Optional: remove HTML and special characters
    skip_blank_keys=True,             # Optional: skip empty keys (default: True)
    strip_whitespace=True,            # Optional: strip whitespace (default: True)
    case_insensitive=False,          # Optional: case-insensitive column matching
    on_duplicate="concat"               # Optional: how to handle duplicates
)

# Enrich the schema and check for unmatched keys
unmatched_keys = engine.enrich_schema(table_name, enrichment_dict)

# Verify all keys matched (positive case)
if len(unmatched_keys) == 0:
    print("✓ All enrichment keys matched successfully!")
else:
    print(f"⚠ Found {len(unmatched_keys)} unmatched keys: {unmatched_keys}")
    # Optionally remove unmatched keys from your CSV or update the schema
```

#### CSV to Dict Parameters

- **`csv_path`**: Path to your CSV file (local file path, or use `read_key_value_csv_s3()` for S3)
- **`key_col`**: Column name containing field keys (must match schema field keys)
- **`value_col`**: Column name containing enrichment text/descriptions
- **`key_prefix`** (optional): Automatically prefix keys with a string (e.g., "Cust_" for PointClickCare)
- **`sanitize_values`** (optional, default: `False`): Remove HTML tags and JSON-breaking characters from values
- **`skip_blank_keys`** (optional, default: `True`): Skip rows where the key is empty/whitespace
- **`strip_whitespace`** (optional, default: `True`): Strip leading/trailing whitespace from keys and values
- **`case_insensitive`** (optional, default: `False`): Match column names case-insensitively
- **`on_duplicate`** (optional, default: `"last"`): How to handle duplicate keys:
  - `"last"`: Last value wins
  - `"first"`: First value wins
  - `"error"`: Raise ValueError
  - `"concat"`: Concatenate values with separator (default: ". ")

#### Handling Unmatched Keys

The `enrich_schema()` method returns a list of unmatched keys. Use this to:
- Validate CSV data quality
- Identify missing schema fields
- Debug mismatches between CSV and schema

```python
unmatched_keys = engine.enrich_schema(table_name, enrichment_dict)
if len(unmatched_keys) > 0:
    # Log or handle unmatched keys
    logger.warning(f"Unmatched enrichment keys: {unmatched_keys}")
```

### PointClickCare Integration

```python
from pcc_schema.pcc_assessment_schema import PCCAssessmentSchema

# Initialize PCC wrapper
pcc_schema = PCCAssessmentSchema()

# Register assessment
assessment_id, assessment_name = pcc_schema.register_assessment(None, pcc_assessment_data)

# Get JSON schema for AI
json_schema = pcc_schema.get_json_schema(assessment_id)

# Validate AI response
is_valid, errors = pcc_schema.validate(assessment_id, ai_response)

# Convert AI response back to PCC format
pcc_result = pcc_schema.reverse_map(assessment_name, ai_response, group_by_containers=["sections"])
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run core engine tests
python tests/schema_engine_test.py

# Run PCC-specific tests
python tests/pcc/pcc_assessment_schema_test.py
```

## Meta-Schema Language

The meta-schema language allows you to describe how external schema languages work. It supports:

- **Flat Schemas**: Direct properties at root level
- **Nested Schemas**: Hierarchical containers with up to 5 nesting levels
- **Type Constraints**: Map external types to internal target types
- **Options Extraction**: Handle simple lists or complex option structures
- **Validation Rules**: Define allowed/ignored types and constraints

See the PointClickCare implementation in `src/pcc/pcc_assessment_schema.py` for a complete example.

## Contributing

1. Follow PEP 8 style guidelines
2. Add tests for new functionality
3. Update documentation for API changes
4. Ensure all tests pass before submitting

## License

This project is part of the SpeakCare EHR system.