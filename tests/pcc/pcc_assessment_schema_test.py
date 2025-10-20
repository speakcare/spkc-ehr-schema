"""
Tests for PointClickCare Assessment Schema wrapper.
"""

import json
import unittest
import logging
from typing import Dict, Any

import sys
import os
# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'src'))
from pcc.pcc_assessment_schema import PCCAssessmentSchema, PCC_META_SCHEMA, extract_response_options


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _save_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _generate_value_for_field(field_meta: Dict[str, Any]) -> Any:
    original_type = field_meta.get("original_schema_type")
    target_type = field_meta.get("target_type")
    field_schema = field_meta.get("field_schema", {})

    # Some None values to exercise null handling deterministically
    key = field_meta.get("key", "")
    if isinstance(key, str) and len(key) % 11 == 0:
        return None

    if original_type in ("txt", "diag") or target_type in ("string", "text"):
        return "Sample text"
    if original_type in ("num", "numde") or target_type in ("number", "integer", "positive_integer", "positive_number"):
        return 42 if target_type in ("number", "positive_number") else 7
    if original_type == "chk" or target_type == "boolean":
        # Return False for some checkboxes to test null conversion
        return len(key) % 3 == 0
    if original_type in ("dte",) or target_type == "date":
        return "1950-01-15"
    if original_type in ("dttm",) or target_type == "datetime":
        return "2025-10-15T13:45:00"
    if original_type in ("rad", "radh", "cmb", "hck") or target_type == "single_select":
        opts = field_schema.get("responseOptions") or []
        if opts:
            return _sanitize_text_for_model(opts[0].get("responseText") or None)
        return None
    if original_type in ("mcs", "mcsh") or target_type == "multiple_select":
        opts = field_schema.get("responseOptions") or []
        names = [_sanitize_text_for_model(o.get("responseText")) for o in opts if o.get("responseText")]
        if not names:
            return None
        max_count = 5
        return names[: max_count]
    if target_type == "instructions" or original_type == "inst":
        # Instructions are const in JSON schema; no input needed
        return None
    if target_type == "virtual_container" or original_type == "gbdy":
        # Will be generated at parent handler, not here
        return {}
    return None


def _sanitize_text_for_model(s: Any) -> Any:
    if not isinstance(s, str):
        return s
    # Remove basic HTML tags and collapse consecutive whitespace
    import re
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _build_valid_model_response(pcc: PCCAssessmentSchema, assessment_id: int) -> Dict[str, Any]:
    schema = pcc.get_json_schema(assessment_id)
    title = schema.get("title", str(assessment_id))
    # Build sections structure by walking field metadata
    model: Dict[str, Any] = {
        "table_name": title,
        "sections": {}
    }

    field_index = pcc.get_field_metadata(assessment_id)

    # Pre-index virtual container children by parent key for gbdy support
    children_by_parent: Dict[str, list] = {}
    for f in field_index:
        if f.get("is_virtual_container_child"):
            parent = f.get("virtual_container_key")
            children_by_parent.setdefault(parent, []).append(f)

    # Helper to get questions properties dict from JSON schema using level_keys
    def _get_questions_props(level_keys: list) -> Dict[str, Any]:
        try:
            sections_props = schema["properties"]["sections"]["properties"]
            section_obj = sections_props[level_keys[1]]
            groups_obj = section_obj["properties"]["assessmentQuestionGroups"]["properties"][level_keys[3]]
            questions_props = groups_obj["properties"]["questions"]["properties"]
            return questions_props
        except Exception:
            return {}

    for f in field_index:
        level_keys = f.get("level_keys", [])
        if len(level_keys) < 5:
            continue
        section_key = level_keys[1]
        group_key = level_keys[3]
        question_name = f.get("name")
        target_type = f.get("target_type")
        original_type = f.get("original_schema_type")

        # Resolve allowed question keys for this group from schema
        questions_allowed = _get_questions_props(level_keys)
        if question_name not in questions_allowed:
            # Skip any field whose display name is not a schema property to avoid additionalProperties errors
            continue

        # Ensure containers exist
        sections = model["sections"]
        section_obj = sections.setdefault(section_key, {"assessmentQuestionGroups": {}})
        groups = section_obj["assessmentQuestionGroups"]
        group_obj = groups.setdefault(group_key, {"questions": {}})
        questions = group_obj["questions"]

        if target_type == "object_array" or original_type == "gbdy":
            # Build array value for gbdy fields
            field_schema = f.get("field_schema", {})
            response_options = field_schema.get("responseOptions", [])
            if response_options:
                # Generate up to 4 entries using first 4 options
                num_entries = min(4, len(response_options))
                entries = []
                
                for i in range(num_entries):
                    option = response_options[i]
                    entry_text = option.get("responseText", "")
                    description = f"Sample description for {entry_text}"
                    entries.append({
                        "entry": entry_text,
                        "description": description
                    })
                questions[question_name] = entries
            else:
                questions[question_name] = []
            continue

        # Regular fields
        questions[question_name] = _generate_value_for_field(f)

    # Ensure instruction constants are present exactly as required by JSON schema
    try:
        sections_props = schema["properties"]["sections"]["properties"]
        for section_key, section_schema in sections_props.items():
            groups_prop = section_schema["properties"]["assessmentQuestionGroups"]["properties"]
            for group_key, group_schema in groups_prop.items():
                qprops = group_schema["properties"]["questions"]["properties"]
                # Ensure containers in model
                section_obj = model["sections"].setdefault(section_key, {"assessmentQuestionGroups": {}})
                group_obj = section_obj["assessmentQuestionGroups"].setdefault(group_key, {"questions": {}})
                questions = group_obj["questions"]
                for qname, qschema in qprops.items():
                    if "const" in qschema:
                        # Instruction-like constant
                        questions[qname] = qschema["const"]
    except Exception:
        pass

    return model


def _reverse_and_save(pcc: PCCAssessmentSchema, assessment_id: int, out_dir: str) -> Dict[str, Any]:
    model = _build_valid_model_response(pcc, assessment_id)
    # Validate
    is_valid, errors = pcc.validate(assessment_id, model)
    if not is_valid:
        raise AssertionError(f"Generated model_response invalid for {assessment_id}: {errors}")
    # Reverse grouped by sections using the table title (name)
    table_name = pcc.get_json_schema(assessment_id).get("title", str(assessment_id))
    grouped = pcc.engine.reverse_map(table_name, model, group_by_containers=["sections"])
    # Save
    _ensure_dir(out_dir)
    out_path = os.path.join(out_dir, f"{assessment_id}.json")
    _save_json(out_path, grouped)
    return {"model": model, "grouped": grouped, "path": out_path}


