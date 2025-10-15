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
        self.assertEqual(instr_field["const"], "Instructions.Please answer the following questions based on observation")
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
        self.assertEqual(fruits_field["type"], "object")
        self.assertFalse(fruits_field["additionalProperties"])
        self.assertIn("Apple", fruits_field["properties"])
        self.assertEqual(fruits_field["properties"]["Apple"]["type"], ["string", "null"])

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
        self.assertEqual(result["data"]["A_1"], {"type": "radio", "value": "c"})  # Wheelchair -> "c"

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
        self.assertEqual(result["data"]["A_1"], {"type": "multi", "value": ["a", "c"]})  # Option A -> "a", Option C -> "c"

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
        self.assertEqual(result["data"]["A_1"], {"type": "checkbox", "value": 1})  # True -> 1
        
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
        self.assertEqual(result_false["data"]["A_1"], {"type": "checkbox", "value": None})  # False -> None

    def test_pcc_virtual_container_reverse(self):
        """Test PCC virtual container reverse formatter."""
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
        
        # Model response
        model_response = {
            "table_name": "Test Assessment",
            "sections": {
                "A.Admission": {
                    "assessmentQuestionGroups": {
                        "1.Basic Info": {
                            "questions": {
                                "Select location(s) of skin abnormality(ies). Document a description of each skin abnormality.": {
                                    "Head": "soft",
                                    "Leg": "smooth",
                                    "Hand": None,
                                    "Wrist": "blue"
                                }
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
        self.assertEqual(result["data"]["A_1"], {"type": "table", "value": expected_table})

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
        self.assertEqual(len(result), 2)  # Two sections
        
        # Find section A
        section_a = next(s for s in result if s.get("sectionCode") == "A")
        self.assertEqual(section_a["data"]["A_1"], {"type": "text", "value": "John Doe"})
        
        # Find section B
        section_b = next(s for s in result if s.get("sectionCode") == "B")
        self.assertEqual(section_b["data"]["B_1"], {"type": "text", "value": "120/80"})

    def test_formatter_access_to_original_schema_type(self):
        """Test that formatters can access original_schema_type from field metadata."""
        pcc = PCCAssessmentSchema()
        
        # Create a custom formatter that checks original_schema_type
        def test_formatter(engine, field_meta, model_value, table_name):
            original_type = field_meta.get("original_schema_type")
            return {field_meta["key"]: {"type": f"original_type_{original_type}", "value": model_value}}
        
        # Register the test formatter for txt and diag original types
        pcc.engine.register_reverse_formatter("txt", test_formatter)
        pcc.engine.register_reverse_formatter("diag", test_formatter)
        
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
        result = pcc.engine.reverse_map(assessment_name, model_response)
        
        # Verify original_schema_type is accessible for both fields
        self.assertEqual(result["data"]["A_1"], {"type": "original_type_txt", "value": "John Doe"})
        self.assertEqual(result["data"]["A_2"], {"type": "original_type_diag", "value": "Hypertension"})

    def test_formatter_precedence_original_over_target(self):
        """Test that original type formatters take precedence over target type formatters."""
        pcc = PCCAssessmentSchema()
        
        # Create a formatter that shows it's using target type fallback
        def target_type_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": f"target_type_fallback_{field_meta.get('target_type')}", "value": model_value}}
        
        # Create a formatter that shows it's using original type
        def original_type_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": f"original_type_{field_meta.get('original_schema_type')}", "value": model_value}}
        
        # Register target type formatter globally (this should be overridden by original type)
        from src.schema_engine import register_reverse_formatter
        register_reverse_formatter("single_select", target_type_formatter)
        
        # Register original type formatter (this should take precedence)
        pcc.engine.register_reverse_formatter("rad", original_type_formatter)
        
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
        result = pcc.engine.reverse_map(assessment_name, model_response)
        
        # Verify original type formatter takes precedence over target type formatter
        self.assertEqual(result["data"]["A_1"], {"type": "original_type_rad", "value": "Male"})


if __name__ == "__main__":
    # Set up logging to see info messages
    logging.basicConfig(level=logging.INFO)
    unittest.main()
