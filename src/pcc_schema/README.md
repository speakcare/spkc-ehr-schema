# PointClickCare (PCC) Assessment Schema

This package provides a PCC-specific wrapper around the core `SchemaEngine` to work with PCC assessment templates and convert between:

- PCC external schemas (template JSON)
- OpenAI-compatible JSON Schema (for model prompts/validation)
- Model responses back to PCC-like formatted outputs (reverse mapping)

## Prerequisites

Before using this package, ensure you have:

1. **Poetry** installed on your system
2. Run the following commands to set up dependencies:

```bash
poetry lock
poetry install
```

These commands will:
- Lock dependencies to ensure reproducible builds
- Install all required packages including development dependencies

## Quick start

```python
from pcc.pcc_assessment_schema import (
    PCCAssessmentSchema,
    get_section_state,
    get_all_section_states
)

pcc = PCCAssessmentSchema()

# Four PCC templates are registered on init
registered_ids = pcc.list_assessments()  # [21242733, 21244981, 21242741, 21244831]

# JSON schema
json_schema = pcc.get_json_schema(21244981)

# Validate a model response
valid, errors = pcc.validate(21244981, {"table_name": "MHCS Nursing Admission Assessment - V 5"})

# Reverse map and access section states
result = pcc.reverse_map(21244981, model_response)
state = get_section_state(result, "Cust_1")  # Get state of a specific section
all_states = get_all_section_states(result)  # Get all section states
```

## Listing assessments

```python
pcc.list_assessments()           # -> [templateId, ...]
pcc.list_assessments_info()     # -> [{"id": <int>, "name": <str>}, ...]
```

## Field metadata

```python
fields = pcc.get_field_metadata(21244981)
# Each field includes: key, id, name, title, original_schema_type,
# target_type, level_keys, property_key, field_schema
```

## Container counts

```python
num_sections = pcc.get_num_sections(21244981)  # -> int, number of sections
# Also works with string identifier:
num_sections = pcc.get_num_sections("MHCS Nursing Admission Assessment - V 5")
```

## Reverse mapping (named formatters)

Reverse mapping converts a validated model response back to an application-specific format using named formatter sets.

Available formatter sets (per PCC wrapper instance):
- `default`: classic PCC-style types and values
- `pcc-ui`: UI-friendly array output with unpacking

Wrapper defaults for `reverse_map`:
- `formatter_name="pcc-ui"`
- `group_by_containers=["sections"]`
- `properties_key="fields"`
- `pack_properties_as="array"`

```python
model_response = {
  "table_name": "MHCS Nursing Weekly Skin Check",
  "sections": {
    "A.Section": {
      "assessmentQuestionGroups": {
        "1.Group": {
          "questions": {
            "Single": "Option A",
            "Multi": ["Choice 1", "Choice 2"],
            "Table": [{"entry": "Head", "description": "bruise"}]
          }
        }
      }
    }
  }
}

result = pcc.reverse_map(21244831, model_response)
# {
#   "doc_type": "pcc_assessment",
#   "assessment_title": <str>,
#   "assessment_std_id": <int>,
#   "sections": {
#     "Cust_1": {
#       "state": "draft",
#       "fields": [
#         {"key": "Cust_1_01_A", "type": "rad", "html_type": "radio_buttons", "value": "1"},
#         ...
#       ]
#     },
#     "Cust_2": {
#       "state": "draft",
#       "fields": [...]
#     }
#   }
# }
```

### Section State Management

Each section in the `reverse_map` output automatically includes a `"state"` field with a default value of `"draft"`. This field can be used to track the completion status of each section (e.g., "draft", "saved", "signed").

```python
from pcc.pcc_assessment_schema import get_section_state, get_all_section_states

result = pcc.reverse_map(21244831, model_response)

# Get the state of a specific section
state = get_section_state(result, "Cust_1")  # Returns "draft" (or None if section not found)

# Get all section states as an array
all_states = get_all_section_states(result)  # Returns ["draft", "draft", "saved", ...]
```

**Helper Functions:**
- `get_section_state(formatted_json, section_name)`: Returns the state of a specific section, or `None` if the section is not found.
- `get_all_section_states(formatted_json)`: Returns a list of all section states in sorted order. Sections without a state field default to `"draft"`.

### Formatter behavior (pcc-ui)

- Single select (`rad`,`radh`,`cmb`): `value` is the PCC `responseValue` for the selected `responseText`.
- Multi select (`mcs`,`mcsh`): unpacked into multiple entries; all entries share the same `key`.
- Object array (`gbdy`): JSON Schema items require `entry` and `description` with `additionalProperties: false`. Reverse output is unpacked to `aN_` and `bN_` entries.

