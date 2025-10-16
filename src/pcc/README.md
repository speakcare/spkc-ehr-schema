# PointClickCare (PCC) Assessment Schema

This package provides a PCC-specific wrapper around the core `SchemaEngine` to work with PCC assessment templates and convert between:

- PCC external schemas (template JSON)
- OpenAI-compatible JSON Schema (for model prompts/validation)
- Model responses back to PCC-like formatted outputs (reverse mapping)

## Quick start

```python
from pcc.pcc_assessment_schema import PCCAssessmentSchema

pcc = PCCAssessmentSchema()

# Four PCC templates are registered on init
registered_ids = pcc.list_assessments()  # [21242733, 21244981, 21242741, 21244831]

# JSON schema
json_schema = pcc.get_json_schema(21244981)

# Validate a model response
valid, errors = pcc.validate(21244981, {"table_name": "MHCS Nursing Admission Assessment - V 5"})
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
#   "assessmentDescription": <str>,
#   "templateId": <int>,
#   "data": [
#     { "sectionCode": "A", "fields": [ {"key","type","value"}, ... ] }
#   ]
# }
```

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

## Templates

On initialization, the wrapper registers four templates from `src/pcc/assmnt_templates` using each file's `templateId`:

- MHCS_IDT_5_Day_Section_GG.json (21242733)
- MHCS_Nursing_Admission_Assessment_-_V_5.json (21244981)
- MHCS_Nursing_Daily_Skilled_Note.json (21242741)
- MHCS_Nursing_Weekly_Skin_Check.json (21244831)

