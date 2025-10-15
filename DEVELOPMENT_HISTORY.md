# Schema Engine Development History

## Overview
This document captures the key development decisions, architectural changes, and implementation details from the schema engine development process.

## Major Refactoring: SchemaConverterEngine → SchemaEngine

### Rationale
The original name `SchemaConverterEngine` was too narrow and didn't reflect the engine's expanded capabilities beyond just conversion. The engine now handles:
- Schema conversion
- Validation
- Metadata management
- Reverse conversion
- Schema enrichment
- Container grouping

### Changes Made
1. **Class Rename**: `SchemaConverterEngine` → `SchemaEngine`
2. **File Rename**: `schema_converter_engine.py` → `schema_engine.py`
3. **Test File Rename**: `schema_converter_engine_test.py` → `schema_engine_test.py`
4. **Updated Imports**: All dependent files updated to use new names
5. **Updated Docstrings**: Documentation reflects expanded capabilities

## Directory Structure Reorganization

### Original Structure
```
backend/
├── schema_converter_engine.py
├── schema_converter_engine_test.py
├── pcc_assessment_schema.py
├── pcc_assessment_schema_test.py
└── pcc/
    └── assmnt_templates/
```

### New Structure
```
src/
├── schema_engine.py
└── pcc/
    ├── pcc_assessment_schema.py
    └── assmnt_templates/
tests/
├── schema_engine_test.py
└── pcc/
    └── pcc_assessment_schema_test.py
```

### Benefits
- **Better Organization**: PCC-specific code properly grouped
- **Cleaner Structure**: Core engine remains at root level
- **Scalable**: Easy to add other schema language implementations
- **Maintainable**: Clear separation between generic engine and specific implementations

## Key Technical Implementations

### 1. Dynamic Container Key Field Extraction
**Problem**: Hardcoded PCC-specific names (`"sectionCode"`, `"assessmentQuestionGroups"`, `"groupNumber"`) in `_process_properties`.

**Solution**: Implemented `_extract_container_key_field` method to dynamically traverse the meta-schema's container hierarchy and find the appropriate `key_field` for a given `level_keys` path.

**Benefits**:
- Supports up to `MAX_NESTING_LEVELS = 5`
- Generic for any schema language
- No hardcoded field names

### 2. Reverse Formatter Decorator Pattern
**Problem**: Inconsistent manual registration of built-in reverse formatters instead of using decorators like builders and validators.

**Solution**: Added `_register_reverse_formatter` decorator and applied it to all built-in reverse formatters.

**Benefits**:
- Consistent registration pattern
- Cleaner code organization
- Easier maintenance

### 3. Production Error Handling
**Problem**: `reverse_map` method defaulted to `"string"` target type if `field_meta` was missing `target_type`, which could mask bugs.

**Solution**: Changed to log an error and return `None` for the problematic field instead of raising an exception.

**Benefits**:
- Graceful degradation in production
- Better debugging information
- Prevents entire reverse mapping from failing

### 4. Dynamic Container Grouping
**Problem**: `reverse_map` method hardcoded `"sections"` for grouping instead of using dynamic `container_name` from meta-schema.

**Solution**: Modified `_group_by_containers` to use the dynamic `container_name` from the meta-schema.

**Benefits**:
- Generic for any schema language
- No hardcoded container names
- Flexible grouping options

## Reverse Conversion Architecture

### Design Principles
1. **Engine handles traversal and orchestration** - walks the model response using `field_index` metadata
2. **Application handles formatting** - registers formatters for type-specific conversions
3. **Formatters return list of tuples** - `[(key, value), ...]` to support fields that expand to multiple entries
4. **Include null values** - pass through null values for all fields except virtual container children
5. **Container grouping** - engine supports grouping by container hierarchy and automatically includes container key fields

### Formatter Signature
```python
def formatter(engine, field_meta, model_value, table_name) -> List[Tuple[str, Any]]
```

### Built-in Formatters
- `_string_formatter`: Pass-through for string fields
- `_boolean_formatter`: Pass-through for boolean fields
- `_number_formatter`: Pass-through for number fields
- `_date_formatter`: Converts ISO date to YYYYMMDD format
- `_datetime_formatter`: Converts ISO datetime to PCC format (YYYY-MM-DD+HH:MM:SS.000)

### PCC-Specific Formatters
- `pcc_chk_reverse_formatter`: Converts boolean to 1/None
- `pcc_single_select_formatter`: Extracts responseValue from responseOptions
- `pcc_multi_select_formatter`: Returns list of responseValues
- `pcc_virtual_container_formatter`: Expands to multiple a#_key/b#_key pairs

## Virtual Container Implementation

### Concept
Virtual containers allow a single external schema property to expand into a nested JSON schema object with multiple child properties.

### Use Case
PCC "gbdy" (grid/table) fields that expand one field with response options into an object with a property per option.

### Implementation
1. Builder returns tuple: `(json_schema, additional_metadata)`
2. Engine marks field as virtual container with flags
3. Child metadata added to field_index with proper level_keys
4. Children marked with `"is_virtual_container_child": True`

## HTML Sanitization

### Implementation
All HTML tags are automatically removed from names, titles, and enum options during registration using `_sanitize_html` method.

### Benefits
- Clean data for LLM consumption
- Prevents HTML injection issues
- Consistent text formatting

## Testing Strategy

### Core Engine Tests
- 38 comprehensive tests covering all functionality
- Tests for flat and nested schema registration
- Validation testing with custom validators
- Meta-schema validation
- Reverse conversion testing

### PCC-Specific Tests
- 16 tests covering PCC wrapper functionality
- Tests for all PCC field types
- Reverse conversion testing with PCC formatters
- Virtual container testing
- Container grouping testing

## Future Considerations

### Extensibility
- Easy to add new schema language implementations
- Plugin architecture for custom builders, validators, and formatters
- Support for additional target types

### Performance
- Efficient field metadata indexing
- Optimized reverse conversion traversal
- Minimal memory footprint

### Maintainability
- Clear separation of concerns
- Comprehensive test coverage
- Well-documented APIs
- Consistent coding patterns

## Migration Notes

### From Original Repository
When migrating from the original demo repository:
1. Update import paths to use new directory structure
2. Use `SchemaEngine` instead of `SchemaConverterEngine`
3. Update test file references
4. Ensure all `__init__.py` files are present for proper module structure

### Import Path Examples
```python
# Old import
from schema_converter_engine import SchemaConverterEngine

# New import
from schema_engine import SchemaEngine

# PCC imports
from pcc.pcc_assessment_schema import PCCAssessmentSchema
```

This document serves as a comprehensive reference for understanding the schema engine's architecture, design decisions, and implementation details.