## JSON Schema guarantees

- All objects set `additionalProperties: false`
- Bottom-level fields are listed in `required`
- `gbdy` modeled as `type: array` of strict objects

## Internal metadata (not emitted)

Formatters may attach internal fields used by the engine:
- `_storage_key`: collision-free storage key
- `_original_field_key`: base field key for grouping
- `_display_key`: key to display in array outputs when different from base

These never appear in final results.

## Custom formatters

You can add your own formatter set:

```python
def my_text_formatter(engine, field_meta, model_value, table_name):
    return [{"key": field_meta["key"], "type": "txt", "value": model_value}]

pcc.engine.register_reverse_formatter("my-ui", "txt", my_text_formatter)
# Register handlers for all original types before calling reverse_map
custom = pcc.reverse_map(21244981, model_response, formatter_name="my-ui")
```

## Schema Enrichment with Model Instructions

You can enrich PCC assessment schemas with model instructions from CSV files. The CSV should contain field keys and corresponding guidance text for the AI model.

### Basic Usage

```python
from pcc.pcc_assessment_schema import PCCAssessmentSchema
from csv_to_dict import read_key_value_csv_path

# Initialize PCC wrapper
pcc = PCCAssessmentSchema()

# The template is already registered, but if registering a new one:
# assessment_id, assessment_name = pcc.register_assessment(template_id, template_data)
assessment_name = "MHCS Nursing Admission Assessment - V 5"
assessment_id = 21244981

# Load your model instructions CSV
# Note: The CSV files in tests/pcc/model_instructions are for test/example only
# You should provide your own CSV files with Key and Guidelines columns
enrichment_dict = read_key_value_csv_path(
    csv_path="your_model_instructions.csv",
    key_col="Key",              # Column with field keys (e.g., "1_A", "1_B", etc.)
    value_col="Guidelines",       # Column with enrichment text
    key_prefix="Cust",            # Prefix keys with "Cust_" to match PCC field keys
    sanitize_values=True,         # Remove HTML tags and special characters
    skip_blank_keys=True,        # Skip empty keys
    strip_whitespace=True,       # Normalize whitespace
)

# Option A: One-call enrichment from CSV (local or S3)
unmatched_keys = pcc.enrich_assessment_from_csv(
    assessment_name,
    csv_path="your_model_instructions.csv",  # Local file example
    key_col,                      # Must provide
    value_col,                    # Must provide
    key_prefix="Cust",            # default
    sanitize_values=True,          # default True in the wrapper
    skip_blank_keys=True,          # default True
    strip_whitespace=False,        # default False
    case_insensitive=False,        # default False
    on_duplicate="concat",        # default "concat"
)

# Option A (S3 variant):
unmatched_keys = pcc.enrich_assessment_from_csv(
    assessment_name,
    s3_bucket="my-bucket",
    s3_key="path/to/your_model_instructions.csv",
    key_col="Key",
    value_col="Guidelines",
    key_prefix="Cust",
    sanitize_values=True,
)

# Option B: Manual control - load CSV then enrich
enrichment_dict = read_key_value_csv_path(
    csv_path="your_model_instructions.csv",
    key_col="Key",
    value_col="Guidelines",
    key_prefix="Cust",
    sanitize_values=True,
)
unmatched_keys = pcc.enrich_assessment_from_csv(
    assessment_name,
    csv_path="your_model_instructions.csv",
    key_col="Key",
    value_col="Guidelines",
    key_prefix="Cust",
    sanitize_values=True,
)

# Check for unmatched keys (CSV keys not found in schema)
if len(unmatched_keys) == 0:
    print("✓ All enrichment keys matched!")
else:
    print(f"⚠ {len(unmatched_keys)} unmatched keys: {unmatched_keys}")

# Get enriched JSON schema for AI consumption
enriched_schema = pcc.get_json_schema(assessment_id)
```

### CSV File Format

Your CSV should have at least two columns:

```csv
Key,Guidelines,Other columns...
1_A,"Check audio first for patient report...","..."
1_B,"If not in audio, check nursing notes...","..."
2_C,"Extract from database if available...","..."
```

The enrichment process will:
1. Read the CSV file
2. Prefix each key with "Cust_" (unless already prefixed)
3. Sanitize values to remove HTML tags and special characters
4. Match keys to schema fields
5. Append enrichment text to each field's description
6. Return list of any unmatched keys

### Complete Example