class TestPCCAssessmentSchema(unittest.TestCase):
    """Test cases for PCC Assessment Schema wrapper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pcc_schema = PCCAssessmentSchema()
        
        # MDS 2.0 Full Assessment test data (simplified version)
        self.mds_assessment = {
            "assessmentDescription": "MDS 2.0 Full Assessment",
            "facId": 100,
            "templateId": 1,
            "templateVersion": "2.0",
            "sections": [
                {
                    "sectionCode": "AA",
                    "sectionDescription": "Identification Information",
                    "sectionSequence": 40,
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "",
                            "groupTitle": "RESIDENT NAME",
                            "questions": [
                                {
                                    "questionKey": "AA1a",
                                    "questionNumber": "a",
                                    "questionText": "First",
                                    "questionTitle": "First Name",
                                    "questionType": "txt",
                                    "required": False,
                                    "length": 12,
                                    "range": "Text,sp(12)"
                                },
                                {
                                    "questionKey": "AA1c",
                                    "questionNumber": "c",
                                    "questionText": "Last",
                                    "questionTitle": "Last Name",
                                    "questionType": "txt",
                                    "required": True,
                                    "length": 18,
                                    "range": "Text"
                                }
                            ]
                        },
                        {
                            "groupNumber": "2",
                            "groupText": "",
                            "groupTitle": "GENDER",
                            "questions": [
                                {
                                    "questionKey": "AA2",
                                    "questionNumber": "",
                                    "questionText": "GENDER",
                                    "questionTitle": "GENDER",
                                    "questionType": "radh",
                                    "required": True,
                                    "length": 1,
                                    "range": "1,2,-",
                                    "responseOptions": [
                                        {
                                            "responseText": "Male",
                                            "responseValue": "1"
                                        },
                                        {
                                            "responseText": "Female",
                                            "responseValue": "2"
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "groupNumber": "3",
                            "groupText": "",
                            "groupTitle": "BIRTHDATE",
                            "questions": [
                                {
                                    "questionKey": "AA3",
                                    "questionNumber": "",
                                    "questionText": "BIRTHDATE",
                                    "questionTitle": "BIRTHDATE",
                                    "questionType": "dte",
                                    "required": True,
                                    "length": 8,
                                    "range": "Valid full or partial date, -(8)"
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "AB",
                    "sectionDescription": "Demographic Information",
                    "sectionSequence": 50,
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "2",
                            "groupText": "",
                            "groupTitle": "ADMITTED FROM (AT ENTRY)",
                            "questions": [
                                {
                                    "questionKey": "AB2",
                                    "questionNumber": "",
                                    "questionText": "ADMITTED FROM (AT ENTRY)",
                                    "questionTitle": "ADMITTED FROM (AT ENTRY)",
                                    "questionType": "rad",
                                    "required": True,
                                    "length": 1,
                                    "range": "1 thru 8,-",
                                    "responseOptions": [
                                        {
                                            "responseText": "Private home/apt. with no home health services",
                                            "responseValue": "1"
                                        },
                                        {
                                            "responseText": "Private home/apt. with home health services",
                                            "responseValue": "2"
                                        },
                                        {
                                            "responseText": "Board and care/assisted living/group home",
                                            "responseValue": "3"
                                        },
                                        {
                                            "responseText": "Nursing home",
                                            "responseValue": "4"
                                        },
                                        {
                                            "responseText": "Acute care hospital",
                                            "responseValue": "5"
                                        },
                                        {
                                            "responseText": "Psychiatric hospital, MR/DD facility",
                                            "responseValue": "6"
                                        },
                                        {
                                            "responseText": "Rehabilitation hospital",
                                            "responseValue": "7"
                                        },
                                        {
                                            "responseText": "Other",
                                            "responseValue": "8"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "A",
                    "sectionDescription": "Identification and Background Information",
                    "sectionSequence": 80,
                    "assessmentQuestionGroups": []  # Empty container
                }
            ]
        }
    
    def test_basic_registration(self):
        """Test basic assessment registration."""
        # Register the assessment
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        self.assertIsInstance(assessment_id, int)
        self.assertEqual(assessment_name, "MDS 2.0 Full Assessment")
        
        # Verify it's registered
        assessments = self.pcc_schema.list_assessments()
        self.assertIn(assessment_id, assessments)
        
        # Verify JSON schema is generated
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        self.assertIsInstance(json_schema, dict)
        self.assertIn("properties", json_schema)
    
    def test_json_schema_structure(self):
        """Test JSON schema structure and nesting."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Verify title
        self.assertEqual(json_schema["title"], "MDS 2.0 Full Assessment")
        
        # Verify table_name field
        self.assertIn("table_name", json_schema["properties"])
        table_name_field = json_schema["properties"]["table_name"]
        self.assertEqual(table_name_field["type"], "string")
        self.assertEqual(table_name_field["const"], "MDS 2.0 Full Assessment")
        
        # Verify sections structure
        self.assertIn("sections", json_schema["properties"])
        sections = json_schema["properties"]["sections"]
        self.assertEqual(sections["type"], "object")
        self.assertFalse(sections["additionalProperties"])
        
        # Verify section properties exist (AA.Identification Information)
        self.assertIn("AA.Identification Information", sections["properties"])
        aa_section = sections["properties"]["AA.Identification Information"]
        self.assertEqual(aa_section["type"], "object")
        self.assertFalse(aa_section["additionalProperties"])
        
        # Verify assessmentQuestionGroups structure
        self.assertIn("assessmentQuestionGroups", aa_section["properties"])
        groups = aa_section["properties"]["assessmentQuestionGroups"]
        self.assertEqual(groups["type"], "object")
        self.assertFalse(groups["additionalProperties"])
        
        # Verify group properties exist (1)
        self.assertIn("1", groups["properties"])
        group1 = groups["properties"]["1"]
        self.assertEqual(group1["type"], "object")
        self.assertFalse(group1["additionalProperties"])
        
        # Verify questions structure
        self.assertIn("questions", group1["properties"])
        questions = group1["properties"]["questions"]
        self.assertEqual(questions["type"], "object")
        self.assertFalse(questions["additionalProperties"])
    
    def test_field_types(self):
        """Test different field types are correctly mapped."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Navigate to questions
        questions = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["1"]["properties"]["questions"]["properties"]
        
        # Test text field (First Name)
        self.assertIn("First", questions)
        first_name_field = questions["First"]
        self.assertEqual(first_name_field["type"], ["string", "null"])
        
        # Test text field (Last Name)
        self.assertIn("Last", questions)
        last_name_field = questions["Last"]
        self.assertEqual(last_name_field["type"], ["string", "null"])
        
        # Navigate to GENDER questions
        gender_questions = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["2"]["properties"]["questions"]["properties"]
        
        # Test radio field (GENDER)
        self.assertIn("GENDER", gender_questions)
        gender_field = gender_questions["GENDER"]
        self.assertEqual(gender_field["type"], ["string", "null"])
        self.assertIn("enum", gender_field)
        
        # Navigate to BIRTHDATE questions
        birthdate_questions = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["3"]["properties"]["questions"]["properties"]
        
        # Test date field (BIRTHDATE)
        self.assertIn("BIRTHDATE", birthdate_questions)
        birthdate_field = birthdate_questions["BIRTHDATE"]
        self.assertEqual(birthdate_field["type"], ["string", "null"])
        self.assertIn("format", birthdate_field)
        self.assertEqual(birthdate_field["format"], "date")
    
    def test_options_extraction(self):
        """Test options extraction from responseOptions."""
        # Test extract_response_options function directly
        options = [
            {"responseText": "Male", "responseValue": "1"},
            {"responseText": "Female", "responseValue": "2"}
        ]
        extracted = extract_response_options(options)
        self.assertEqual(extracted, ["Male", "Female"])
        
        # Test with empty options
        empty_extracted = extract_response_options([])
        self.assertEqual(empty_extracted, [])
        
        # Test with None
        none_extracted = extract_response_options(None)
        self.assertEqual(none_extracted, [])
        
        # Test enum values in JSON schema
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Check GENDER field enum
        gender_field = json_schema["properties"]["sections"]["properties"]["AA.Identification Information"]["properties"]["assessmentQuestionGroups"]["properties"]["2"]["properties"]["questions"]["properties"]["GENDER"]
        self.assertIn("enum", gender_field)
        self.assertIn("Male", gender_field["enum"])
        self.assertIn("Female", gender_field["enum"])
        self.assertIn(None, gender_field["enum"])  # null should be included
        
        # Check ADMITTED FROM field enum
        admitted_from_field = json_schema["properties"]["sections"]["properties"]["AB.Demographic Information"]["properties"]["assessmentQuestionGroups"]["properties"]["2"]["properties"]["questions"]["properties"]["ADMITTED FROM (AT ENTRY)"]
        self.assertIn("enum", admitted_from_field)
        self.assertIn("Private home/apt. with no home health services", admitted_from_field["enum"])
        self.assertIn("Other", admitted_from_field["enum"])
        self.assertIn(None, admitted_from_field["enum"])
    
    def test_empty_containers(self):
        """Test handling of empty containers."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Verify empty section is handled gracefully
        sections = json_schema["properties"]["sections"]["properties"]
        
        # Section A should exist but have no assessmentQuestionGroups
        self.assertIn("A.Identification and Background Information", sections)
        section_a = sections["A.Identification and Background Information"]
        
        # Should have assessmentQuestionGroups property but it should be empty
        self.assertIn("assessmentQuestionGroups", section_a["properties"])
        groups = section_a["properties"]["assessmentQuestionGroups"]
        self.assertEqual(groups["type"], "object")
        self.assertEqual(groups["properties"], {})  # Empty properties
        self.assertEqual(groups["required"], [])  # Empty required
    
    def test_validation_success(self):
        """Test successful validation with valid data."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        
        # Valid data matching the schema structure
        valid_data = {
            "table_name": "MDS 2.0 Full Assessment",
            "sections": {
                "AA.Identification Information": {
                    "assessmentQuestionGroups": {
                        "1": {
                            "questions": {
                                "First": "John",
                                "Last": "Doe"
                            }
                        },
                        "2": {
                            "questions": {
                                "GENDER": "Male"
                            }
                        },
                        "3": {
                            "questions": {
                                "BIRTHDATE": "1950-01-15"
                            }
                        }
                    }
                },
                "AB.Demographic Information": {
                    "assessmentQuestionGroups": {
                        "2": {
                            "questions": {
                                "ADMITTED FROM (AT ENTRY)": "Private home/apt. with no home health services"
                            }
                        }
                    }
                },
                "A.Identification and Background Information": {
                    "assessmentQuestionGroups": {}
                }
            }
        }
        
        is_valid, errors = self.pcc_schema.validate(assessment_id, valid_data)
        self.assertTrue(is_valid, f"Expected validation to pass, but got errors: {errors}")
    
    def test_validation_failure(self):
        """Test validation failure with invalid data."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        
        # Invalid enum value for GENDER
        invalid_data = {
            "table_name": "MDS 2.0 Full Assessment",
            "sections": {
                "AA.Identification Information": {
                    "assessmentQuestionGroups": {
                        "2": {
                            "questions": {
                                "GENDER": "Invalid Gender"  # Not in enum
                            }
                        }
                    }
                }
            }
        }
        
        is_valid, errors = self.pcc_schema.validate(assessment_id, invalid_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid enum value")
        self.assertTrue(any("not one of" in error.lower() for error in errors), f"Expected enum error, got: {errors}")
        
        # Invalid date format
        invalid_date_data = {
            "table_name": "MDS 2.0 Full Assessment",
            "sections": {
                "AA.Identification Information": {
                    "assessmentQuestionGroups": {
                        "3": {
                            "questions": {
                                "BIRTHDATE": "not-a-date"  # Invalid date format
                            }
                        }
                    }
                }
            }
        }
        
        is_valid, errors = self.pcc_schema.validate(assessment_id, invalid_date_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid date")
    
    def test_field_metadata(self):
        """Test field metadata collection."""
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, self.mds_assessment)
        
        field_metadata = self.pcc_schema.get_field_metadata(assessment_id)
        
        # Should have metadata for all fields
        self.assertGreater(len(field_metadata), 0)
        
        # Find specific field metadata
        first_name_meta = next((field for field in field_metadata if field["key"] == "AA1a"), None)
        self.assertIsNotNone(first_name_meta, "Should have metadata for AA1a field")
        self.assertEqual(first_name_meta["name"], "First")
        self.assertEqual(first_name_meta["target_type"], "string")
        # level_keys should be ["AA", "1", "questions"] based on the actual schema structure
        self.assertEqual(first_name_meta["level_keys"], ["sections", "AA.Identification Information", "assessmentQuestionGroups", "1", "questions"])
        
        # Check gender field metadata
        gender_meta = next((field for field in field_metadata if field["key"] == "AA2"), None)
        self.assertIsNotNone(gender_meta, "Should have metadata for AA2 field")
        self.assertEqual(gender_meta["name"], "GENDER")
        self.assertEqual(gender_meta["target_type"], "single_select")
        
        # Check birthdate field metadata
        birthdate_meta = next((field for field in field_metadata if field["key"] == "AA3"), None)
        self.assertIsNotNone(birthdate_meta, "Should have metadata for AA3 field")
        self.assertEqual(birthdate_meta["name"], "BIRTHDATE")
        self.assertEqual(birthdate_meta["target_type"], "date")

    def test_instruction_fields(self):
        """Test that instruction fields are properly mapped with const values."""
        assessment_with_instructions = {
            "assessmentDescription": "Test Assessment with Instructions",
            "facId": 100,
            "templateId": 1,
            "templateVersion": "1.0",
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Test Section",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Test Group",
                            "questions": [
                                {
                                    "questionKey": "INSTR1",
                                    "questionNumber": "1",
                                    "questionText": "Please answer the following questions based on observation",
                                    "questionTitle": "Instructions",
                                    "questionType": "inst"
                                },
                                {
                                    "questionKey": "Q1",
                                    "questionNumber": "2",
                                    "questionText": "Patient height",
                                    "questionTitle": "Height",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, assessment_with_instructions)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Navigate to the questions - groupText is empty, so the key is just "1"
        questions = json_schema["properties"]["sections"]["properties"]["A.Test Section"]["properties"]["assessmentQuestionGroups"]["properties"]["1"]["properties"]["questions"]
        
        # Verify instruction field - property key is "1.Instructions"
        instr_field = questions["properties"]["1.Instructions"]
        self.assertEqual(instr_field["type"], "string")
        self.assertEqual(instr_field["const"], "Instructions. Please answer the following questions based on observation")
        self.assertEqual(instr_field["description"], "These are instructions that should be used as context for other properties of the same schema object and adjacent schema objects.")
        
        # Verify it's in the required list
        self.assertIn("1.Instructions", questions["required"])

    def test_gbdy_virtual_container(self):
        """Test that gbdy fields expand into virtual containers."""
        pcc = PCCAssessmentSchema()
        assessment = {
            "assessmentDescription": "Test Grid Field",
            "templateId": 1,
            "templateVersion": "1.0",
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Test Section",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Test Group",
                            "questions": [
                                {
                                    "questionKey": "A1",
                                    "questionNumber": "1",
                                    "questionText": "Table of fruits",
                                    "questionTitle": "Fruits",
                                    "questionType": "gbdy",
                                    "responseOptions": [
                                        {"responseValue": "a", "responseText": "Apple"},
                                        {"responseValue": "b", "responseText": "Banana"},
                                        {"responseValue": "c", "responseText": "Cherry"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        assessment_id, _ = pcc.register_assessment(None, assessment)
        json_schema = pcc.get_json_schema(assessment_id)
        fruits_field = json_schema["properties"]["sections"]["properties"]["A.Test Section"]["properties"]["assessmentQuestionGroups"]["properties"]["1"]["properties"]["questions"]["properties"]["Table of fruits"]
        self.assertEqual(fruits_field["type"], "array")
        self.assertIn("maxItems", fruits_field)
        self.assertIn("items", fruits_field)
        items_schema = fruits_field["items"]
        self.assertEqual(items_schema["type"], "object")
        self.assertIn("entry", items_schema["properties"])
        self.assertIn("description", items_schema["properties"])
        self.assertEqual(items_schema["properties"]["entry"]["type"], "string")
        self.assertIn("enum", items_schema["properties"]["entry"])
        self.assertIn("Apple", items_schema["properties"]["entry"]["enum"])

    def test_computed_fields_skipped(self):
        """Test that computed (cp) fields are skipped in JSON schema."""
        assessment_with_computed = {
            "assessmentDescription": "Test Assessment with Computed Fields",
            "facId": 100,
            "templateId": 1,
            "templateVersion": "1.0",
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Test Section",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Test Group",
                            "questions": [
                                {
                                    "questionKey": "COMP1",
                                    "questionNumber": "1",
                                    "questionText": "Computed total score",
                                    "questionTitle": "Total Score",
                                    "questionType": "cp"
                                },
                                {
                                    "questionKey": "Q1",
                                    "questionNumber": "2",
                                    "questionText": "Patient height",
                                    "questionTitle": "Height",
                                    "questionType": "txt"
                                },
                                {
                                    "questionKey": "COMP2",
                                    "questionNumber": "3",
                                    "questionText": "Computed BMI",
                                    "questionTitle": "BMI",
                                    "questionType": "cp"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = self.pcc_schema.register_assessment(None, assessment_with_computed)
        json_schema = self.pcc_schema.get_json_schema(assessment_id)
        
        # Navigate to the questions - groupText is empty, so the key is just "1"
        questions = json_schema["properties"]["sections"]["properties"]["A.Test Section"]["properties"]["assessmentQuestionGroups"]["properties"]["1"]["properties"]["questions"]
        
        # Verify computed fields are NOT in the schema
        self.assertNotIn("Computed total score", questions["properties"])
        self.assertNotIn("Computed BMI", questions["properties"])
        
        # Verify regular field IS in the schema
        self.assertIn("Patient height", questions["properties"])
        
        # Verify computed fields are NOT in required list
        self.assertNotIn("Computed total score", questions["required"])
        self.assertNotIn("Computed BMI", questions["required"])
        
        # Verify regular field IS in required list
        self.assertIn("Patient height", questions["required"])
        
        # Verify only 1 field in questions (not 3)
        self.assertEqual(len(questions["properties"]), 1)
        self.assertEqual(len(questions["required"]), 1)

    def test_pcc_single_select_reverse(self):
        """Test PCC single select reverse formatter."""
        pcc = PCCAssessmentSchema()
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Resident arrived via:",
                                    "questionType": "radh",
                                    "responseOptions": [
                                        {"responseText": "Ambulatory", "responseValue": "a"},
                                        {"responseText": "Stretcher", "responseValue": "b"},
                                        {"responseText": "Wheelchair", "responseValue": "c"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Resident arrived via:": "Wheelchair"
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map
        result = pcc.engine.reverse_map(assessment_name, model_response)
        
        # Verify responseValue extraction
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["A_1"], {"type": "radio", "value": "c"})  # Wheelchair -> "c"

    def test_pcc_multi_select_reverse(self):
        """Test PCC multi select reverse formatter."""
        pcc = PCCAssessmentSchema()
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Select all that apply:",
                                    "questionType": "mcs",
                                    "responseOptions": [
                                        {"responseText": "Option A", "responseValue": "a"},
                                        {"responseText": "Option B", "responseValue": "b"},
                                        {"responseText": "Option C", "responseValue": "c"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Select all that apply:": ["Option A", "Option C"]
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map
        result = pcc.engine.reverse_map(assessment_name, model_response)
        
        # Verify multiple responseValue extraction
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["A_1"], {"type": "multi", "value": ["a", "c"]})  # Option A -> "a", Option C -> "c"

    def test_pcc_chk_reverse(self):
        """Test PCC checkbox reverse formatter."""
        pcc = PCCAssessmentSchema()
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Is resident alert?",
                                    "questionType": "chk"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Is resident alert?": True
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map
        result = pcc.engine.reverse_map(assessment_name, model_response)
        
        # Verify boolean to 1/None conversion
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["A_1"], {"type": "checkbox", "value": 1})  # True -> 1
        
        # Test false case
        model_response_false = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Is resident alert?": False
                            }
                        }
                    }
                }
            }
        }
        
        result_false = pcc.engine.reverse_map(assessment_name, model_response_false)
        self.assertIn("assessmentDescription", result_false)  # schema metadata
        self.assertIn("templateId", result_false)  # schema metadata
        self.assertIsInstance(result_false["data"], list)
        self.assertEqual(len(result_false["data"]), 1)
        self.assertEqual(result_false["data"][0]["properties"]["A_1"], {"type": "checkbox", "value": None})  # False -> None

    def test_pcc_object_array_reverse(self):
        """Test PCC object array reverse formatter."""
        pcc = PCCAssessmentSchema()
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Select location(s) of skin abnormality(ies). Document a description of each skin abnormality.",
                                    "questionType": "gbdy",
                                    "length": 20,
                                    "responseOptions": [
                                        {"responseText": "Head", "responseValue": "0"},
                                        {"responseText": "Leg", "responseValue": "1"},
                                        {"responseText": "Hand", "responseValue": "2"},
                                        {"responseText": "Wrist", "responseValue": "3"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response with array format
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Select location(s) of skin abnormality(ies). Document a description of each skin abnormality.": [
                                    {"entry": "Head", "description": "soft"},
                                    {"entry": "Leg", "description": "smooth"},
                                    {"entry": "Wrist", "description": "blue"}
                                ]
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map
        result = pcc.engine.reverse_map(assessment_name, model_response)
        
        # Verify table formatting
        expected_table = [
            {"a0_A_1": "0", "b0_A_1": "soft"},   # Head
            {"a1_A_1": "1", "b1_A_1": "smooth"},  # Leg  
            {"a2_A_1": "3", "b2_A_1": "blue"}     # Wrist
        ]
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["A_1"], {"type": "table", "value": expected_table})

    def test_pcc_reverse_grouped_by_sections(self):
        """Test PCC reverse mapping with section grouping."""
        pcc = PCCAssessmentSchema()
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Patient Name",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "B",
                    "sectionDescription": "Vitals",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Vital Signs",
                            "questions": [
                                {
                                    "questionKey": "B_1",
                                    "questionNumber": "1",
                                    "questionText": "Blood Pressure",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Patient Name": "John Doe"
                            }
                        }
                    }
                },
                "B.Vitals": {
                    "assessmentQuestionGroups": {
                        "1.Vital Signs": {
                            "questions": {
                                "Blood Pressure": "120/80"
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map with grouping
        result = pcc.engine.reverse_map(assessment_name, model_response, group_by_containers=["sections"])
        
        # Verify grouped structure
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 2)  # Two sections
        
        # Find section A
        section_a = next(s for s in result["data"] if s.get("sectionCode") == "A")
        self.assertEqual(section_a["properties"]["A_1"], {"type": "text", "value": "John Doe"})
        
        # Find section B
        section_b = next(s for s in result["data"] if s.get("sectionCode") == "B")
        self.assertEqual(section_b["properties"]["B_1"], {"type": "text", "value": "120/80"})

    def test_formatter_access_to_original_schema_type(self):
        """Test that formatters can access original_schema_type from field metadata."""
        pcc = PCCAssessmentSchema()
        
        # Create a custom formatter that checks original_schema_type
        def test_formatter(engine, field_meta, model_value, table_name):
            original_type = field_meta.get("original_schema_type")
            return {field_meta["key"]: {"type": f"original_type_{original_type}", "value": model_value}}
        
        # Register the test formatter for txt and diag original types
        pcc.engine.register_reverse_formatter("test", "txt", test_formatter)
        pcc.engine.register_reverse_formatter("test", "diag", test_formatter)
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Patient Name",
                                    "questionType": "txt"  # Maps to string target type
                                },
                                {
                                    "questionKey": "A_2",
                                    "questionNumber": "2",
                                    "questionText": "Diagnosis",
                                    "questionType": "diag"  # Maps to string target type
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Patient Name": "John Doe",
                                "Diagnosis": "Hypertension"
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map
        result = pcc.engine.reverse_map(assessment_name, model_response, formatter_name="test")
        
        # Verify original_schema_type is accessible for both fields
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["A_1"], {"type": "original_type_txt", "value": "John Doe"})
        self.assertEqual(result["data"][0]["properties"]["A_2"], {"type": "original_type_diag", "value": "Hypertension"})

    def test_formatter_precedence_original_over_target(self):
        """Test that original type formatters take precedence over target type formatters."""
        pcc = PCCAssessmentSchema()
        
        # Create a formatter that shows it's using target type fallback
        def target_type_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": f"target_type_fallback_{field_meta.get('target_type')}", "value": model_value}}
        
        # Create a formatter that shows it's using original type
        def original_type_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": f"original_type_{field_meta.get('original_schema_type')}", "value": model_value}}
        
        # Register original type formatter (this should take precedence)
        pcc.engine.register_reverse_formatter("test", "rad", original_type_formatter)
        
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 12345,
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Admission",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupText": "Basic Info",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Gender",
                                    "questionType": "rad",  # Maps to single_select target type
                                    "responseOptions": [
                                        {"responseText": "Male", "responseValue": "1"},
                                        {"responseText": "Female", "responseValue": "2"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        assessment_id, assessment_name = pcc.register_assessment(1, assessment_schema)
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Gender": "Male"
                            }
                        }
                    }
                }
            }
        }
        
        # Reverse map
        result = pcc.engine.reverse_map(assessment_name, model_response, formatter_name="test")
        
        # Verify original type formatter takes precedence over target type formatter
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["A_1"], {"type": "original_type_rad", "value": "Male"})

    def test_mhcs_idt_5_day_section_gg(self):
        """Test MHCS IDT 5 Day Section GG assessment (templateId: 21242733)."""
        pcc = PCCAssessmentSchema()
        
        # Verify the assessment is registered
        self.assertIn(21242733, pcc.list_assessments())
        
        # Test JSON schema generation
        json_schema = pcc.get_json_schema(21242733)
        self.assertEqual(json_schema["title"], "MHCS IDT 5 Day Section GG")
        self.assertIn("sections", json_schema["properties"])
        
        # Test field metadata collection
        field_metadata = pcc.get_field_metadata(21242733)
        self.assertGreater(len(field_metadata), 0)
        
        # Verify we have fields from the expected sections
        section_keys = set()
        for field in field_metadata:
            level_keys = field.get("level_keys", [])
            if len(level_keys) > 1 and level_keys[0] == "sections":
                section_keys.add(level_keys[1])
        
        # Should have Cust_1 section (Prior Function and Functional Limitations)
        self.assertIn("Cust_1.Prior Function and Functional Limitations", section_keys)
        
        # Test reverse mapping with sample data
        model_response = {
            "table_name": "MHCS IDT 5 Day Section GG",
            "sections": {
                "Cust_1.Prior Function and Functional Limitations": {
                    "assessmentQuestionGroups": {
                        "01.Prior Functioning: Everyday Activities": {
                            "questions": {
                                "Self-Care: Code the resident's need for assistance with bathing, dressing, using the toilet, or eating prior to the current illness, exacerbation, or injury.": "Independent"
                            }
                        }
                    }
                }
            }
        }
        
        result = pcc.engine.reverse_map("MHCS IDT 5 Day Section GG", model_response)
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertIsInstance(result["data"][0]["properties"], dict)

    def test_mhcs_nursing_admission_assessment(self):
        """Test MHCS Nursing Admission Assessment - V 5 (templateId: 21244981)."""
        pcc = PCCAssessmentSchema()
        
        # Verify the assessment is registered
        self.assertIn(21244981, pcc.list_assessments())
        
        # Test JSON schema generation
        json_schema = pcc.get_json_schema(21244981)
        self.assertEqual(json_schema["title"], "MHCS Nursing Admission Assessment - V 5")
        self.assertIn("sections", json_schema["properties"])
        
        # Test field metadata collection
        field_metadata = pcc.get_field_metadata(21244981)
        self.assertGreater(len(field_metadata), 0)
        
        # Verify we have fields from the expected sections
        section_keys = set()
        for field in field_metadata:
            level_keys = field.get("level_keys", [])
            if len(level_keys) > 1 and level_keys[0] == "sections":
                section_keys.add(level_keys[1])
        
        # Should have Cust_1 section (Admission Details, Orientation to Facility and Preferences)
        self.assertIn("Cust_1.Admission Details, Orientation to Facility and Preferences", section_keys)
        
        # Test reverse mapping with sample data
        model_response = {
            "table_name": "MHCS Nursing Admission Assessment - V 5",
            "sections": {
                "Cust_1.Admission Details, Orientation to Facility and Preferences": {
                    "assessmentQuestionGroups": {
                        "A.Admission Details": {
                            "questions": {
                                "Resident arrived via:": "Wheelchair"
                            }
                        }
                    }
                }
            }
        }
        
        result = pcc.engine.reverse_map("MHCS Nursing Admission Assessment - V 5", model_response)
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertIsInstance(result["data"][0]["properties"], dict)

    def test_mhcs_nursing_daily_skilled_note(self):
        """Test MHCS Nursing Daily Skilled Note (templateId: 21242741)."""
        pcc = PCCAssessmentSchema()
        
        # Verify the assessment is registered
        self.assertIn(21242741, pcc.list_assessments())
        
        # Test JSON schema generation
        json_schema = pcc.get_json_schema(21242741)
        self.assertEqual(json_schema["title"], "MHCS Nursing Daily Skilled Note")
        self.assertIn("sections", json_schema["properties"])
        
        # Test field metadata collection
        field_metadata = pcc.get_field_metadata(21242741)
        self.assertGreater(len(field_metadata), 0)
        
        # Verify we have fields from the expected sections
        section_keys = set()
        for field in field_metadata:
            level_keys = field.get("level_keys", [])
            if len(level_keys) > 1 and level_keys[0] == "sections":
                section_keys.add(level_keys[1])
        
        # Should have Cust section (MHCS Nursing Daily Skilled Note)
        self.assertIn("Cust.MHCS Nursing Daily Skilled Note", section_keys)
        
        # Test reverse mapping with sample data
        model_response = {
            "table_name": "MHCS Nursing Daily Skilled Note",
            "sections": {
                "Cust.MHCS Nursing Daily Skilled Note": {
                    "assessmentQuestionGroups": {
                        "A.Vital Signs": {
                            "questions": {
                                "Vital signs": "Normal"
                            }
                        }
                    }
                }
            }
        }
        
        result = pcc.engine.reverse_map("MHCS Nursing Daily Skilled Note", model_response)
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertIsInstance(result["data"][0]["properties"], dict)

    def test_mhcs_nursing_weekly_skin_check(self):
        """Test MHCS Nursing Weekly Skin Check (templateId: 21244831)."""
        pcc = PCCAssessmentSchema()
        
        # Verify the assessment is registered
        self.assertIn(21244831, pcc.list_assessments())
        
        # Test JSON schema generation
        json_schema = pcc.get_json_schema(21244831)
        self.assertEqual(json_schema["title"], "MHCS Nursing Weekly Skin Check")
        self.assertIn("sections", json_schema["properties"])
        
        # Test field metadata collection
        field_metadata = pcc.get_field_metadata(21244831)
        self.assertGreater(len(field_metadata), 0)
        
        # Verify we have fields from the expected sections
        section_keys = set()
        for field in field_metadata:
            level_keys = field.get("level_keys", [])
            if len(level_keys) > 1 and level_keys[0] == "sections":
                section_keys.add(level_keys[1])
        
        # Should have Cust section (MHCS Nursing Weekly Skin Check)
        self.assertIn("Cust.MHCS Nursing Weekly Skin Check", section_keys)
        
        # Test reverse mapping with sample data
        model_response = {
            "table_name": "MHCS Nursing Weekly Skin Check",
            "sections": {
                "Cust.MHCS Nursing Weekly Skin Check": {
                    "assessmentQuestionGroups": {
                        ".Weekly Skin Check": {
                            "questions": {
                                "Each week, on the designated day, the nurse is to observe the resident's skin for any NEW skin impairments. If any NEW skin impairments are noted, the nurse must describe them below.": "No new skin impairments noted"
                            }
                        }
                    }
                }
            }
        }
        
        result = pcc.engine.reverse_map("MHCS Nursing Weekly Skin Check", model_response)
        self.assertIn("assessmentDescription", result)  # schema metadata
        self.assertIn("templateId", result)  # schema metadata
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertIsInstance(result["data"][0]["properties"], dict)

    def test_all_assessments_registered(self):
        """Test that all 4 assessment templates are properly registered."""
        pcc = PCCAssessmentSchema()
        
        # Verify all 4 assessments are registered
        registered_ids = pcc.list_assessments()
        expected_ids = [21242733, 21244981, 21242741, 21244831]
        
        self.assertEqual(len(registered_ids), 4)
        for expected_id in expected_ids:
            self.assertIn(expected_id, registered_ids)
        
        # Test that we can get JSON schemas for all assessments
        for assessment_id in expected_ids:
            json_schema = pcc.get_json_schema(assessment_id)
            self.assertIsInstance(json_schema, dict)
            self.assertIn("title", json_schema)
            self.assertIn("properties", json_schema)
        
        # Test that we can get field metadata for all assessments
        for assessment_id in expected_ids:
            field_metadata = pcc.get_field_metadata(assessment_id)
            self.assertIsInstance(field_metadata, list)
            self.assertGreater(len(field_metadata), 0)

    def test_assessment_field_counts(self):
        """Test field counts for each assessment to ensure they're properly loaded."""
        pcc = PCCAssessmentSchema()
        
        # Expected field counts (approximate, based on template complexity)
        expected_counts = {
            21242733: 30,   # MHCS IDT 5 Day Section GG - complex assessment (reduced due to gbdy -> object_array)
            21244981: 60,   # MHCS Nursing Admission Assessment - V 5 - very complex (reduced due to gbdy -> object_array)
            21242741: 20,   # MHCS Nursing Daily Skilled Note - moderate (reduced due to gbdy -> object_array)
            21244831: 5     # MHCS Nursing Weekly Skin Check - simple (reduced due to gbdy -> object_array)
        }
        
        for assessment_id, expected_min_count in expected_counts.items():
            field_metadata = pcc.get_field_metadata(assessment_id)
            actual_count = len(field_metadata)
            self.assertGreaterEqual(actual_count, expected_min_count, 
                                  f"Assessment {assessment_id} should have at least {expected_min_count} fields, got {actual_count}")

    def test_assessment_section_structure(self):
        """Test that assessments have proper section structure."""
        pcc = PCCAssessmentSchema()
        
        # Test each assessment has proper section structure
        assessments = [
            (21242733, "MHCS IDT 5 Day Section GG"),
            (21244981, "MHCS Nursing Admission Assessment - V 5"),
            (21242741, "MHCS Nursing Daily Skilled Note"),
            (21244831, "MHCS Nursing Weekly Skin Check")
        ]
        
        for assessment_id, expected_name in assessments:
            json_schema = pcc.get_json_schema(assessment_id)
            
            # Verify title matches
            self.assertEqual(json_schema["title"], expected_name)
            
            # Verify sections structure exists
            self.assertIn("sections", json_schema["properties"])
            sections_prop = json_schema["properties"]["sections"]
            self.assertEqual(sections_prop["type"], "object")
            self.assertFalse(sections_prop["additionalProperties"])
            
            # Verify sections have properties
            self.assertIn("properties", sections_prop)
            self.assertGreater(len(sections_prop["properties"]), 0)

    def test_json_schema_strict_structure_validation(self):
        """Test that all JSON schema properties have additionalProperties: false and proper required fields."""
        pcc = PCCAssessmentSchema()
        
        # Test with a real assessment that has various field types
        assessment_id = 21244831  # MHCS Nursing Weekly Skin Check
        json_schema = pcc.get_json_schema(assessment_id)
        
        def validate_schema_structure(schema_dict, path="root"):
            """Recursively validate schema structure."""
            issues = []
            
            if isinstance(schema_dict, dict):
                # Check if this is an object schema
                if schema_dict.get("type") == "object":
                    # Must have additionalProperties: false
                    if "additionalProperties" not in schema_dict:
                        issues.append(f"{path}: Missing 'additionalProperties' field")
                    elif schema_dict["additionalProperties"] is not False:
                        issues.append(f"{path}: 'additionalProperties' must be false, got {schema_dict['additionalProperties']}")
                    
                    # Check required field exists (can be empty array)
                    if "required" not in schema_dict:
                        issues.append(f"{path}: Missing 'required' field")
                    elif not isinstance(schema_dict["required"], list):
                        issues.append(f"{path}: 'required' must be a list, got {type(schema_dict['required'])}")
                    
                    # Recursively check properties
                    if "properties" in schema_dict:
                        for prop_name, prop_schema in schema_dict["properties"].items():
                            prop_issues = validate_schema_structure(prop_schema, f"{path}.properties.{prop_name}")
                            issues.extend(prop_issues)
                
                # Check array items if present
                elif schema_dict.get("type") == "array" and "items" in schema_dict:
                    items_issues = validate_schema_structure(schema_dict["items"], f"{path}.items")
                    issues.extend(items_issues)
                
                # Recursively check other nested objects
                for key, value in schema_dict.items():
                    if key not in ["type", "properties", "items", "required", "additionalProperties", "description", "enum", "const", "maxItems", "minItems"]:
                        nested_issues = validate_schema_structure(value, f"{path}.{key}")
                        issues.extend(nested_issues)
            
            return issues
        
        # Validate the entire schema
        issues = validate_schema_structure(json_schema)
        
        # Report any issues found
        if issues:
            print(f"\nSchema structure validation issues found:")
            for issue in issues:
                print(f"  - {issue}")
            self.fail(f"Found {len(issues)} schema structure issues. See output above.")
        
        # Additional specific checks for key areas
        self.assertIn("properties", json_schema)
        self.assertFalse(json_schema.get("additionalProperties", True), 
                        "Root schema must have additionalProperties: false")
        
        # Check sections container
        sections_prop = json_schema["properties"]["sections"]
        self.assertEqual(sections_prop["type"], "object")
        self.assertFalse(sections_prop.get("additionalProperties", True),
                        "Sections container must have additionalProperties: false")
        
        # Check that we have some sections
        self.assertIn("properties", sections_prop)
        self.assertGreater(len(sections_prop["properties"]), 0, "Should have at least one section")
        
        # Check a specific section structure
        section_names = list(sections_prop["properties"].keys())
        if section_names:
            first_section = sections_prop["properties"][section_names[0]]
            self.assertEqual(first_section["type"], "object")
            self.assertFalse(first_section.get("additionalProperties", True),
                            f"Section '{section_names[0]}' must have additionalProperties: false")
            
            # Check assessmentQuestionGroups
            if "assessmentQuestionGroups" in first_section["properties"]:
                groups_prop = first_section["properties"]["assessmentQuestionGroups"]
                self.assertEqual(groups_prop["type"], "object")
                self.assertFalse(groups_prop.get("additionalProperties", True),
                                "assessmentQuestionGroups must have additionalProperties: false")
                
                # Check questions if present
                if "questions" in groups_prop["properties"]:
                    questions_prop = groups_prop["properties"]["questions"]
                    self.assertEqual(questions_prop["type"], "object")
                    self.assertFalse(questions_prop.get("additionalProperties", True),
                                    "questions must have additionalProperties: false")

    def test_pcc_ui_formatter_unpacking(self):
        """Test PCC-UI formatter unpacking capabilities."""
        pcc = PCCAssessmentSchema()
        
        # Create a test assessment with various field types
        test_assessment = {
            "assessmentDescription": "Test Assessment",
            "templateId": 99999,
            "sections": [{
                "sectionCode": "A",
                "sectionDescription": "Test Section",
                "assessmentQuestionGroups": [{
                    "groupNumber": "1",
                    "groupText": "Test Group",
                    "questions": [
                        {
                            "questionKey": "A_1",
                            "questionNumber": "1",
                            "questionText": "Text field",
                            "questionType": "txt"
                        },
                        {
                            "questionKey": "A_2",
                            "questionNumber": "2",
                            "questionText": "Single select",
                            "questionType": "rad",
                            "responseOptions": [
                                {"responseText": "Option A", "responseValue": "a"},
                                {"responseText": "Option B", "responseValue": "b"}
                            ]
                        },
                        {
                            "questionKey": "A_3",
                            "questionNumber": "3",
                            "questionText": "Multi select",
                            "questionType": "mcs",
                            "responseOptions": [
                                {"responseText": "Choice 1", "responseValue": "1"},
                                {"responseText": "Choice 2", "responseValue": "2"},
                                {"responseText": "Choice 3", "responseValue": "3"}
                            ]
                        },
                        {
                            "questionKey": "A_4",
                            "questionNumber": "4",
                            "questionText": "Table field",
                            "questionType": "gbdy",
                            "length": 3,
                            "responseOptions": [
                                {"responseText": "Head", "responseValue": "0"},
                                {"responseText": "Arm", "responseValue": "1"},
                                {"responseText": "Leg", "responseValue": "2"}
                            ]
                        }
                    ]
                }]
            }]
        }
        
        # Register the test assessment
        table_id, table_name = pcc.engine.register_table(99999, test_assessment)
        
        # Test model response with various field types
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Text field": "Hello World",
                                "Single select": "Option A",
                                "Multi select": ["Choice 1", "Choice 3"],
                                "Table field": [
                                    {"entry": "Head", "description": "soft tissue"},
                                    {"entry": "Arm", "description": "bruised"}
                                ]
                            }
                        }
                    }
                }
            }
        }
        
        # Test with pcc-ui formatter
        result = pcc.reverse_map(99999, model_response, formatter_name="pcc-ui")
        
        # Verify structure
        self.assertIn("assessmentDescription", result)
        self.assertIn("templateId", result)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        
        # Verify section structure
        self.assertEqual(len(result["data"]), 1)
        section = result["data"][0]
        self.assertIn("sectionCode", section)
        self.assertIn("fields", section)
        self.assertIsInstance(section["fields"], list)
        
        # Verify field unpacking
        fields = section["fields"]
        field_keys = [field["key"] for field in fields]
        
        # Basic field - single entry
        self.assertIn("A_1", field_keys)
        text_field = next(f for f in fields if f["key"] == "A_1")
        self.assertEqual(text_field["type"], "txt")
        self.assertEqual(text_field["value"], "Hello World")
        
        # Single select - single entry with responseValue
        self.assertIn("A_2", field_keys)
        single_field = next(f for f in fields if f["key"] == "A_2")
        self.assertEqual(single_field["type"], "rad")
        self.assertEqual(single_field["value"], "a")  # responseValue, not responseText
        
        # Multi-select - unpacked into multiple entries (same key for all entries)
        self.assertGreaterEqual(field_keys.count("A_3"), 2)
        multi_entries = [f for f in fields if f["key"] == "A_3"]
        multi_field_0, multi_field_1 = multi_entries[0], multi_entries[1]
        self.assertEqual(multi_field_0["type"], "mcs")
        self.assertEqual(multi_field_0["value"], "1")  # responseValue for "Choice 1"
        self.assertEqual(multi_field_1["type"], "mcs")
        self.assertEqual(multi_field_1["value"], "3")  # responseValue for "Choice 3"
        
        # Object array - unpacked into aN/bN pairs
        self.assertIn("a0_A_4", field_keys)
        self.assertIn("b0_A_4", field_keys)
        self.assertIn("a1_A_4", field_keys)
        self.assertIn("b1_A_4", field_keys)
        
        a0_field = next(f for f in fields if f["key"] == "a0_A_4")
        b0_field = next(f for f in fields if f["key"] == "b0_A_4")
        a1_field = next(f for f in fields if f["key"] == "a1_A_4")
        b1_field = next(f for f in fields if f["key"] == "b1_A_4")
        
        self.assertEqual(a0_field["type"], "gbdy")
        self.assertEqual(a0_field["value"], "0")  # responseValue for "Head"
        self.assertEqual(b0_field["type"], "gbdy")
        self.assertEqual(b0_field["value"], "soft tissue")
        
        self.assertEqual(a1_field["type"], "gbdy")
        self.assertEqual(a1_field["value"], "1")  # responseValue for "Arm"
        self.assertEqual(b1_field["type"], "gbdy")
        self.assertEqual(b1_field["value"], "bruised")
        
        # Verify all fields have original types
        for field in fields:
            self.assertIn("type", field)
            self.assertIn("value", field)
            # All types should be original PCC types
            self.assertIn(field["type"], ["txt", "rad", "mcs", "gbdy"])
            
            # Verify html_type is present and correct
            self.assertIn("html_type", field)
            self.assertIsInstance(field["html_type"], str)
            
            # Verify some specific mappings
            if field["type"] == "txt":
                self.assertIn(field["html_type"], ["textarea_singleline", "textarea_multiline"])
            elif field["type"] == "rad":
                self.assertEqual(field["html_type"], "radio_buttons")
            elif field["type"] == "mcs":
                self.assertEqual(field["html_type"], "checkbox_multi")
            elif field["type"] == "gbdy":
                # For gbdy fields, html_type depends on whether it's an entry or description
                if field["key"].startswith("a"):
                    self.assertEqual(field["html_type"], "combobox")
                elif field["key"].startswith("b"):
                    self.assertEqual(field["html_type"], "textarea_singleline")

    def test_reverse_map_pcc_ui_defaults(self):
        """Test reverse_map method with PCC-UI defaults."""
        pcc = PCCAssessmentSchema()
        
        # Test data with some fields
        model_response = {
            "table_name": "MHCS Nursing Weekly Skin Check",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Test Question": "Test Value"
                            }
                        }
                    }
                }
            }
        }
        
        # Test with default PCC-UI parameters
        result = pcc.reverse_map(21244831, model_response)
        
        # Verify structure with new defaults
        self.assertIn("assessmentDescription", result)
        self.assertIn("templateId", result)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        
        # Verify the data structure has the new defaults
        if result["data"]:
            first_section = result["data"][0]
            self.assertIn("sectionCode", first_section)
            self.assertIn("fields", first_section)  # properties_key = "fields"
            self.assertIsInstance(first_section["fields"], list)  # pack_properties_as = "array"
            
            # Verify fields is an array of objects
            if first_section["fields"]:
                first_field = first_section["fields"][0]
                self.assertIsInstance(first_field, dict)
                self.assertIn("type", first_field)
                self.assertIn("value", first_field)
        
        # Test that explicit parameters override defaults
        result_explicit = pcc.reverse_map(
            21244831, 
            model_response,
            formatter_name="default",
            group_by_containers=["sections"],
            properties_key="properties",
            pack_properties_as="object"
        )
        
        # Should have different structure
        if result_explicit["data"]:
            first_section = result_explicit["data"][0]
            self.assertIn("properties", first_section)  # properties_key = "properties"
            self.assertIsInstance(first_section["properties"], dict)  # pack_properties_as = "object"

    def test_reverse_map_by_formatter_name(self):
        """Test reverse_map method with different formatter names."""
        pcc = PCCAssessmentSchema()
        
        # Test data - use a simple structure that should work
        model_response = {
            "table_name": "MHCS Nursing Weekly Skin Check",
            "sections": {}
        }
        
        # Test with default formatter (pcc-ui)
        result_default = pcc.reverse_map(21244831, model_response)
        self.assertIn("assessmentDescription", result_default)
        self.assertIn("templateId", result_default)
        self.assertIn("data", result_default)
        
        # Test with explicit pcc-ui formatter name (should be same as default)
        result_explicit = pcc.reverse_map(21244831, model_response, formatter_name="pcc-ui")
        self.assertEqual(result_default, result_explicit)
        
        # Test with default formatter (different output format)
        result_default_formatter = pcc.reverse_map(21244831, model_response, formatter_name="default")
        self.assertIn("assessmentDescription", result_default_formatter)
        self.assertIn("templateId", result_default_formatter)
        self.assertIn("data", result_default_formatter)
        
        # Test with custom parameters
        result_custom = pcc.reverse_map(
            21244831, 
            model_response, 
            formatter_name="default",
            group_by_containers=["sections"],
            properties_key="fields",
            pack_properties_as="array"
        )
        self.assertIn("assessmentDescription", result_custom)
        self.assertIn("templateId", result_custom)
        self.assertIn("data", result_custom)
        
        # Verify the data structure has the custom properties_key
        if result_custom["data"]:
            first_section = result_custom["data"][0]
            self.assertIn("fields", first_section)
            self.assertIsInstance(first_section["fields"], list)

    def test_object_array_validation_strict_schema(self):
        """Test that object_array (gbdy) fields enforce strict schema validation."""
        pcc = PCCAssessmentSchema()
        
        # Create a test assessment with a gbdy field
        assessment_schema = {
            "assessmentDescription": "Test Assessment",
            "templateId": 99999,
            "sections": [{
                "sectionCode": "A",
                "sectionDescription": "Test Section",
                "assessmentQuestionGroups": [{
                    "groupNumber": "1",
                    "groupText": "Test Group",
                    "questions": [{
                        "questionKey": "A_1",
                        "questionNumber": "1",
                        "questionText": "Select skin locations",
                        "questionType": "gbdy",
                        "length": 5,
                        "responseOptions": [
                            {"responseText": "Head", "responseValue": "0"},
                            {"responseText": "Arm", "responseValue": "1"},
                            {"responseText": "Leg", "responseValue": "2"}
                        ]
                    }]
                }]
            }]
        }
        
        table_id, table_name = pcc.engine.register_table(99999, assessment_schema)
        json_schema = pcc.get_json_schema(99999)
        
        # 1. Verify schema structure
        # Navigate to the items schema for the gbdy field
        items_schema = json_schema["properties"]["sections"]["properties"]["A.Test Section"]["properties"]["assessmentQuestionGroups"]["properties"]["1.Test Group"]["properties"]["questions"]["properties"]["Select skin locations"]
        
        self.assertEqual(items_schema["type"], "array")
        self.assertIn("items", items_schema)
        self.assertEqual(items_schema["items"]["type"], "object")
        self.assertFalse(items_schema["items"].get("additionalProperties", True), 
                        "additionalProperties should be explicitly set to false")
        self.assertIn("required", items_schema["items"])
        self.assertEqual(set(items_schema["items"]["required"]), {"entry", "description"})
        
        # 2. Valid data passes
        valid_data = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Select skin locations": [
                                    {"entry": "Head", "description": "soft tissue"},
                                    {"entry": "Arm", "description": "bruised"}
                                ]
                            }
                        }
                    }
                }
            }
        }
        is_valid, errors = pcc.validate(99999, valid_data)
        self.assertTrue(is_valid, f"Valid data should pass: {errors}")
        
        # 3. Missing required field 'entry'
        missing_entry = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Select skin locations": [
                                    {"description": "soft tissue"}  # Missing 'entry'
                                ]
                            }
                        }
                    }
                }
            }
        }
        is_valid, errors = pcc.validate(99999, missing_entry)
        self.assertFalse(is_valid, "Should reject object missing 'entry' field")
        
        # 4. Missing required field 'description'
        missing_description = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Select skin locations": [
                                    {"entry": "Head"}  # Missing 'description'
                                ]
                            }
                        }
                    }
                }
            }
        }
        is_valid, errors = pcc.validate(99999, missing_description)
        self.assertFalse(is_valid, "Should reject object missing 'description' field")
        
        # 5. Additional properties
        extra_property = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Select skin locations": [
                                    {"entry": "Head", "description": "soft tissue", "extra": "field"}
                                ]
                            }
                        }
                    }
                }
            }
        }
        is_valid, errors = pcc.validate(99999, extra_property)
        self.assertFalse(is_valid, "Should reject object with additional properties")
        
        # 6. Empty array is valid
        empty_array = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Test Section": {
                    "assessmentQuestionGroups": {
                        "1.Test Group": {
                            "questions": {
                                "Select skin locations": []
                            }
                        }
                    }
                }
            }
        }
        is_valid, errors = pcc.validate(99999, empty_array)
        self.assertTrue(is_valid, f"Empty array should be valid: {errors}")

    def test_list_assessments_info(self):
        """Test that list_assessments_info returns id and name for all registered assessments."""
        pcc = PCCAssessmentSchema()
        info = pcc.list_assessments_info()
        
        # Should be a list of 4 entries
        self.assertIsInstance(info, list)
        self.assertEqual(len(info), 4)
        
        # Validate structure of each entry
        for entry in info:
            self.assertIn("id", entry)
            self.assertIn("name", entry)
            self.assertIsInstance(entry["id"], int)
            self.assertIsInstance(entry["name"], str)
            self.assertGreater(len(entry["name"].strip()), 0)
        
        # Validate specific expected IDs and names
        expected = {
            21242733: "MHCS IDT 5 Day Section GG",
            21244981: "MHCS Nursing Admission Assessment - V 5",
            21242741: "MHCS Nursing Daily Skilled Note",
            21244831: "MHCS Nursing Weekly Skin Check",
        }
        ids = {e["id"] for e in info}
        self.assertEqual(set(expected.keys()), ids)
        for e in info:
            self.assertEqual(expected[e["id"]], e["name"]) 

    def test_generate_and_save_formatted_output_idt_gg(self):
        pcc = PCCAssessmentSchema()
        artifact_dir = os.path.join(os.path.dirname(__file__), "_formatted_outputs", "pcc")
        res = _reverse_and_save(pcc, 21242733, artifact_dir)
        self.assertTrue(os.path.exists(res["path"]))
        self.assertIn("assessmentDescription", res["grouped"])  # schema metadata
        self.assertIn("templateId", res["grouped"])  # schema metadata
        self.assertIn("data", res["grouped"])
        self.assertIsInstance(res["grouped"]["data"], list)
        self.assertGreater(len(res["grouped"]["data"]), 0)

    def test_generate_and_save_formatted_output_admission(self):
        pcc = PCCAssessmentSchema()
        artifact_dir = os.path.join(os.path.dirname(__file__), "_formatted_outputs", "pcc")
        res = _reverse_and_save(pcc, 21244981, artifact_dir)
        self.assertTrue(os.path.exists(res["path"]))
        self.assertIn("assessmentDescription", res["grouped"])  # schema metadata
        self.assertIn("templateId", res["grouped"])  # schema metadata
        self.assertIn("data", res["grouped"])
        self.assertIsInstance(res["grouped"]["data"], list)
        self.assertGreater(len(res["grouped"]["data"]), 0)

    def test_generate_and_save_formatted_output_daily(self):
        pcc = PCCAssessmentSchema()
        artifact_dir = os.path.join(os.path.dirname(__file__), "_formatted_outputs", "pcc")
        res = _reverse_and_save(pcc, 21242741, artifact_dir)
        self.assertTrue(os.path.exists(res["path"]))
        self.assertIn("assessmentDescription", res["grouped"])  # schema metadata
        self.assertIn("templateId", res["grouped"])  # schema metadata
        self.assertIn("data", res["grouped"])
        self.assertIsInstance(res["grouped"]["data"], list)
        self.assertGreater(len(res["grouped"]["data"]), 0)

    def test_generate_and_save_formatted_output_skin(self):
        pcc = PCCAssessmentSchema()
        artifact_dir = os.path.join(os.path.dirname(__file__), "_formatted_outputs", "pcc")
        res = _reverse_and_save(pcc, 21244831, artifact_dir)
        self.assertTrue(os.path.exists(res["path"]))
        self.assertIn("assessmentDescription", res["grouped"])  # schema metadata
        self.assertIn("templateId", res["grouped"])  # schema metadata
        self.assertIn("data", res["grouped"])
        self.assertIsInstance(res["grouped"]["data"], list)
        self.assertGreater(len(res["grouped"]["data"]), 0)

    def test_generate_complete_model_responses_all_assessments(self):
        """Generate complete model responses with valid values for all fields in all assessments."""
        pcc = PCCAssessmentSchema()
        
        # Assessment IDs and their expected names
        assessments = [
            (21242733, "MHCS IDT 5 Day Section GG"),
            (21244981, "MHCS Nursing Admission Assessment - V 5"),
            (21242741, "MHCS Nursing Daily Skilled Note"),
            (21244831, "MHCS Nursing Weekly Skin Check")
        ]
        
        for assessment_id, assessment_name in assessments:
            with self.subTest(assessment=assessment_name):
                # Get JSON schema
                json_schema = pcc.get_json_schema(assessment_id)
                
                # Generate complete model response by following JSON schema structure
                model_response = self._generate_model_from_json_schema(json_schema)
                
                # Validate the model response
                is_valid, errors = pcc.validate(assessment_id, model_response)
                self.assertTrue(is_valid, 
                              f"Model validation failed for {assessment_name}: {errors}")
                
                # Test reverse mapping
                reverse_result = pcc.engine.reverse_map(assessment_name, model_response, group_by_containers=["sections"])
                self.assertIn("assessmentDescription", reverse_result)  # schema metadata
                self.assertIn("templateId", reverse_result)  # schema metadata
                self.assertIn("data", reverse_result)
                self.assertIsInstance(reverse_result["data"], list)
                self.assertGreater(len(reverse_result["data"]), 0)
                
                # Save the complete model response for inspection
                self._save_complete_model_response(assessment_id, assessment_name, model_response)

    def _generate_model_from_json_schema(self, json_schema):
        """Generate a complete model by following the JSON schema structure directly."""
        model = {"table_name": json_schema["title"]}
        
        # Process sections
        if "properties" in json_schema and "sections" in json_schema["properties"]:
            sections_schema = json_schema["properties"]["sections"]["properties"]
            model["sections"] = {}
            
            for section_name, section_def in sections_schema.items():
                model["sections"][section_name] = {}
                
                # Process assessmentQuestionGroups
                if "properties" in section_def and "assessmentQuestionGroups" in section_def["properties"]:
                    groups_schema = section_def["properties"]["assessmentQuestionGroups"]["properties"]
                    model["sections"][section_name]["assessmentQuestionGroups"] = {}
                    
                    for group_name, group_def in groups_schema.items():
                        model["sections"][section_name]["assessmentQuestionGroups"][group_name] = {}
                        
                        # Process questions
                        if "properties" in group_def and "questions" in group_def["properties"]:
                            questions_schema = group_def["properties"]["questions"]["properties"]
                            model["sections"][section_name]["assessmentQuestionGroups"][group_name]["questions"] = {}
                            
                            for question_name, question_def in questions_schema.items():
                                # Generate value based on question schema
                                value = self._generate_value_from_question_schema(question_def, question_name=question_name)
                                model["sections"][section_name]["assessmentQuestionGroups"][group_name]["questions"][question_name] = value
        
        return model

    def _generate_value_from_question_schema(self, question_def, index=0, question_name=None):
        """Generate a valid value based on the question schema definition."""
        question_type = question_def.get("type")
        
        # Check if it's a date field first (before handling union types)
        if "format" in question_def and question_def["format"] == "date":
            return "2024-12-15"
        
        # Handle union types (e.g., ['string', 'null'])
        if isinstance(question_type, list):
            # Remove 'null' and use the first non-null type
            non_null_types = [t for t in question_type if t != 'null']
            if non_null_types:
                question_type = non_null_types[0]
            else:
                return None
        
        if question_type == "string":
            # Check if it's an instruction field (has const value)
            if "const" in question_def:
                return question_def["const"]
            # Check if it has enum options
            elif "enum" in question_def:
                enum_values = [v for v in question_def["enum"] if v is not None]
                if enum_values:
                    # Filter out special response values for radio buttons (prefer valid digits/letters)
                    # Avoid responseText values that start with "Not assessed" or "Blank"
                    valid_values = [
                        v for v in enum_values 
                        if not (isinstance(v, str) and (v.startswith("Not assessed") or v.startswith("Blank") or v == "Unable to answer"))
                    ]
                    if valid_values:
                        # Use index to pick different valid enum values for array items
                        return valid_values[index % len(valid_values)]
                    else:
                        # Fallback to any enum value if no valid ones found
                        return enum_values[index % len(enum_values)]
            # Check if it's a date field by looking at description
            elif "description" in question_def and "date" in question_def["description"].lower():
                return "2024-12-15"
            # Default string value
            return "Sample text"
            
        elif question_type == "boolean":
            # Prefer true over false in a 3:1 ratio for more realistic test data
            # Use question name hash to ensure consistent results for same field
            if question_name:
                hash_value = hash(question_name) % 4  # 0, 1, 2, 3
                return hash_value < 3  # 3 out of 4 cases return True
            else:
                return True  # Default to True if no name
            
        elif question_type in ["integer", "number"]:
            return 42
            
        elif question_type == "array":
            # For arrays, check if it has items schema
            if "items" in question_def:
                items_schema = question_def["items"]
                max_items = question_def.get("maxItems", 10)
                
                # Generate up to 4 items or up to maxItems, whichever is smaller
                num_items = min(4, max_items)
                
                result = []
                for i in range(num_items):
                    item = self._generate_value_from_question_schema(items_schema, index=i, question_name=f"{question_name}_item_{i}")
                    result.append(item)
                return result
            return []
            
        elif question_type == "object":
            # For objects, generate properties
            if "properties" in question_def:
                obj = {}
                for prop_name, prop_def in question_def["properties"].items():
                    if prop_name == "entry" and "enum" in prop_def:
                        # For entry fields with enum, use the index to pick different values
                        enum_values = [v for v in prop_def["enum"] if v is not None]
                        if enum_values:
                            obj[prop_name] = enum_values[index % len(enum_values)]
                        else:
                            obj[prop_name] = self._generate_value_from_question_schema(prop_def)
                    else:
                        obj[prop_name] = self._generate_value_from_question_schema(prop_def)
                return obj
            return {}
        
        return None

    def _generate_complete_model_response(self, pcc, assessment_id, field_metadata):
        """Generate a complete model response with valid values for all fields."""
        json_schema = pcc.get_json_schema(assessment_id)
        model_response = {"table_name": json_schema["title"]}
        
        # Group fields by their target type for better value generation
        fields_by_type = {}
        for field_meta in field_metadata:
            target_type = field_meta.get("target_type")
            if target_type not in fields_by_type:
                fields_by_type[target_type] = []
            fields_by_type[target_type].append(field_meta)
        
        # Generate values for each field
        for field_meta in field_metadata:
            if field_meta.get("is_virtual_container_child"):
                continue  # Skip virtual container children
                
            value = self._generate_value_for_field_type(field_meta, fields_by_type, field_metadata)
            self._set_value_in_model_response(model_response, field_meta, value)
        
        return model_response

    def _generate_value_for_field_type(self, field_meta, fields_by_type, field_metadata):
        """Generate appropriate value based on field type."""
        target_type = field_meta.get("target_type")
        original_type = field_meta.get("original_schema_type")
        field_key = field_meta.get("key")
        
        # Debug: print what we're generating for specific problematic fields
        if field_key in ["Cust_A_1", "Cust_1_A"]:
            print(f"DEBUG: Generating value for {field_key} - target_type: {target_type}, original_type: {original_type}")
            print(f"DEBUG: responseOptions: {field_meta.get('responseOptions', [])}")
            field_schema = field_meta.get("field_schema", {})
            print(f"DEBUG: field_schema keys: {list(field_schema.keys())}")
            print(f"DEBUG: enum values: {field_schema.get('enum', [])}")
        
        if target_type == "string" or original_type in ["txt", "diag"]:
            return f"Sample text for {field_key}"
            
        elif target_type == "integer" or original_type in ["num", "int"]:
            return 42
            
        elif target_type == "boolean" or original_type == "chk":
            # Prefer true over false in a 3:1 ratio for more realistic test data
            # Use field key hash to ensure consistent results for same field
            field_key = field_meta.get("key", "")
            hash_value = hash(field_key) % 4  # 0, 1, 2, 3
            return hash_value < 3  # 3 out of 4 cases return True
            
        elif target_type == "single_select" or original_type in ["rad", "radh", "cmb", "hck"]:
            response_options = field_meta.get("responseOptions", [])
            if response_options:
                # Filter out special response values (prefer valid digits/letters)
                # Avoid responseText values that start with "Not assessed" or "Blank"
                valid_options = [
                    opt for opt in response_options 
                    if not (opt.get("responseText", "").startswith("Not assessed") or 
                           opt.get("responseText", "").startswith("Blank") or 
                           opt.get("responseText") == "Unable to answer")
                ]
                if valid_options:
                    return valid_options[0]["responseText"]
                else:
                    # Fallback to first option if no valid ones found
                    return response_options[0]["responseText"]
            
            # If no responseOptions, try to get enum values from field schema
            field_schema = field_meta.get("field_schema", {})
            enum_values = field_schema.get("enum")
            if enum_values and len(enum_values) > 0:
                # Filter out None values and special response values
                valid_options = [
                    v for v in enum_values 
                    if v is not None and not (isinstance(v, str) and (v.startswith("Not assessed") or v.startswith("Blank") or v == "Unable to answer"))
                ]
                if valid_options:
                    return valid_options[0]
                else:
                    # Fallback to any non-None value if no valid ones found
                    fallback_options = [v for v in enum_values if v is not None]
                    if fallback_options:
                        return fallback_options[0]
            
            # If no valid options found, return None (let validation handle it)
            return None
            
        elif target_type == "multiple_select" or original_type in ["mcs", "mcsh"]:
            response_options = field_meta.get("responseOptions", [])
            if response_options:
                # Return first 2-3 options as array, but ensure they're valid responseText values
                max_options = min(3, len(response_options))
                return [opt["responseText"] for opt in response_options[:max_options]]
            
            # If no responseOptions, try to get enum values from field schema
            field_schema = field_meta.get("field_schema", {})
            enum_values = field_schema.get("enum")
            if enum_values and len(enum_values) > 0:
                # Filter out None values and return first 2-3 valid options
                valid_options = [v for v in enum_values if v is not None]
                if valid_options:
                    max_options = min(2, len(valid_options))
                    return valid_options[:max_options]
            
            # If no valid options found, return empty list for multi-select
            return []
            
        elif target_type == "date" or original_type == "dte":
            return "2024-12-15"
            
        elif target_type == "datetime" or original_type == "dttm":
            return "2024-12-15T14:30:00"
            
        elif target_type == "object_array" or original_type == "gbdy":
            # Generate array of objects for gbdy fields
            field_schema = field_meta.get("field_schema", {})
            response_options = field_schema.get("responseOptions", [])
            if response_options:
                # Generate up to 4 entries using first 4 options
                num_entries = min(4, len(response_options))
                entries = []
                
                for i in range(num_entries):
                    option = response_options[i]
                    entry_text = option.get("responseText", "")
                    description = f"Sample description for {entry_text}"
                    entries.append({
                        "entry": entry_text,
                        "description": description
                    })
                return entries
            return []
            
        elif target_type == "instructions" or original_type == "inst":
            # For instruction fields, construct the value from questionTitle and questionText
            field_schema = field_meta.get("field_schema", {})
            const_value = field_schema.get("const")
            if const_value:
                return const_value
            
            # If no const value, construct from questionTitle and questionText (like the schema engine does)
            question_title = field_schema.get("questionTitle", "")
            question_text = field_schema.get("questionText", "")
            
            # Simple HTML sanitization (remove HTML tags)
            import re
            title_value = re.sub(r'<[^>]+>', '', question_title).strip()
            text_value = re.sub(r'<[^>]+>', '', question_text).strip()
            
            if title_value and text_value:
                return f"{title_value}. {text_value}"
            elif title_value:
                return title_value
            elif text_value:
                return text_value
            else:
                return f"Instructions for {field_meta['key']}"
            
        else:
            return f"Default value for {field_meta['key']}"

    def _set_value_in_model_response(self, model_response, field_meta, value):
        """Set value in model response using field metadata level_keys."""
        level_keys = field_meta.get("level_keys", [])
        property_key = field_meta.get("property_key")
        
        if not level_keys or not property_key:
            return
            
        # Navigate/create nested structure
        current = model_response
        for i, level_key in enumerate(level_keys[:-1]):
            if level_key not in current:
                # Create container based on meta-schema structure
                if i == 0 and level_key == "sections":
                    # This is the top-level container - create object
                    current[level_key] = {}
                else:
                    # This is a nested container - create object
                    current[level_key] = {}
            current = current[level_key]
        
        # Set the final value
        final_key = level_keys[-1]
        if final_key not in current:
            current[final_key] = {}
        current[final_key][property_key] = value

    def _verify_all_fields_populated(self, model_response, field_metadata):
        """Verify that all fields have non-null values."""
        for field_meta in field_metadata:
            if field_meta.get("is_virtual_container_child"):
                continue
                
            level_keys = field_meta.get("level_keys", [])
            property_key = field_meta.get("property_key")
            
            if not level_keys or not property_key:
                continue
                
            # Navigate to the field value
            current = model_response
            for level_key in level_keys:
                if level_key in current:
                    current = current[level_key]
                else:
                    self.fail(f"Field {field_meta['key']} not found in model response")
                    return
            
            if property_key in current:
                field_value = current[property_key]
                
                # Skip null check for instruction fields and fields with no valid options
                target_type = field_meta.get("target_type")
                if target_type != "instructions":
                    # Check if field has any valid options
                    response_options = field_meta.get("responseOptions", [])
                    field_schema = field_meta.get("field_schema", {})
                    enum_values = field_schema.get("enum", [])
                    has_valid_options = (response_options and len(response_options) > 0) or (enum_values and len([v for v in enum_values if v is not None]) > 0)
                    
                    if has_valid_options:
                        self.assertIsNotNone(field_value, f"Field {field_meta['key']} has null value but has valid options")
                    # If no valid options, allow null values
                
                # Additional checks for specific types
                if target_type == "multiple_select":
                    self.assertIsInstance(field_value, list, f"Multi-select field {field_meta['key']} should be a list")
                    if has_valid_options:
                        self.assertGreater(len(field_value), 0, f"Multi-select field {field_meta['key']} should have values")
                elif target_type == "virtual_container":
                    self.assertIsInstance(field_value, dict, f"Table field {field_meta['key']} should be a dict")
                    self.assertGreater(len(field_value), 0, f"Table field {field_meta['key']} should have values")

    def _validate_field_value_type(self, field_type, value, field_key):
        """Validate that a field value conforms to its expected type."""
        if field_type in ["txt", "diag"]:
            # Text fields should have string values or None
            self.assertTrue(
                isinstance(value, str) or value is None,
                f"Field {field_key} (type: {field_type}) should have string or None value, got {type(value).__name__}: {value}"
            )
        elif field_type in ["num", "numde"]:
            # Numeric fields should have numeric values or None
            self.assertTrue(
                isinstance(value, (int, float)) or value is None,
                f"Field {field_key} (type: {field_type}) should have numeric or None value, got {type(value).__name__}: {value}"
            )
        elif field_type == "chk":
            # Checkbox fields should have 1, None, or boolean values
            self.assertTrue(
                value in [1, None, True, False],
                f"Field {field_key} (type: {field_type}) should have 1, None, True, or False value, got {type(value).__name__}: {value}"
            )
        elif field_type in ["rad", "radh", "cmb", "hck"]:
            # Single select fields should have responseValue codes (1-2 chars) or None
            self.assertTrue(
                isinstance(value, str) or value is None,
                f"Field {field_key} (type: {field_type}) should have string or None value, got {type(value).__name__}: {value}"
            )
            if isinstance(value, str):
                # ResponseValue codes should be 1-2 characters (letters or numbers)
                self.assertLessEqual(
                    len(value), 2,
                    f"Field {field_key} (type: {field_type}) should have 1-2 character responseValue code, got: {value}"
                )
                # Should be alphanumeric only
                self.assertRegex(
                    value, r'^[a-zA-Z0-9]+$',
                    f"Field {field_key} (type: {field_type}) should have alphanumeric responseValue code, got: {value}"
                )
        elif field_type in ["mcs", "mcsh"]:
            # Multi-select fields should have responseValue codes (1-2 chars) or None
            self.assertTrue(
                isinstance(value, str) or value is None,
                f"Field {field_key} (type: {field_type}) should have string or None value, got {type(value).__name__}: {value}"
            )
            if isinstance(value, str):
                # ResponseValue codes should be 1-2 characters (letters or numbers)
                self.assertLessEqual(
                    len(value), 2,
                    f"Field {field_key} (type: {field_type}) should have 1-2 character responseValue code, got: {value}"
                )
                # Should be alphanumeric only
                self.assertRegex(
                    value, r'^[a-zA-Z0-9]+$',
                    f"Field {field_key} (type: {field_type}) should have alphanumeric responseValue code, got: {value}"
                )
        elif field_type in ["dte", "dttm"]:
            # Date/datetime fields should have string values or None
            self.assertTrue(
                isinstance(value, str) or value is None,
                f"Field {field_key} (type: {field_type}) should have string or None value, got {type(value).__name__}: {value}"
            )
            if isinstance(value, str) and value:
                # Date strings should be in ISO format
                if field_type == "dte":
                    self.assertRegex(
                        value, r'^\d{4}-\d{2}-\d{2}$',
                        f"Field {field_key} (type: {field_type}) should have ISO date format (YYYY-MM-DD), got: {value}"
                    )
                elif field_type == "dttm":
                    self.assertRegex(
                        value, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
                        f"Field {field_key} (type: {field_type}) should have ISO datetime format, got: {value}"
                    )
        elif field_type == "gbdy":
            # Table fields should have string values or None
            self.assertTrue(
                isinstance(value, str) or value is None,
                f"Field {field_key} (type: {field_type}) should have string or None value, got {type(value).__name__}: {value}"
            )
        else:
            # Unknown field type - just check it's not an unexpected type
            self.assertNotIsInstance(
                value, (list, dict),
                f"Field {field_key} (type: {field_type}) should not have complex types like list/dict, got {type(value).__name__}: {value}"
            )

    def _save_complete_model_response(self, assessment_id, assessment_name, model_response):
        """Save complete model response to file for inspection."""
        import os
        import json
        
        # Create directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(__file__), "_complete_model_responses")
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the model response
        filename = f"{assessment_id}_{assessment_name.replace(' ', '_')}_complete_model.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(model_response, f, indent=2, ensure_ascii=False)
        
        print(f"Saved complete model response for {assessment_name} to {filepath}")

    def test_generate_pcc_ui_formatted_outputs_all_assessments(self):
        """Generate complete model responses and save PCC-UI formatted outputs for all assessments."""
        pcc = PCCAssessmentSchema()
        
        assessments = [
            (21242733, "MHCS IDT 5 Day Section GG"),
            (21244981, "MHCS Nursing Admission Assessment - V 5"),
            (21242741, "MHCS Nursing Daily Skilled Note"),
            (21244831, "MHCS Nursing Weekly Skin Check")
        ]
        
        # Create output directory
        output_dir = os.path.join(os.path.dirname(__file__), "_pcc_ui_formatted_outputs")
        os.makedirs(output_dir, exist_ok=True)
        
        for assessment_id, assessment_name in assessments:
            with self.subTest(assessment=assessment_name):
                # Generate complete model response by following JSON schema structure
                model_response = self._generate_model_from_json_schema(pcc.get_json_schema(assessment_id))
                
                # Validate the model response
                is_valid, errors = pcc.validate(assessment_id, model_response)
                self.assertTrue(is_valid, 
                              f"Model validation failed for {assessment_name}: {errors}")
                
                # Use PCC wrapper's reverse_map with pcc-ui formatter defaults
                formatted_output = pcc.reverse_map(assessment_id, model_response)
                
                # Verify output structure
                self.assertIn("assessmentDescription", formatted_output)
                self.assertIn("templateId", formatted_output)
                self.assertIn("data", formatted_output)
                self.assertIsInstance(formatted_output["data"], list)
                self.assertGreater(len(formatted_output["data"]), 0)
                
                # Verify pcc-ui formatter behavior (fields array format)
                for section in formatted_output["data"]:
                    self.assertIn("sectionCode", section)
                    self.assertIn("fields", section)
                    self.assertIsInstance(section["fields"], list)
                    
                # Check that fields have the expected structure
                for field in section["fields"]:
                    self.assertIn("key", field)
                    self.assertIn("type", field)
                    self.assertIn("value", field)
                    # Verify type is original schema type (not target type)
                    self.assertIn(field["type"], ["txt", "num", "numde", "dte", "dttm", "chk", "diag", "hck", 
                                               "rad", "radh", "cmb", "mcs", "mcsh", "gbdy"])
                    
                    # Validate that values conform to field types
                    self._validate_field_value_type(field["type"], field["value"], field["key"])
                
                # Save formatted output to file
                filename = f"{assessment_id}_{assessment_name.replace(' ', '_')}_pcc_ui_formatted.json"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(formatted_output, f, indent=2, ensure_ascii=False)
                
                print(f"Saved PCC-UI formatted output for {assessment_name} to {filepath}")
                
                # Also save the model response for reference
                model_filename = f"{assessment_id}_{assessment_name.replace(' ', '_')}_model.json"
                model_filepath = os.path.join(output_dir, model_filename)
                
                with open(model_filepath, 'w', encoding='utf-8') as f:
                    json.dump(model_response, f, indent=2, ensure_ascii=False)
                
                print(f"Saved model response for {assessment_name} to {model_filepath}")


if __name__ == "__main__":
    # Set up logging to see info messages
    logging.basicConfig(level=logging.INFO)
    unittest.main()