```python
from pcc.pcc_assessment_schema import PCCAssessmentSchema
from csv_to_dict import read_key_value_csv_path

# Initialize PCC wrapper
pcc = PCCAssessmentSchema()

# Register an assessment (or use existing)
assessment_id, assessment_name = pcc.register_assessment(
    template_id=21244981,
    template_data=your_template_data
)

# Load and apply model instructions
enrichment_dict = read_key_value_csv_path(
    "model_instructions.csv",
    key_col="Key",
    value_col="Guidelines",
    key_prefix="Cust",
    sanitize_values=True,
)

unmatched_keys = pcc.enrich_assessment_from_csv(
    assessment_name,
    csv_path="model_instructions.csv",
    key_col="Key",
    value_col="Guidelines",
    key_prefix="Cust",
    sanitize_values=True,
)

# Verify enrichment succeeded
assert len(unmatched_keys) == 0, f"Unmatched keys: {unmatched_keys}"

# Use enriched schema for AI model
json_schema = pcc.get_json_schema(assessment_id)
```

## Templates

On initialization, the wrapper registers four templates from `src/pcc/assmnt_templates` using each file's `templateId`:

- MHCS_IDT_5_Day_Section_GG.json (21242733)
- MHCS_Nursing_Admission_Assessment_-_V_5.json (21244981)
- MHCS_Nursing_Daily_Skilled_Note.json (21242741)
- MHCS_Nursing_Weekly_Skin_Check.json (21244831)

**Note**: CSV files in `tests/pcc/model_instructions/` are provided for testing and demonstration purposes only. Production deployments should use actual CSV files provided by the user with the required Key and Guidelines columns.

## Assessment Comparison Tool

The package includes a command-line tool to compare SpeakCare chart data with PCC assessment data, generating a CSV report of field-by-field differences.

### Usage

#### Single File Mode

Compare a single JSON file containing both `speakcare_chart` and `pcc_assessment` data:

```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --file <path_to_json_file> \
  --output <path_to_output_csv>
```

**Example:**
```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --file /path/to/unified_6_36909675_21242741_1767198195.json \
  --output comparison_single.csv
```

#### Directory Mode

Process multiple JSON files in a directory and generate an aggregated CSV:

```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --directory <path_to_directory> \
  --output <path_to_output_csv>
```

**Example:**
```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --directory tests/pcc/data_comparison/input \
  --output tests/pcc/data_comparison/output.csv
```

#### State Filtering

By default, the script only processes files where `speakcare_chart.state == "draft"`. You can customize this behavior:

**Default (draft only):**
```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --directory <path_to_directory> \
  --output <path_to_output_csv>
```

**Filter by specific state(s):**
```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --directory <path_to_directory> \
  --output <path_to_output_csv> \
  --state draft signed
```

**Process all states (no filtering):**
```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --directory <path_to_directory> \
  --output <path_to_output_csv> \
  --state
```

**Note:** The `--state` flag accepts multiple values. If no values are provided (just `--state`), all files are processed regardless of state.

#### Verbose Logging

Add `--verbose` or `-v` for detailed output:

```bash
poetry run python src/pcc_schema/compare_assessments.py \
  --directory <path_to_directory> \
  --output <path_to_output_csv> \
  --verbose
```

### CSV Output Format

The generated CSV has the following structure:

- **Header**: `fields, facility_id:patient_id:assessment_id, facility_id:patient_id:assessment_id, ...`
  - First column is always `fields`
  - Subsequent columns are assessment identifiers in format `facility_id:patient_id:assessment_id`
  
- **Data Rows**: Each row represents a field that had a difference in at least one assessment
  - Column 0: Field key in format `question_key:question_text` (e.g., `Cust_E_1:Does the resident have a cardiac diagnosis or symptoms?`)
  - Column 1+: Difference string in format `"pcc_value" != "speakcare_value"` or empty if no difference for that assessment

**Example CSV:**
```csv
fields,6:36909675:13448374,6:36909676:13448375
Cust_E_1:Does the resident have a cardiac diagnosis or symptoms?,""b"" != ""a"",
Cust_D_1:Resident is currently receiving (select all that apply):,""b,c"" != ""b,c,d"",
```

### Important Notes

- Only fields where SpeakCare has a **non-empty value** that differs from PCC are included in the output
- Empty SpeakCare values are ignored (not shown as differences, even if PCC has a value)
- When processing multiple files, the CSV includes rows for every field that had a difference in **any** of the comparisons
- Empty cells indicate that assessment had no difference for that field

### Help

View all available options:

```bash
poetry run python src/pcc_schema/compare_assessments.py --help
```

