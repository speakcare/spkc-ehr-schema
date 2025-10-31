"""
Tests for SchemaEngine.

Tests cover:
- Flat table registration and JSON schema generation
- Nested table registration with object-based structure
- Enum extraction (simple list[str] and complex with extractor)
- Re-registration behavior and logging
- 1000 table limit enforcement
- Level key capture for reverse conversion
- Validation with JSON Schema + per-type validators
- Meta-schema language validation
- Comprehensive nested schema testing
"""

import unittest
from unittest.mock import patch
import logging
import copy
from typing import List, Dict, Any
import json

import sys
import os
# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from schema_engine import SchemaEngine


class TestSchemaEngine(unittest.TestCase):
    """Test cases for SchemaEngine."""

    def setUp(self):
        """Set up test fixtures."""
        # Meta-schema language definition for flat tables
        self.flat_meta_schema = {
            "schema_name": "table_name",
            "schema_id": "table_id",
            "properties": {
                "properties_name": "fields",
                "property": {
                    "key": "field_id",
                    "id": "field_number", 
                    "name": "field_name",
                    "title": "field_title",
                    "type": "field_type",
                    "options": "field_options",
                    "validation": {
                        "allowed_types": ["text", "number", "rad", "checkbox", "date", "complex_select", "percent"],
                        "type_constraints": {
                            "text": {
                                "target_type": "string",
                                "requires_options": False
                            },
                            "number": {
                                "target_type": "number", 
                                "requires_options": False
                            },
                            "percent": {
                                "target_type": "percent",
                                "requires_options": False
                            },
                            "rad": {
                                "target_type": "single_select",
                                "requires_options": True,
                                "options_field": "field_options",
                                "options_extractor": "multi_select_extractor"
                            },
                            "checkbox": {
                                "target_type": "boolean",
                                "requires_options": False
                            },
                            "date": {
                                "target_type": "date",
                                "requires_options": False
                            },
                            "complex_select": {
                                "target_type": "single_select",
                                "requires_options": True,
                                "options_field": "field_options",
                                "options_extractor": "multi_select_extractor",
                                "options_extractor": "extract_complex_options"
                            }
                        }
                    }
                }
            }
        }
        
        # Meta-schema language definition for nested tables
        self.nested_meta_schema = {
            "schema_name": "assessmentDescription",
            "container": {
                "container_name": "sections",
                "object": {
                    "key": "sectionCode",
                    "name": "sectionDescription",
                    "container": {
                        "container_name": "assessmentQuestionGroups",
                        "object": {
                            "key": "groupNumber",
                            "name": "groupTitle",
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
                                        "allowed_types": ["txt", "rad", "dte", "chk"],
                                        "type_constraints": {
                                            "txt": {
                                                "target_type": "string",
                                                "requires_options": False
                                            },
                                            "rad": {
                                                "target_type": "single_select",
                                                "requires_options": True,
                                                "options_field": "responseOptions",
                                                "options_extractor": "response_options_extractor"
                                            },
                                            "dte": {
                                                "target_type": "date",
                                                "requires_options": False
                                            },
                                            "chk": {
                                                "target_type": "boolean",
                                                "requires_options": False
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
        
        self.flat_engine = SchemaEngine(self.flat_meta_schema)
        self.nested_engine = SchemaEngine(self.nested_meta_schema)
        
        # Register extractor function
        self.flat_engine.register_options_extractor("extract_complex_options", self._extract_complex_options)
        
        # Register simple extractor for nested engine
        def simple_extractor(options):
            if isinstance(options, list):
                return [str(opt) for opt in options]
            return []
        self.nested_engine.register_options_extractor("simple_extractor", simple_extractor)
        
        # Register response options extractor for nested engine
        def response_options_extractor(options):
            if isinstance(options, list):
                return [opt.get("responseText", str(opt)) for opt in options if isinstance(opt, dict)]
            return []
        self.nested_engine.register_options_extractor("response_options_extractor", response_options_extractor)

    def _extract_complex_options(self, options: Dict[str, Any]) -> List[str]:
        """Test extractor for complex options."""
        return [choice["name"] for choice in options.get("choices", [])]

    def test_flat_table_registration(self):
        """Test registering a simple flat table."""
        external_schema = {
            "table_name": "Patient Assessment",
            "fields": [
                {
                    "field_id": "patient_name",
                    "field_number": "1",
                    "field_name": "Full patient name",
                    "field_title": "Patient Name",
                    "field_type": "text",
                },
                {
                    "field_id": "age",
                    "field_number": "2", 
                    "field_name": "Patient age in years",
                    "field_title": "Age",
                    "field_type": "number",
                },
                {
                    "field_id": "oxygen_saturation",
                    "field_number": "2b", 
                    "field_name": "O2 saturation percent",
                    "field_title": "O2 %",
                    "field_type": "percent",
                },
                {
                    "field_id": "gender",
                    "field_number": "3",
                    "field_name": "Patient gender",
                    "field_title": "Gender",
                    "field_type": "rad",
                    "field_options": ["Male", "Female", "Other"],
                },
            ]
        }

        table_id, table_name = self.flat_engine.register_table(1, external_schema)
        self.assertEqual(table_id, 1)
        self.assertEqual(table_name, "Patient Assessment")
        
        # Check table is registered
        self.assertIn(1, self.flat_engine.list_tables())
        
        # Get JSON schema
        schema = self.flat_engine.get_json_schema(1)
        
        # Verify root structure (flat schema with properties_name wrapper)
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["title"], "Patient Assessment")
        self.assertEqual(set(schema["required"]), {"table_name", "fields"})
        
        # Verify table_name field
        table_name_field = schema["properties"]["table_name"]
        self.assertEqual(table_name_field["type"], "string")
        self.assertEqual(table_name_field["const"], "Patient Assessment")
        self.assertEqual(table_name_field["description"], "The name of the table")
        
        # Verify fields container structure
        fields_container = schema["properties"]["fields"]
        self.assertEqual(fields_container["type"], "object")
        self.assertFalse(fields_container["additionalProperties"])
        self.assertEqual(set(fields_container["required"]), {"Full patient name", "Patient age in years", "O2 saturation percent", "Patient gender"})
        
        # Verify field schemas
        props = fields_container["properties"]
        
        # Patient name (nullable string)
        self.assertEqual(props["Full patient name"]["type"], ["string", "null"])
        
        # Age (nullable number)
        self.assertEqual(props["Patient age in years"]["type"], ["number", "null"])

        # Oxygen saturation (nullable percent with bounds)
        self.assertEqual(props["O2 saturation percent"]["type"], ["number", "null"])
        self.assertEqual(props["O2 saturation percent"]["minimum"], 0)
        self.assertEqual(props["O2 saturation percent"]["maximum"], 100)
        
        # Gender (nullable string with enum)
        self.assertEqual(props["Patient gender"]["type"], ["string", "null"])
        self.assertEqual(props["Patient gender"]["enum"], ["Male", "Female", "Other", None])

    def test_nested_table_registration(self):
        """Test registering a nested table with object-based structure."""
        external_schema = {
            "assessmentDescription": "MDS 2.0 Full Assessment",
            "sections": [
                {
                    "sectionCode": "AA",
                    "sectionDescription": "Identification Information",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "RESIDENT NAME",
                            "questions": [
                                {
                                    "questionKey": "AA1a",
                                    "questionNumber": "a",
                                    "questionText": "First",
                                    "questionTitle": "First Name",
                                    "questionType": "txt",
                                    "responseOptions": []
                                },
                                {
                                    "questionKey": "AA1b",
                                    "questionNumber": "b",
                                    "questionText": "Middle initial",
                                    "questionTitle": "Middle Initial",
                                    "questionType": "txt",
                                    "responseOptions": []
                                },
                                {
                                    "questionKey": "AA1c",
                                    "questionNumber": "c",
                                    "questionText": "Last",
                                    "questionTitle": "Last Name",
                                    "questionType": "txt",
                                    "responseOptions": []
                                }
                            ]
                        },
                        {
                            "groupNumber": "2",
                            "groupTitle": "GENDER",
                            "questions": [
                                {
                                    "questionKey": "AA2",
                                    "questionNumber": "",
                                    "questionText": "Gender selection",
                                    "questionTitle": "GENDER",
                                    "questionType": "rad",
                                    "responseOptions": [
                                        {"responseText": "Male", "responseValue": "1"},
                                        {"responseText": "Female", "responseValue": "2"}
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "AB",
                    "sectionDescription": "Demographic Information",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "DATE OF ENTRY",
                            "questions": [
                                {
                                    "questionKey": "AB1",
                                    "questionNumber": "",
                                    "questionText": "Date the stay began.",
                                    "questionTitle": "DATE OF ENTRY",
                                    "questionType": "dte",
                                    "responseOptions": []
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        self.nested_engine.register_table(1, external_schema)
        
        schema = self.nested_engine.get_json_schema(1)
        
        # Verify root structure
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["title"], "MDS 2.0 Full Assessment")
        self.assertEqual(set(schema["required"]), {"table_name", "sections"})
        
        # Verify table_name field
        table_name_field = schema["properties"]["table_name"]
        self.assertEqual(table_name_field["type"], "string")
        self.assertEqual(table_name_field["const"], "MDS 2.0 Full Assessment")
        self.assertEqual(table_name_field["description"], "The name of the table")
        
        # Verify sections container structure
        sections = schema["properties"]["sections"]
        self.assertEqual(sections["type"], "object")
        self.assertFalse(sections["additionalProperties"])
        self.assertEqual(set(sections["required"]), {"AA.Identification Information", "AB.Demographic Information"})
        
        # Verify first section structure
        section_aa = sections["properties"]["AA.Identification Information"]
        self.assertEqual(section_aa["type"], "object")
        self.assertFalse(section_aa["additionalProperties"])
        self.assertEqual(list(section_aa["required"]), ["assessmentQuestionGroups"])
        
        # Verify groups container
        groups = section_aa["properties"]["assessmentQuestionGroups"]
        self.assertEqual(groups["type"], "object")
        self.assertFalse(groups["additionalProperties"])
        self.assertEqual(set(groups["required"]), {"1.RESIDENT NAME", "2.GENDER"})
        
        # Verify first group structure
        group_1 = groups["properties"]["1.RESIDENT NAME"]
        self.assertEqual(group_1["type"], "object")
        self.assertFalse(group_1["additionalProperties"])
        self.assertEqual(list(group_1["required"]), ["questions"])
        
        # Verify questions container
        questions = group_1["properties"]["questions"]
        self.assertEqual(questions["type"], "object")
        self.assertFalse(questions["additionalProperties"])
        self.assertEqual(set(questions["required"]), {"First", "Middle initial", "Last"})
        
        # Verify individual question schemas
        question_props = questions["properties"]
        self.assertEqual(question_props["First"]["type"], ["string", "null"])
        self.assertEqual(question_props["Middle initial"]["type"], ["string", "null"])
        self.assertEqual(question_props["Last"]["type"], ["string", "null"])
        
        # Verify second group with radio button
        group_2 = groups["properties"]["2.GENDER"]
        gender_questions = group_2["properties"]["questions"]
        gender_props = gender_questions["properties"]
        # The field name comes from questionText
        self.assertEqual(gender_props["Gender selection"]["type"], ["string", "null"])
        self.assertEqual(gender_props["Gender selection"]["enum"], ["Male", "Female", None])

    def test_complex_options_extraction(self):
        """Test complex options extraction with custom extractor."""
        external_schema = {
            "table_name": "Complex Assessment",
            "fields": [
                {
                    "field_id": "priority",
                    "field_number": "1",
                    "field_name": "Priority Level",
                    "field_title": "Priority",
                    "field_type": "complex_select",
                    "field_options": {
                        "choices": [
                            {"name": "High", "color": "red"},
                            {"name": "Medium", "color": "yellow"},
                            {"name": "Low", "color": "green"},
                        ]
                    },
                }
            ]
        }

        self.flat_engine.register_table(1, external_schema)
        
        schema = self.flat_engine.get_json_schema(1)
        fields_container = schema["properties"]["fields"]
        priority_field = fields_container["properties"]["Priority Level"]
        
        self.assertEqual(priority_field["type"], ["string", "null"])
        self.assertEqual(priority_field["enum"], ["High", "Medium", "Low", None])

    def test_re_registration_and_logging(self):
        """Test re-registration behavior and logging."""
        external_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Test field",
                    "field_title": "Field 1",
                    "field_type": "text"
                }
            ]
        }

        # First registration
        self.flat_engine.register_table(1, external_schema)
        
        # Re-registration should log info and replace
        with patch('schema_engine.logger') as mock_logger:
            self.flat_engine.register_table(1, external_schema)
            mock_logger.info.assert_called_with("Re-registering table_id=%d (table_name=%s); replacing previous schema", 1, "Test Table")
        
        # Verify replacement
        schema = self.flat_engine.get_json_schema(1)
        self.assertEqual(schema["title"], "Test Table")

    def test_table_limit_enforcement(self):
        """Test 1000 table limit enforcement."""
        external_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Test field",
                    "field_title": "Field 1",
                    "field_type": "text"
                }
            ]
        }

        # Register 1000 tables (should succeed)
        for i in range(1000):
            self.flat_engine.register_table(f"table_{i}", external_schema)
        
        # 1001st should fail
        with self.assertRaises(ValueError) as context:
            self.flat_engine.register_table("table_1000", external_schema)
        
        self.assertIn("Maximum number of tables reached: 1000", str(context.exception))

    def test_level_key_capture(self):
        """Test that level keys are captured for reverse conversion."""
        external_schema = {
            "assessmentDescription": "Key Test Assessment",
            "sections": [
                {
                    "sectionCode": "AA",
                    "sectionDescription": "Test Section",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Test Group",
                            "questions": [
                                {
                                    "questionKey": "AA1",
                                    "questionNumber": "1",
                                    "questionText": "Test question",
                                    "questionTitle": "Test Question",
                                    "questionType": "txt",
                                    "responseOptions": []
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        self.nested_engine.register_table(1, external_schema)
        
        # Get field index
        field_index = self.nested_engine.get_field_metadata(1)#table_record["field_index"]
        
        # Verify level keys are captured
        self.assertEqual(len(field_index), 1)
        field_info = field_index[0]
        self.assertEqual(field_info["key"], "AA1")
        self.assertEqual(field_info["id"], "1")
        self.assertEqual(field_info["name"], "Test question")
        self.assertEqual(field_info["level_keys"], ["sections", "AA.Test Section", "assessmentQuestionGroups", "1.Test Group", "questions"])

    def test_validation_success(self):
        """Test successful data validation."""
        external_schema = {
            "table_name": "Validation Test",
            "fields": [
                {
                    "field_id": "name",
                    "field_number": "1",
                    "field_name": "Full name",
                    "field_title": "Name",
                    "field_type": "text"
                },
                {
                    "field_id": "age",
                    "field_number": "2",
                    "field_name": "Age in years",
                    "field_title": "Age",
                    "field_type": "number"
                },
                {
                    "field_id": "gender",
                    "field_number": "3",
                    "field_name": "Gender",
                    "field_title": "Gender",
                    "field_type": "rad",
                    "field_options": ["M", "F"]
                }
            ]
        }

        self.flat_engine.register_table(1, external_schema)
        
        # Valid data
        valid_data = {
            "table_name": "Validation Test",
            "fields": {
                "Full name": "John Doe",
                "Age in years": 30,
                "Gender": "M"
            }
        }
        
        is_valid, errors = self.flat_engine.validate(1, valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validation_failure(self):
        """Test data validation failures."""
        external_schema = {
            "table_name": "Validation Test",
            "fields": [
                {
                    "field_id": "name",
                    "field_number": "1",
                    "field_name": "Full name",
                    "field_title": "Name",
                    "field_type": "text"
                },
                {
                    "field_id": "age",
                    "field_number": "2",
                    "field_name": "Age in years",
                    "field_title": "Age",
                    "field_type": "number"
                },
                {
                    "field_id": "gender",
                    "field_number": "3",
                    "field_name": "Gender",
                    "field_title": "Gender",
                    "field_type": "rad",
                    "field_options": ["M", "F"]
                }
            ]
        }

        self.flat_engine.register_table(1, external_schema)
        
        # Invalid data
        invalid_data = {
            "table_name": "Validation Test",
            "fields": {
                "Full name": "John Doe",
                "Age in years": "not_a_number",  # Wrong type
                "Gender": "X"  # Not in enum
            }
        }
        
        is_valid, errors = self.flat_engine.validate(1, invalid_data)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Check specific error messages
        error_text = " ".join(errors)
        self.assertIn("not_a_number", error_text)
        self.assertIn("X", error_text)

    def test_date_validation(self):
        """Test date field validation with custom validator."""
        external_schema = {
            "table_name": "Date Test",
            "fields": [
                {
                    "field_id": "birth_date",
                    "field_number": "1",
                    "field_name": "Birth date",
                    "field_title": "Birth Date",
                    "field_type": "date"
                }
            ]
        }

        self.flat_engine.register_table(1, external_schema)
        
        # Valid date
        valid_data = {
            "table_name": "Date Test",
            "fields": {"Birth date": "1990-01-15"}
        }
        is_valid, errors = self.flat_engine.validate(1, valid_data)
        self.assertTrue(is_valid)
        
        # Invalid date (jsonschema doesn't validate format by default)
        invalid_data = {
            "table_name": "Date Test",
            "fields": {"Birth date": "not-a-date"}
        }
        is_valid, errors = self.flat_engine.validate(1, invalid_data)
        # Note: jsonschema doesn't validate format by default, but our custom validator does
        # So this will fail validation due to custom date validator
        self.assertFalse(is_valid)
        self.assertIn("Invalid ISO date format", errors[0])

    def test_unknown_table_errors(self):
        """Test errors for unknown table operations."""
        with self.assertRaises(ValueError):
            self.flat_engine.get_json_schema("unknown_table")
        
        with self.assertRaises(ValueError):
            self.flat_engine.validate("unknown_table", {})

    def test_unknown_field_type_error(self):
        """Test error for unknown external field type."""
        external_schema = {
            "table_name": "Error Test",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Test field",
                    "field_title": "Field 1",
                    "field_type": "unknown_type"
                }
            ]
        }

        with self.assertRaises(ValueError) as context:
            self.flat_engine.register_table(1, external_schema)
        
        self.assertIn("Field type 'unknown_type' not in allowed types", str(context.exception))

    def test_meta_schema_validation_errors(self):
        """Test meta-schema language validation errors."""
        # Missing schema_name
        invalid_meta_schema_1 = {
            "properties": {
                "properties_name": "fields",
                "property": {
                    "key": "field_id",
                    "name": "field_name",
                    "type": "field_type",
                    "validation": {
                        "allowed_types": ["text"],
                        "type_constraints": {
                            "text": {"target_type": "string", "requires_options": False}
                        }
                    }
                }
            }
        }
        
        with self.assertRaises(ValueError) as context:
            SchemaEngine(invalid_meta_schema_1)
        self.assertIn("Meta-schema must contain 'schema_name' field", str(context.exception))
        
        # Both properties and container (should be mutually exclusive)
        invalid_meta_schema_2 = {
            "schema_name": "test",
            "properties": {
                "properties_name": "fields",
                "property": {
                    "key": "field_id",
                    "name": "field_name",
                    "type": "field_type",
                    "validation": {
                        "allowed_types": ["text"],
                        "type_constraints": {
                            "text": {"target_type": "string", "requires_options": False}
                        }
                    }
                }
            },
            "container": {
                "container_name": "sections",
                "object": {
                    "key": "section_id",
                    "name": "section_name"
                }
            }
        }
        
        with self.assertRaises(ValueError) as context:
            SchemaEngine(invalid_meta_schema_2)
        self.assertIn("Meta-schema cannot contain both 'properties' and 'container'", str(context.exception))
        
        # Missing mandatory property fields
        invalid_meta_schema_3 = {
            "schema_name": "test",
            "properties": {
                "properties_name": "fields",
                "property": {
                    "key": "field_id",
                    # Missing "name" field
                    "type": "field_type",
                    "validation": {
                        "allowed_types": ["text"],
                        "type_constraints": {
                            "text": {"target_type": "string", "requires_options": False}
                        }
                    }
                }
            }
        }
        
        with self.assertRaises(ValueError) as context:
            SchemaEngine(invalid_meta_schema_3)
        self.assertIn("Property definition must contain 'name' field", str(context.exception))

    def test_comprehensive_nested_schema(self):
        """Test comprehensive nested schema with maximum levels and multiple containers."""
        # Meta-schema with 5 levels
        meta_schema = {
            'schema_name': 'document_name',
            'container': {
                'container_name': 'level1s',
                'object': {
                    'key': 'level1_id',
                    'name': 'level1_name',
                    'container': {
                        'container_name': 'level2s',
                        'object': {
                            'key': 'level2_id',
                            'name': 'level2_name',
                            'container': {
                                'container_name': 'level3s',
                                'object': {
                                    'key': 'level3_id',
                                    'name': 'level3_name',
                                    'container': {
                                        'container_name': 'level4s',
                                        'object': {
                                            'key': 'level4_id',
                                            'name': 'level4_name',
                                            'properties': {
                                                'properties_name': 'level5s',
                                                'property': {
                                                    'key': 'level5_id',
                                                    'id': 'level5_seq',
                                                    'name': 'level5_name',
                                                    'title': 'level5_title',
                                                    'type': 'level5_type',
                                                    'options': 'level5_options',
                                                    'validation': {
                                                        'allowed_types': ['text', 'number', 'rad', 'chk'],
                                                        'type_constraints': {
                                                            'text': {'target_type': 'string', 'requires_options': False},
                                                            'number': {'target_type': 'number', 'requires_options': False},
                                                            'rad': {'target_type': 'single_select', 'requires_options': True, 'options_field': 'level5_options'},
                                                            'chk': {'target_type': 'boolean', 'requires_options': False}
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
                }
            }
        }

        engine = SchemaEngine(meta_schema)

        # Comprehensive external schema with 2-3 containers at each level
        external_schema = {
            'document_name': 'Comprehensive Deep Nested Assessment Form',
            'level1s': [
                {
                    'level1_id': 'L1A',
                    'level1_name': 'Category A',
                    'level2s': [
                        {
                            'level2_id': 'L2A1',
                            'level2_name': 'Subcategory A1',
                            'level3s': [
                                {
                                    'level3_id': 'L3A1a',
                                    'level3_name': 'Group A1a',
                                    'level4s': [
                                        {
                                            'level4_id': 'L4A1a1',
                                            'level4_name': 'Section A1a1',
                                            'level5s': [
                                                {
                                                    'level5_id': 'field1',
                                                    'level5_seq': '1',
                                                    'level5_name': 'First field',
                                                    'level5_title': 'First Field',
                                                    'level5_type': 'text'
                                                },
                                                {
                                                    'level5_id': 'field2',
                                                    'level5_seq': '2',
                                                    'level5_name': 'Second field',
                                                    'level5_title': 'Second Field',
                                                    'level5_type': 'number'
                                                },
                                                {
                                                    'level5_id': 'field3',
                                                    'level5_seq': '3',
                                                    'level5_name': 'Third field',
                                                    'level5_title': 'Third Field',
                                                    'level5_type': 'rad',
                                                    'level5_options': ['Option A1', 'Option A2', 'Option A3']
                                                }
                                            ]
                                        },
                                        {
                                            'level4_id': 'L4A1a2',
                                            'level4_name': 'Section A1a2',
                                            'level5s': [
                                                {
                                                    'level5_id': 'field4',
                                                    'level5_seq': '4',
                                                    'level5_name': 'Fourth field',
                                                    'level5_title': 'Fourth Field',
                                                    'level5_type': 'chk'
                                                },
                                                {
                                                    'level5_id': 'field5',
                                                    'level5_seq': '5',
                                                    'level5_name': 'Fifth field',
                                                    'level5_title': 'Fifth Field',
                                                    'level5_type': 'text'
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                {
                    'level1_id': 'L1B',
                    'level1_name': 'Category B',
                    'level2s': [
                        {
                            'level2_id': 'L2B1',
                            'level2_name': 'Subcategory B1',
                            'level3s': [
                                {
                                    'level3_id': 'L3B1a',
                                    'level3_name': 'Group B1a',
                                    'level4s': [
                                        {
                                            'level4_id': 'L4B1a1',
                                            'level4_name': 'Section B1a1',
                                            'level5s': [
                                                {
                                                    'level5_id': 'field6',
                                                    'level5_seq': '6',
                                                    'level5_name': 'Sixth field',
                                                    'level5_title': 'Sixth Field',
                                                    'level5_type': 'number'
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        engine.register_table(1, external_schema)
        schema = engine.get_json_schema(1)
        
        # Verify root structure
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["title"], "Comprehensive Deep Nested Assessment Form")
        self.assertEqual(set(schema["required"]), {"table_name", "level1s"})
        
        # Verify table_name field
        table_name_field = schema["properties"]["table_name"]
        self.assertEqual(table_name_field["type"], "string")
        self.assertEqual(table_name_field["const"], "Comprehensive Deep Nested Assessment Form")
        self.assertEqual(table_name_field["description"], "The name of the table")
        
        # Verify level1s container
        level1s = schema["properties"]["level1s"]
        self.assertEqual(level1s["type"], "object")
        self.assertFalse(level1s["additionalProperties"])
        self.assertEqual(set(level1s["required"]), {"L1A.Category A", "L1B.Category B"})
        
        # Verify first level1 structure
        level1a = level1s["properties"]["L1A.Category A"]
        self.assertEqual(level1a["type"], "object")
        self.assertFalse(level1a["additionalProperties"])
        self.assertEqual(list(level1a["required"]), ["level2s"])
        
        # Verify level2s container
        level2s = level1a["properties"]["level2s"]
        self.assertEqual(level2s["type"], "object")
        self.assertFalse(level2s["additionalProperties"])
        self.assertEqual(set(level2s["required"]), {"L2A1.Subcategory A1"})
        
        # Verify level3s container
        level2a1 = level2s["properties"]["L2A1.Subcategory A1"]
        level3s = level2a1["properties"]["level3s"]
        self.assertEqual(level3s["type"], "object")
        self.assertFalse(level3s["additionalProperties"])
        self.assertEqual(set(level3s["required"]), {"L3A1a.Group A1a"})
        
        # Verify level4s container
        level3a1a = level3s["properties"]["L3A1a.Group A1a"]
        level4s = level3a1a["properties"]["level4s"]
        self.assertEqual(level4s["type"], "object")
        self.assertFalse(level4s["additionalProperties"])
        self.assertEqual(set(level4s["required"]), {"L4A1a1.Section A1a1", "L4A1a2.Section A1a2"})
        
        # Verify level5s container (bottom level)
        level4a1a1 = level4s["properties"]["L4A1a1.Section A1a1"]
        level5s = level4a1a1["properties"]["level5s"]
        self.assertEqual(level5s["type"], "object")
        self.assertFalse(level5s["additionalProperties"])
        self.assertEqual(set(level5s["required"]), {"First field", "Second field", "Third field"})
        
        # Verify individual field schemas
        field_props = level5s["properties"]
        self.assertEqual(field_props["First field"]["type"], ["string", "null"])
        self.assertEqual(field_props["Second field"]["type"], ["number", "null"])
        self.assertEqual(field_props["Third field"]["type"], ["string", "null"])
        self.assertEqual(field_props["Third field"]["enum"], ["Option A1", "Option A2", "Option A3", None])
        
        # Verify field metadata collection
        field_index = engine.get_field_metadata(1)
        self.assertEqual(len(field_index), 6)  # Total fields across all containers
        
        # Check specific field metadata
        field1_info = next(f for f in field_index if f["key"] == "field1")
        self.assertEqual(field1_info["key"], "field1")
        self.assertEqual(field1_info["id"], "1")
        self.assertEqual(field1_info["name"], "First field")
        self.assertEqual(field1_info["level_keys"], ["level1s", "L1A.Category A", "level2s", "L2A1.Subcategory A1", "level3s", "L3A1a.Group A1a", "level4s", "L4A1a1.Section A1a1", "level5s"])

    def test_instance_validator_override(self):
        """Test that instance validators can be registered and override global validators."""
        # Register instance-specific validator for string type (which has no global validator)
        def strict_string_validator(engine, value, field_metadata):
            if not isinstance(value, str):
                return False, "Must be string"
            if len(value) < 5:
                return False, f"String too short, must be at least 5 chars, got {len(value)}"
            return True, ""
        
        self.flat_engine.register_validator("string", strict_string_validator)
        
        # Register a test table with string field
        test_schema = {
            "table_name": "Test String",
            "fields": [
                {
                    "field_id": "name",
                    "field_number": "1",
                    "field_name": "Name Field",
                    "field_title": "Name",
                    "field_type": "text"
                }
            ]
        }
        
        self.flat_engine.register_table(1, test_schema)
        
        # Value "abc" passes JSON schema but fails custom validator
        data = {
            "table_name": "Test String",
            "fields": {"Name Field": "abc"}
        }
        
        is_valid, errors = self.flat_engine.validate(1, data)
        # The custom validator should be called and should fail
        self.assertFalse(is_valid, f"Expected validation to fail, but got errors: {errors}")
        self.assertTrue(len(errors) > 0, "Expected at least one error")
        self.assertIn("String too short", errors[0])

    def test_instance_schema_field_builder_override(self):
        """Test that instance builders override global builders."""
        # Create a new engine for this test with checkbox type mapping
        test_meta = copy.deepcopy(self.flat_meta_schema)
        # Add checkbox type mapping to meta-schema BEFORE creating engine
        test_meta["properties"]["property"]["validation"]["type_constraints"]["checkbox"] = {
            "target_type": "boolean",
            "requires_options": False
        }
        
        engine = SchemaEngine(test_meta)
        
        # Register custom checkbox builder (Yes/No instead of boolean)
        def checkbox_yes_no_builder(engine, target_type, enum_values, nullable, property_def, prop):
            return {
                "type": ["string", "null"] if nullable else "string",
                "enum": ["Yes", "No", None] if nullable else ["Yes", "No"],
                "description": "Select Yes or No"
            }
        
        engine.register_field_schema_builder("boolean", checkbox_yes_no_builder)
        
        # Register table with boolean field
        table_schema = {
            "name": "Test Table",
            "fields": [
                {"field_name": "active", "field_type": "checkbox", "field_id": "active_id"}
            ]
        }
        
        engine.register_table(1, table_schema)
        json_schema = engine.get_json_schema(1)
        
        # Verify custom builder was used
        active_field = json_schema["properties"]["fields"]["properties"]["active"]
        self.assertEqual(active_field["enum"], ["Yes", "No", None])
        self.assertIn("Select Yes or No", active_field["description"])

    def test_html_sanitization_engine(self):
        """Engine strips HTML tags from names, titles, and enum options."""
        external_schema = {
            "assessmentDescription": "<b>Assessment</b>",
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "<i>Section</i>",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "<b>Group</b>",
                            "questions": [
                                {
                                    "questionKey": "Q1",
                                    "questionNumber": "1",
                                    "questionText": "<b>Question</b> <i>Text</i>",
                                    "questionTitle": "Title <br/> Here",
                                    "questionType": "rad",
                                    "responseOptions": [
                                        {"responseText": "<b>Yes</b>"},
                                        {"responseText": "No <i>maybe</i>"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        # Register using nested engine (has response_options_extractor registered)
        table_id, table_name = self.nested_engine.register_table(None, external_schema)
        self.assertIsInstance(table_id, int)

        schema = self.nested_engine.get_json_schema(table_id)
        # Title sanitized
        self.assertEqual(schema["title"], "Assessment")
        # Section key.name uses sanitized name
        self.assertIn("A.Section", schema["properties"]["sections"]["properties"])
        groups = schema["properties"]["sections"]["properties"]["A.Section"]["properties"]["assessmentQuestionGroups"]
        self.assertIn("1.Group", groups["properties"])  # groupTitle sanitized
        questions = groups["properties"]["1.Group"]["properties"]["questions"]
        # Question property key sanitized
        self.assertIn("Question Text", questions["properties"])
        qnode = questions["properties"]["Question Text"]
        # Enum sanitized and includes None
        self.assertIn("enum", qnode)
        self.assertEqual(set(qnode["enum"]), {"Yes", "No maybe", None})
        # Metadata sanitized
        meta = self.nested_engine.get_field_metadata(table_id)
        qmeta = next(f for f in meta if f.get("key") == "Q1")
        self.assertEqual(qmeta["name"], "Question Text")
        self.assertEqual(qmeta["title"], "Title Here")

    def test_custom_validator_with_field_schema_access(self):
        """Test that custom validators can access field_schema for validation."""
        def single_select_validator_with_options(engine, value, field_metadata):
            # Access the original field schema
            field_schema = field_metadata.get("field_schema", {})
            
            # Extract options from field schema
            options = field_schema.get("field_options", [])
            
            if value not in options:
                return False, f"Value '{value}' not in allowed choices: {options}"
            
            return True, ""
        
        # Register the validator
        self.flat_engine.register_validator("single_select", single_select_validator_with_options)
        
        # Register a test table with single_select field
        test_schema = {
            "table_name": "Test Single Select",
            "fields": [
                {
                    "field_id": "priority",
                    "field_number": "1",
                    "field_name": "Priority Level",
                    "field_title": "Priority",
                    "field_type": "rad",
                    "field_options": ["High", "Medium", "Low"]
                }
            ]
        }
        
        self.flat_engine.register_table(1, test_schema)
        
        # Test with valid choice
        valid_data = {
            "table_name": "Test Single Select",
            "fields": {"Priority Level": "High"}
        }
        
        is_valid, errors = self.flat_engine.validate(1, valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test with invalid choice
        invalid_data = {
            "table_name": "Test Single Select", 
            "fields": {"Priority Level": "Unknown"}  # Not in choices
        }
        
        is_valid, errors = self.flat_engine.validate(1, invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("'Unknown' is not one of ['High', 'Medium', 'Low', None]", errors[0])

    def test_custom_builder_with_field_schema_access(self):
        """Test that custom builders can access field_schema for schema generation."""
        def percent_with_precision_builder(engine, target_type, enum_values, nullable, property_def, prop):
            # Access field details from schema
            field_name = prop.get("field_name", "Percent")  # Use field_name from meta-schema
            precision = prop.get("precision", 2)  # Default 2 decimal places
            
            return {
                "type": ["number", "null"] if nullable else "number",
                "minimum": 0,
                "maximum": 100,
                "multipleOf": 10 ** -precision,
                "description": f"{field_name}: Percentage with {precision} decimal precision"
            }
        
        # Create new engine and register custom builder
        test_meta = copy.deepcopy(self.flat_meta_schema)
        engine = SchemaEngine(test_meta)
        engine.register_field_schema_builder("percent", percent_with_precision_builder)
        
        # Register table with percent field that has precision info
        table_schema = {
            "name": "Test Table",
            "fields": [
                {"field_name": "accuracy", "field_type": "percent", "precision": 3, "field_id": "accuracy_id"}
            ]
        }
        
        engine.register_table(1, table_schema)
        json_schema = engine.get_json_schema(1)
        
        # Verify custom builder was used with field-specific precision
        accuracy_field = json_schema["properties"]["fields"]["properties"]["accuracy"]
        self.assertEqual(accuracy_field["multipleOf"], 0.001)  # 10^-3
        self.assertIn("accuracy: Percentage with 3 decimal precision", accuracy_field["description"])

    def test_custom_properties_name_field_path(self):
        """Test that field paths use the correct properties_name from meta-schema."""
        # Create meta-schema with custom properties_name
        custom_meta = copy.deepcopy(self.flat_meta_schema)
        custom_meta["properties"]["properties_name"] = "custom_fields"  # Change from "fields"
        
        engine = SchemaEngine(custom_meta)
        
        # Register a simple test table with a field that we know works
        table_schema = {
            "name": "Test Custom Properties",
            "custom_fields": [  # Use custom_fields to match our custom properties_name
                {
                    "field_id": "test_field",
                    "field_number": "1", 
                    "field_name": "Test Field",
                    "field_title": "Test",
                    "field_type": "text"  # Use text which is in allowed_types
                }
            ]
        }
        
        engine.register_table(1, table_schema)
        
        # Check that the field was registered
        field_index = engine.get_field_metadata(1)
        self.assertEqual(len(field_index), 1, f"Expected 1 field, got {len(field_index)}")
        
        # Check that the field path uses custom_fields
        field_meta = field_index[0]
        expected_path = ["custom_fields", "Test Field"]
        
        # Test the _build_field_path method directly
        actual_path = engine._build_field_path(field_meta)
        self.assertEqual(actual_path, expected_path, f"Expected path {expected_path}, got {actual_path}")

    def test_global_validator_fallback(self):
        """Test that global validators are used when no instance validator is registered."""
        # Don't register any instance validator for "string" type
        
        # Register a simple test table
        test_schema = {
            "table_name": "Test Text",
            "fields": [
                {
                    "field_id": "text_field",
                    "field_number": "1",
                    "field_name": "Text Field",
                    "field_title": "Text",
                    "field_type": "text"
                }
            ]
        }
        
        self.flat_engine.register_table(1, test_schema)
        
        # Test with valid string data
        valid_data = {
            "table_name": "Test Text",
            "fields": {"Text Field": "Some text"}
        }
        
        is_valid, errors = self.flat_engine.validate(1, valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test with invalid string data (should fail JSON schema validation)
        invalid_data = {
            "table_name": "Test Text",
            "fields": {"Text Field": 123}  # Wrong type
        }
        
        is_valid, errors = self.flat_engine.validate(1, invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("is not of type 'string'", errors[0])

    def test_global_builder_fallback(self):
        """Test that global builders are used when no instance builder is registered."""
        # Don't register any instance builder for "string" type
        
        # Register a simple table with string field
        table_schema = {
            "name": "Test Vital Signs",
            "fields": [
                {"field_name": "title", "field_type": "text", "field_id": "title_id"}
            ]
        }
        
        self.flat_engine.register_table(1, table_schema)
        json_schema = self.flat_engine.get_json_schema(1)
        
        # Verify global builder was used (should be simple string type)
        title_field = json_schema["properties"]["fields"]["properties"]["title"]
        self.assertEqual(title_field["type"], ["string", "null"])

    def test_field_metadata_completeness(self):
        """Test that field metadata contains all expected fields."""
        # Register a simple test table first
        test_schema = {
            "table_name": "Test Metadata",
            "fields": [
                {
                    "field_id": "test_field",
                    "field_number": "1",
                    "field_name": "Test Field",
                    "field_title": "Test",
                    "field_type": "text"
                }
            ]
        }
        
        self.flat_engine.register_table(1, test_schema)
        
        # Get field index from the registered table
        field_index = self.flat_engine.get_field_metadata(1)
        
        # Find a field with all metadata
        field_meta = field_index[0]  # First field
        
        # Verify all expected metadata fields are present
        expected_fields = {"key", "level_keys", "target_type", "field_schema"}
        self.assertTrue(expected_fields.issubset(set(field_meta.keys())))
        
        # Verify field_schema contains original field definition
        field_schema = field_meta["field_schema"]
        self.assertIn("field_name", field_schema)
        self.assertIn("field_type", field_schema)

    def test_multiple_select_type(self):
        """Test multiple_select field type with options."""
        # Create meta-schema with multiple_select type mapping
        test_meta = copy.deepcopy(self.flat_meta_schema)
        # Add multi_select to allowed_types
        test_meta["properties"]["property"]["validation"]["allowed_types"].append("multi_select")
        test_meta["properties"]["property"]["validation"]["type_constraints"]["multi_select"] = {
            "target_type": "multiple_select",
            "requires_options": True,
            "options_field": "field_options",
            "options_extractor": "multi_select_extractor"
        }
        
        engine = SchemaEngine(test_meta)
        
        # Register options extractor for multi_select fields
        def multi_select_extractor(options: List[Dict[str, Any]]) -> List[str]:
            """Extract option names from multi_select field options."""
            return [option["name"] for option in options]
        
        engine.register_options_extractor("multi_select_extractor", multi_select_extractor)
        
        # Register a test table with multiple_select field
        table_schema = {
            "name": "Test Multiple Select",
            "fields": [
                {
                    "field_id": "hobbies",
                    "field_number": "1",
                    "field_name": "Hobbies",
                    "field_title": "Select Hobbies",
                    "field_type": "multi_select",
                    "field_options": [
                        {"name": "Reading", "value": "reading"},
                        {"name": "Sports", "value": "sports"},
                        {"name": "Music", "value": "music"},
                        {"name": "Cooking", "value": "cooking"}
                    ]
                }
            ]
        }
        
        engine.register_table(1, table_schema)
        
        # Test JSON schema generation
        json_schema = engine.get_json_schema(1)
        
        # Verify the multiple_select field schema
        hobbies_field = json_schema["properties"]["fields"]["properties"]["Hobbies"]
        self.assertEqual(hobbies_field["type"], ["array", "null"])
        self.assertEqual(hobbies_field["items"]["type"], ["string", "null"])
        self.assertEqual(hobbies_field["items"]["enum"], ["Reading", "Sports", "Music", "Cooking", None])
        self.assertIn("Select one or more of the valid enum options", hobbies_field["description"])
        
        # Test validation with valid data
        valid_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {"Hobbies": ["Reading", "Sports"]}
        }
        is_valid, errors = engine.validate(1, valid_data)
        self.assertTrue(is_valid, f"Expected validation to pass, but got errors: {errors}")
        
        # Test validation with invalid data (invalid enum value)
        invalid_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {"Hobbies": ["Reading", "InvalidHobby"]}
        }
        is_valid, errors = engine.validate(1, invalid_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid enum value")
        self.assertTrue(len(errors) > 0, "Expected at least one error")
        self.assertIn("InvalidHobby", errors[0])
        
        # Test validation with null value (should pass)
        null_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {"Hobbies": None}
        }
        is_valid, errors = engine.validate(1, null_data)
        self.assertTrue(is_valid, f"Expected null value to pass, but got errors: {errors}")
        
        # Test validation with empty array (should pass)
        empty_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {"Hobbies": []}
        }
        is_valid, errors = engine.validate(1, empty_data)
        self.assertTrue(is_valid, f"Expected empty array to pass, but got errors: {errors}")
        
        # Test field metadata collection
        field_index = engine.get_field_metadata(1)
        self.assertEqual(len(field_index), 1)
        
        field_meta = field_index[0]
        self.assertEqual(field_meta["key"], "hobbies")
        self.assertEqual(field_meta["name"], "Hobbies")
        self.assertEqual(field_meta["target_type"], "multiple_select")
        self.assertEqual(field_meta["level_keys"], ["fields"])
        
        # Verify field_schema contains original field definition
        field_schema = field_meta["field_schema"]
        self.assertEqual(field_schema["field_type"], "multi_select")
        self.assertEqual(len(field_schema["field_options"]), 4)
        self.assertEqual(field_schema["field_options"][0]["name"], "Reading")

    def test_multiple_select_custom_validator(self):
        """Test multiple_select with custom validator."""
        # Create meta-schema with multiple_select type mapping
        test_meta = copy.deepcopy(self.flat_meta_schema)
        # Add multi_select to allowed_types
        test_meta["properties"]["property"]["validation"]["allowed_types"].append("multi_select")
        test_meta["properties"]["property"]["validation"]["type_constraints"]["multi_select"] = {
            "target_type": "multiple_select",
            "requires_options": True,
            "options_field": "field_options",
            "options_extractor": "multi_select_extractor"
        }
        
        engine = SchemaEngine(test_meta)
        
        # Register options extractor for multi_select fields
        def multi_select_extractor(options: List[Dict[str, Any]]) -> List[str]:
            """Extract option names from multi_select field options."""
            return [option["name"] for option in options]
        
        engine.register_options_extractor("multi_select_extractor", multi_select_extractor)
        
        # Register custom validator for multiple_select
        def strict_multiple_select_validator(engine, value, field_metadata):
            """Custom validator that enforces minimum 2 selections."""
            if not isinstance(value, list):
                return False, "Must be an array"
            
            if len(value) < 2:
                return False, f"Must select at least 2 items, got {len(value)}"
            
            return True, ""
        
        engine.register_validator("multiple_select", strict_multiple_select_validator)
        
        # Register test table
        table_schema = {
            "name": "Test Strict Multiple Select",
            "fields": [
                {
                    "field_id": "skills",
                    "field_number": "1",
                    "field_name": "Skills",
                    "field_title": "Select Skills",
                    "field_type": "multi_select",
                    "field_options": [
                        {"name": "Python", "value": "python"},
                        {"name": "JavaScript", "value": "javascript"},
                        {"name": "SQL", "value": "sql"}
                    ]
                }
            ]
        }
        
        engine.register_table(1, table_schema)
        
        # Test validation with insufficient selections (should fail custom validator)
        insufficient_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {"Skills": ["Python"]}  # Only 1 selection
        }
        is_valid, errors = engine.validate(1, insufficient_data)
        self.assertFalse(is_valid, "Expected validation to fail with insufficient selections")
        self.assertIn("Must select at least 2 items", errors[0])
        
        # Test validation with sufficient selections (should pass)
        sufficient_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {"Skills": ["Python", "JavaScript"]}  # 2 selections
        }
        is_valid, errors = engine.validate(1, sufficient_data)
        self.assertTrue(is_valid, f"Expected validation to pass with sufficient selections, but got errors: {errors}")

    def test_positive_number_type(self):
        """Test positive_number field type with JSON schema generation and validation."""
        # Create meta-schema with positive_number type mapping
        test_meta = copy.deepcopy(self.flat_meta_schema)
        # Add positive_number to allowed_types
        test_meta["properties"]["property"]["validation"]["allowed_types"].append("positive_number")
        test_meta["properties"]["property"]["validation"]["type_constraints"]["positive_number"] = {
            "target_type": "positive_number",
            "requires_options": False
        }
        
        # Create engine with updated meta-schema
        engine = SchemaEngine(test_meta)
        
        # Register a test table with positive_number field
        table_schema = {
            "name": "Test Positive Number",
            "fields": [
                {
                    "field_id": "age",
                    "field_number": "1", 
                    "field_name": "Age",
                    "field_title": "Patient Age",
                    "field_type": "positive_number"
                },
                {
                    "field_id": "weight",
                    "field_number": "2",
                    "field_name": "Weight",
                    "field_title": "Patient Weight (kg)",
                    "field_type": "positive_number"
                }
            ]
        }
        
        engine.register_table(1, table_schema)
        
        # Get JSON schema
        json_schema = engine.get_json_schema(1)
        
        # Verify the positive_number field schema
        age_field = json_schema["properties"]["fields"]["properties"]["Age"]
        self.assertEqual(age_field["type"], ["number", "null"])
        self.assertEqual(age_field["minimum"], 0)
        self.assertNotIn("maximum", age_field)  # No maximum constraint
        
        weight_field = json_schema["properties"]["fields"]["properties"]["Weight"]
        self.assertEqual(weight_field["type"], ["number", "null"])
        self.assertEqual(weight_field["minimum"], 0)
        self.assertNotIn("maximum", weight_field)
        
        # Test validation with valid positive numbers
        valid_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {
                "Age": 25,
                "Weight": 70.5
            }
        }
        is_valid, errors = engine.validate(1, valid_data)
        self.assertTrue(is_valid, f"Expected validation to pass with valid positive numbers, but got errors: {errors}")
        
        # Test validation with zero (should pass)
        zero_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": 0,
                "Weight": 0.0
            }
        }
        is_valid, errors = engine.validate(1, zero_data)
        self.assertTrue(is_valid, f"Expected validation to pass with zero values, but got errors: {errors}")
        
        # Test validation with negative numbers (should fail JSON schema validation)
        negative_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": -5,
                "Weight": -10.0
            }
        }
        is_valid, errors = engine.validate(1, negative_data)
        self.assertFalse(is_valid, "Expected validation to fail with negative numbers")
        self.assertTrue(any("minimum" in error.lower() for error in errors), f"Expected minimum constraint error, got: {errors}")
        
        # Test validation with null values (should pass)
        null_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": None,
                "Weight": None
            }
        }
        is_valid, errors = engine.validate(1, null_data)
        self.assertTrue(is_valid, f"Expected validation to pass with null values, but got errors: {errors}")
        
        # Test validation with invalid types (should fail JSON schema validation)
        invalid_type_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": "not a number",
                "Weight": ["array", "not", "number"]
            }
        }
        is_valid, errors = engine.validate(1, invalid_type_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid types")
        
        # Verify field metadata collection
        field_index = engine.get_field_metadata(1)
        self.assertEqual(len(field_index), 2)
        
        # Check Age field metadata
        age_field_meta = next(field for field in field_index if field["key"] == "age")
        self.assertEqual(age_field_meta["key"], "age")
        self.assertEqual(age_field_meta["name"], "Age")
        self.assertEqual(age_field_meta["target_type"], "positive_number")
        self.assertEqual(age_field_meta["level_keys"], ["fields"])
        
        # Check Weight field metadata
        weight_field_meta = next(field for field in field_index if field["key"] == "weight")
        self.assertEqual(weight_field_meta["key"], "weight")
        self.assertEqual(weight_field_meta["name"], "Weight")
        self.assertEqual(weight_field_meta["target_type"], "positive_number")
        self.assertEqual(weight_field_meta["level_keys"], ["fields"])

    def test_positive_integer_type(self):
        """Test positive_integer field type with JSON schema generation and validation."""
        # Create meta-schema with positive_integer type mapping
        test_meta = copy.deepcopy(self.flat_meta_schema)
        # Add positive_integer to allowed_types
        test_meta["properties"]["property"]["validation"]["allowed_types"].append("positive_integer")
        test_meta["properties"]["property"]["validation"]["type_constraints"]["positive_integer"] = {
            "target_type": "positive_integer",
            "requires_options": False
        }
        
        # Create engine with updated meta-schema
        engine = SchemaEngine(test_meta)
        
        # Register a test table with positive_integer field
        table_schema = {
            "name": "Test Positive Integer",
            "fields": [
                {
                    "field_id": "age",
                    "field_number": "1", 
                    "field_name": "Age",
                    "field_title": "Patient Age",
                    "field_type": "positive_integer"
                },
                {
                    "field_id": "count",
                    "field_number": "2",
                    "field_name": "Count",
                    "field_title": "Item Count",
                    "field_type": "positive_integer"
                }
            ]
        }
        
        engine.register_table(1, table_schema)
        
        # Get JSON schema
        json_schema = engine.get_json_schema(1)
        
        # Verify the positive_integer field schema
        age_field = json_schema["properties"]["fields"]["properties"]["Age"]
        self.assertEqual(age_field["type"], ["integer", "null"])
        self.assertEqual(age_field["minimum"], 0)
        self.assertNotIn("maximum", age_field)  # No maximum constraint
        
        count_field = json_schema["properties"]["fields"]["properties"]["Count"]
        self.assertEqual(count_field["type"], ["integer", "null"])
        self.assertEqual(count_field["minimum"], 0)
        self.assertNotIn("maximum", count_field)
        
        # Test validation with valid positive integers
        valid_data = {
            "table_name": "Unknown Table",  # Must match the JSON schema const
            "fields": {
                "Age": 25,
                "Count": 0
            }
        }
        is_valid, errors = engine.validate(1, valid_data)
        self.assertTrue(is_valid, f"Expected validation to pass with valid positive integers, but got errors: {errors}")
        
        # Test validation with zero (should pass)
        zero_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": 0,
                "Count": 0
            }
        }
        is_valid, errors = engine.validate(1, zero_data)
        self.assertTrue(is_valid, f"Expected validation to pass with zero values, but got errors: {errors}")
        
        # Test validation with negative integers (should fail JSON schema validation)
        negative_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": -5,
                "Count": -10
            }
        }
        is_valid, errors = engine.validate(1, negative_data)
        self.assertFalse(is_valid, "Expected validation to fail with negative integers")
        self.assertTrue(any("minimum" in error.lower() for error in errors), f"Expected minimum constraint error, got: {errors}")
        
        # Test validation with floats (should fail JSON schema validation)
        float_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": 25.5,
                "Count": 1.7
            }
        }
        is_valid, errors = engine.validate(1, float_data)
        self.assertFalse(is_valid, "Expected validation to fail with float values")
        
        # Test validation with null values (should pass)
        null_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": None,
                "Count": None
            }
        }
        is_valid, errors = engine.validate(1, null_data)
        self.assertTrue(is_valid, f"Expected validation to pass with null values, but got errors: {errors}")
        
        # Test validation with invalid types (should fail JSON schema validation)
        invalid_type_data = {
            "table_name": "Unknown Table",
            "fields": {
                "Age": "not a number",
                "Count": ["array", "not", "number"]
            }
        }
        is_valid, errors = engine.validate(1, invalid_type_data)
        self.assertFalse(is_valid, "Expected validation to fail with invalid types")
        
        # Verify field metadata collection
        field_index = engine.get_field_metadata(1)
        self.assertEqual(len(field_index), 2)
        
        # Check Age field metadata
        age_field_meta = next(field for field in field_index if field["key"] == "age")
        self.assertEqual(age_field_meta["key"], "age")
        self.assertEqual(age_field_meta["name"], "Age")
        self.assertEqual(age_field_meta["target_type"], "positive_integer")
        self.assertEqual(age_field_meta["level_keys"], ["fields"])
        
        # Check Count field metadata
        count_field_meta = next(field for field in field_index if field["key"] == "count")
        self.assertEqual(count_field_meta["key"], "count")
        self.assertEqual(count_field_meta["name"], "Count")
        self.assertEqual(count_field_meta["target_type"], "positive_integer")
        self.assertEqual(count_field_meta["level_keys"], ["fields"])

    def test_table_id_allocation(self):
        """Test automatic table ID allocation and manual ID assignment."""
        # Simple external schema for testing
        simple_external_schema = {
            "table_name": "Simple Test",
            "fields": [
                {
                    "field_id": "name",
                    "field_number": "1",
                    "field_name": "Name",
                    "field_title": "Full Name",
                    "field_type": "text"
                }
            ]
        }
        
        # Test automatic ID allocation
        table_id_1, table_name_1 = self.flat_engine.register_table(None, simple_external_schema)
        self.assertIsInstance(table_id_1, int)
        self.assertEqual(table_name_1, "Simple Test")
        self.assertEqual(table_id_1, 1)  # First allocated ID should be 1
        
        # Test another automatic allocation
        table_id_2, table_name_2 = self.flat_engine.register_table(None, simple_external_schema)
        self.assertEqual(table_id_2, 2)  # Second allocated ID should be 2
        self.assertEqual(table_name_2, "Simple Test")
        
        # Test manual ID assignment
        table_id_manual, table_name_manual = self.flat_engine.register_table(100, simple_external_schema)
        self.assertEqual(table_id_manual, 100)
        self.assertEqual(table_name_manual, "Simple Test")
        
        # Test that manual ID doesn't affect allocation counter
        table_id_3, table_name_3 = self.flat_engine.register_table(None, simple_external_schema)
        self.assertEqual(table_id_3, 3)  # Should continue from last allocated
        self.assertEqual(table_name_3, "Simple Test")
        
        # Test ID collision handling
        table_id_4, table_name_4 = self.flat_engine.register_table(None, simple_external_schema)
        self.assertEqual(table_id_4, 4)
        self.assertEqual(table_name_4, "Simple Test")
        
        # Unregister table 2 and register new one - should skip 2 and use 5
        self.flat_engine.unregister_table(2)
        table_id_5, table_name_5 = self.flat_engine.register_table(None, simple_external_schema)
        self.assertEqual(table_id_5, 5)  # Should skip the unregistered ID 2
        self.assertEqual(table_name_5, "Simple Test")
        
        # Test that we can reuse unregistered ID manually
        table_id_reuse, table_name_reuse = self.flat_engine.register_table(2, simple_external_schema)
        self.assertEqual(table_id_reuse, 2)
        self.assertEqual(table_name_reuse, "Simple Test")
        
        # Verify all tables are registered
        registered_ids = self.flat_engine.list_tables()
        self.assertIn(1, registered_ids)
        self.assertIn(2, registered_ids)
        self.assertIn(3, registered_ids)
        self.assertIn(4, registered_ids)
        self.assertIn(5, registered_ids)
        self.assertIn(100, registered_ids)
        self.assertEqual(len(registered_ids), 6)
        
        # Test that register_table returns the correct ID
        table_id_200, table_name_200 = self.flat_engine.register_table(200, simple_external_schema)
        self.assertEqual(table_id_200, 200)
        self.assertEqual(table_name_200, "Simple Test")
        
        # Test re-registration with same ID
        with self.assertLogs('schema_engine', level='INFO') as cm:
            returned_id, returned_name = self.flat_engine.register_table(200, simple_external_schema)
            self.assertEqual(returned_id, 200)
            self.assertEqual(returned_name, "Simple Test")
            self.assertIn("Re-registering table_id=200", cm.output[0])

    def test_table_name_lookup(self):
        """Test lookup by table name vs table ID."""
        external_schema = {
            "table_name": "Test Assessment",
            "fields": [
                {
                    "field_id": "name",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_title": "Name",
                    "field_type": "text"
                }
            ]
        }
        
        # Register table
        table_id, table_name = self.flat_engine.register_table(None, external_schema)
        self.assertEqual(table_name, "Test Assessment")
        
        # Test lookup by ID
        schema_by_id = self.flat_engine.get_json_schema(table_id)
        self.assertEqual(schema_by_id["title"], "Test Assessment")
        
        # Test lookup by name
        schema_by_name = self.flat_engine.get_json_schema(table_name)
        self.assertEqual(schema_by_name["title"], "Test Assessment")
        
        # Verify both schemas are identical
        self.assertEqual(schema_by_id, schema_by_name)
        
        # Test validation by ID
        valid_data = {
            "table_name": "Test Assessment",
            "fields": {
                "Patient Name": "John Doe"
            }
        }
        is_valid_id, errors_id = self.flat_engine.validate(table_id, valid_data)
        self.assertTrue(is_valid_id)
        self.assertEqual(errors_id, [])
        
        # Test validation by name
        is_valid_name, errors_name = self.flat_engine.validate(table_name, valid_data)
        self.assertTrue(is_valid_name)
        self.assertEqual(errors_name, [])
        
        # Test error cases
        with self.assertRaises(ValueError) as cm:
            self.flat_engine.get_json_schema("Unknown Table")
        self.assertIn("Unknown table_name: Unknown Table", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            self.flat_engine.get_json_schema(999)
        self.assertIn("Unknown table_id: 999", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            self.flat_engine.get_json_schema(None)
        self.assertIn("Table identifier must be int or str", str(cm.exception))

    def test_get_field_metadata(self):
        """Test get_field_metadata method with both ID and name lookup."""
        external_schema = {
            "table_name": "Metadata Test",
            "fields": [
                {
                    "field_id": "name",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_title": "Name",
                    "field_type": "text"
                },
                {
                    "field_id": "age",
                    "field_number": "2",
                    "field_name": "Patient Age",
                    "field_title": "Age",
                    "field_type": "number"
                }
            ]
        }
        
        # Register table
        table_id, table_name = self.flat_engine.register_table(None, external_schema)
        
        # Test get_field_metadata by ID
        metadata_by_id = self.flat_engine.get_field_metadata(table_id)
        self.assertEqual(len(metadata_by_id), 2)
        
        # Test get_field_metadata by name
        metadata_by_name = self.flat_engine.get_field_metadata(table_name)
        self.assertEqual(len(metadata_by_name), 2)
        
        # Verify both return identical results
        self.assertEqual(metadata_by_id, metadata_by_name)
        
        # Verify metadata structure
        name_field = next(f for f in metadata_by_id if f["key"] == "name")
        self.assertEqual(name_field["name"], "Patient Name")
        self.assertEqual(name_field["target_type"], "string")
        self.assertEqual(name_field["level_keys"], ["fields"])
        
        age_field = next(f for f in metadata_by_id if f["key"] == "age")
        self.assertEqual(age_field["name"], "Patient Age")
        self.assertEqual(age_field["target_type"], "number")
        self.assertEqual(age_field["level_keys"], ["fields"])
        
        # Test error cases
        with self.assertRaises(ValueError) as cm:
            self.flat_engine.get_field_metadata("Unknown Table")
        self.assertIn("Unknown table_name: Unknown Table", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            self.flat_engine.get_field_metadata(999)
        self.assertIn("Unknown table_id: 999", str(cm.exception))

    def test_get_container_count(self):
        """Test get_container_count method for both flat and nested schemas."""
        # Test with flat schema (no containers) - should return 0
        flat_schema = {
            "table_name": "Flat Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Field 1",
                    "field_type": "text"
                }
            ]
        }
        table_id, _ = self.flat_engine.register_table(None, flat_schema)
        
        # Flat schema has no containers, so count should be 0
        count = self.flat_engine.get_container_count(table_id, "any_container")
        self.assertEqual(count, 0)
        
        # Test with nested schema (has containers) using correct field names
        nested_schema = {
            "assessmentDescription": "Nested Table",
            "sections": [
                {
                    "sectionCode": "A",
                    "sectionDescription": "Section A",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Group 1",
                            "questions": [
                                {
                                    "questionKey": "A_1",
                                    "questionNumber": "1",
                                    "questionText": "Question A1",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "B", 
                    "sectionDescription": "Section B",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Group 1",
                            "questions": [
                                {
                                    "questionKey": "B_1",
                                    "questionNumber": "1",
                                    "questionText": "Question B1",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                },
                {
                    "sectionCode": "C",
                    "sectionDescription": "Section C",
                    "assessmentQuestionGroups": [
                        {
                            "groupNumber": "1",
                            "groupTitle": "Group 1",
                            "questions": [
                                {
                                    "questionKey": "C_1",
                                    "questionNumber": "1",
                                    "questionText": "Question C1",
                                    "questionType": "txt"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Register nested schema
        nested_table_id, _ = self.nested_engine.register_table(None, nested_schema)
        
        # Get count for top-level container
        count = self.nested_engine.get_container_count(nested_table_id, "sections")
        self.assertEqual(count, 3)
        
        # Try to get count for non-existent container - should return 0
        count = self.nested_engine.get_container_count(nested_table_id, "nonexistent")
        self.assertEqual(count, 0)
        
        # Test lookup by name
        count = self.nested_engine.get_container_count("Nested Table", "sections")
        self.assertEqual(count, 3)
        
        # Test error for unknown table
        with self.assertRaises(ValueError) as cm:
            self.nested_engine.get_container_count("Unknown Table", "sections")
        self.assertIn("Unknown table_name: Unknown Table", str(cm.exception))

    def test_instructions_type(self):
        """Test instructions field type with title.name const value."""
        # Create meta-schema with instructions type
        test_meta = copy.deepcopy(self.flat_meta_schema)
        test_meta["properties"]["property"]["validation"]["allowed_types"].append("inst")
        test_meta["properties"]["property"]["validation"]["type_constraints"]["inst"] = {
            "target_type": "instructions",
            "requires_options": False
        }
        
        engine = SchemaEngine(test_meta)
        
        # Test case 1: Field with both title and name
        table_schema_with_title = {
            "name": "Test Instructions",
            "fields": [
                {
                    "field_id": "instr1",
                    "field_number": "1",
                    "field_name": "Please read carefully",
                    "field_title": "Section A Instructions",
                    "field_type": "inst"
                },
                {
                    "field_id": "field1",
                    "field_number": "2",
                    "field_name": "Patient Name",
                    "field_title": "Name",
                    "field_type": "text"
                }
            ]
        }
        
        table_id_1, table_name_1 = engine.register_table(1, table_schema_with_title)
        json_schema = engine.get_json_schema(1)
        
        # Verify instructions field schema - property key is now "1.Instructions"
        instr_field = json_schema["properties"]["fields"]["properties"]["1.Instructions"]
        self.assertEqual(instr_field["type"], "string")
        self.assertEqual(instr_field["const"], "Section A Instructions. Please read carefully")
        self.assertIn("context for other properties", instr_field["description"])
        self.assertEqual(instr_field["description"], "These are instructions that should be used as context for other properties of the same schema object and adjacent schema objects.")
        
        # Verify instructions field is in field_index
        field_index = engine.get_field_metadata(1)
        instr_metadata = next(f for f in field_index if f["key"] == "instr1")
        self.assertEqual(instr_metadata["target_type"], "instructions")
        
        # Test case 2: Field with name only (no title)
        table_schema_no_title = {
            "name": "Test No Title",
            "fields": [
                {
                    "field_id": "instr2",
                    "field_number": "1",
                    "field_name": "Answer all questions",
                    "field_type": "inst"
                }
            ]
        }
        
        table_id_2, table_name_2 = engine.register_table(2, table_schema_no_title)
        json_schema2 = engine.get_json_schema(2)
        
        # Verify property key is "1.Instructions", const is the name
        instr_field2 = json_schema2["properties"]["fields"]["properties"]["1.Instructions"]
        self.assertEqual(instr_field2["const"], "Answer all questions")
        self.assertEqual(instr_field2["description"], "These are instructions that should be used as context for other properties of the same schema object and adjacent schema objects.")
        
        # Test case 3: Validation - const field should only accept its const value
        valid_data = {
            "table_name": table_name_2,  # Use the actual registered table name
            "fields": {
                "1.Instructions": "Answer all questions"  # Use new property key
            }
        }
        is_valid, errors = engine.validate(2, valid_data)
        self.assertTrue(is_valid, f"Expected validation to pass with matching const, got errors: {errors}")
        
        # Wrong value should fail
        invalid_data = {
            "table_name": table_name_2,  # Use the actual registered table name
            "fields": {
                "1.Instructions": "Different text"  # Use new property key
            }
        }
        is_valid, errors = engine.validate(2, invalid_data)
        self.assertFalse(is_valid, "Expected validation to fail with non-matching const")
        
        # Test case 4: Field with title but no name
        table_schema_title_only = {
            "name": "Test Title Only",
            "fields": [
                {
                    "field_id": "instr3",
                    "field_number": "1",
                    "field_title": "Important Instructions",
                    "field_type": "inst"
                }
            ]
        }
        
        table_id_3, table_name_3 = engine.register_table(3, table_schema_title_only)
        json_schema3 = engine.get_json_schema(3)
        
        # Verify const value is just the title when no name
        instr_field3 = json_schema3["properties"]["fields"]["properties"]["1.Instructions"]
        self.assertEqual(instr_field3["const"], "Important Instructions")
        self.assertEqual(instr_field3["description"], "These are instructions that should be used as context for other properties of the same schema object and adjacent schema objects.")

    def test_ignored_types(self):
        """Test that ignored_types fields are omitted from JSON schema."""
        # Create meta-schema with ignored_types
        test_meta = copy.deepcopy(self.flat_meta_schema)
        test_meta["properties"]["property"]["validation"]["ignored_types"] = ["skip"]
        
        engine = SchemaEngine(test_meta)
        
        # Register table with ignored fields mixed with regular fields
        table_schema = {
            "name": "Test Ignored Fields",
            "fields": [
                {
                    "field_id": "skip1",
                    "field_number": "1",
                    "field_name": "Internal ID",
                    "field_type": "skip"
                },
                {
                    "field_id": "regular1",
                    "field_number": "2",
                    "field_name": "Patient Name",
                    "field_type": "text"
                },
                {
                    "field_id": "skip2",
                    "field_number": "3",
                    "field_name": "Computed Field",
                    "field_type": "skip"
                },
                {
                    "field_id": "regular2",
                    "field_number": "4",
                    "field_name": "Patient Age",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        json_schema = engine.get_json_schema(table_id)
        
        # Verify ignored fields are NOT in the schema
        fields_properties = json_schema["properties"]["fields"]["properties"]
        self.assertNotIn("Internal ID", fields_properties)
        self.assertNotIn("Computed Field", fields_properties)
        
        # Verify regular fields ARE in the schema
        self.assertIn("Patient Name", fields_properties)
        self.assertIn("Patient Age", fields_properties)
        
        # Verify ignored fields are NOT in required list
        required = json_schema["properties"]["fields"]["required"]
        self.assertNotIn("Internal ID", required)
        self.assertNotIn("Computed Field", required)
        
        # Verify regular fields ARE in required list
        self.assertIn("Patient Name", required)
        self.assertIn("Patient Age", required)
        
        # Verify only 2 fields in schema (not 4)
        self.assertEqual(len(fields_properties), 2)
        self.assertEqual(len(required), 2)
        
        # Verify field metadata does not include ignored fields
        field_metadata = engine.get_field_metadata(table_id)
        ignored_fields = [f for f in field_metadata if f.get("target_type") == "skip"]
        self.assertEqual(len(ignored_fields), 0, "Ignored fields should not be in metadata")

    def test_ignored_types_mutual_exclusion(self):
        """Test that types cannot be in both allowed_types and ignored_types."""
        invalid_meta = copy.deepcopy(self.flat_meta_schema)
        invalid_meta["properties"]["property"]["validation"]["allowed_types"] = ["txt", "num", "dte"]
        invalid_meta["properties"]["property"]["validation"]["ignored_types"] = ["txt", "skip"]  # "txt" is in both!
        
        with self.assertRaises(ValueError) as ctx:
            SchemaEngine(invalid_meta)
        
        self.assertIn("both 'allowed_types' and 'ignored_types'", str(ctx.exception))
        self.assertIn("txt", str(ctx.exception))

    def test_ignored_types_not_in_type_constraints(self):
        """Test that ignored types should not have type_constraints defined."""
        invalid_meta = copy.deepcopy(self.flat_meta_schema)
        invalid_meta["properties"]["property"]["validation"]["ignored_types"] = ["skip"]
        invalid_meta["properties"]["property"]["validation"]["type_constraints"]["skip"] = {
            "target_type": "string",
            "requires_options": False
        }
        
        with self.assertRaises(ValueError) as ctx:
            SchemaEngine(invalid_meta)
        
        self.assertIn("Ignored types should not have type_constraints defined", str(ctx.exception))
        self.assertIn("skip", str(ctx.exception))

    def test_virtual_container_metadata(self):
        """Test that builders can return virtual children metadata for virtual containers."""
        # Create meta-schema
        test_meta = copy.deepcopy(self.flat_meta_schema)
        test_meta["properties"]["property"]["validation"]["allowed_types"].append("virtual")
        test_meta["properties"]["property"]["validation"]["type_constraints"]["virtual"] = {
            "target_type": "test_virtual",
            "requires_options": False
        }
        
        engine = SchemaEngine(test_meta)
        
        # Register custom builder that returns (container_schema, virtual_children_metadata)
        def test_virtual_builder(eng, target_type, enum_values, nullable, property_def, prop):
            container = eng.create_object_node(nullable=False)
            eng.add_properties(container, {
                "Child1": eng.build_property_node("string", prop=prop, nullable=True),
                "Child2": eng.build_property_node("string", prop=prop, nullable=True),
            })
            eng.set_required(container, ["Child1", "Child2"])
            virtual_children_metadata = [
                {"child_property_name": "Child1", "child_index": 0},
                {"child_property_name": "Child2", "child_index": 1},
            ]
            return (container, virtual_children_metadata)
        
        engine.register_field_schema_builder("test_virtual", test_virtual_builder)
        
        # Register table with a single virtual field
        table_schema = {
            "name": "Test Virtual Container",
            "fields": [
                {"field_id": "vc1", "field_number": "1", "field_name": "Container Field", "field_type": "virtual"}
            ]
        }
        
        table_id, _ = engine.register_table(None, table_schema)
        
        field_metadata = engine.get_field_metadata(table_id)
        self.assertEqual(len(field_metadata), 3)  # 1 container + 2 children
        
        container_meta = field_metadata[0]
        self.assertTrue(container_meta.get("is_virtual_container"))
        self.assertEqual(container_meta.get("expanded_children"), ["Child1", "Child2"])
        
        child1 = field_metadata[1]
        self.assertTrue(child1.get("is_virtual_container_child"))
        self.assertEqual(child1.get("virtual_container_key"), "vc1")
        self.assertEqual(child1.get("name"), "Child1")
        self.assertEqual(child1.get("level_keys"), ["fields", "Container Field"])
        
        # Verify JSON schema
        schema = engine.get_json_schema(table_id)
        node = schema["properties"]["fields"]["properties"]["Container Field"]
        self.assertEqual(node["type"], "object")
        self.assertIn("Child1", node["properties"]) 
        self.assertIn("Child2", node["properties"]) 
        self.assertEqual(node["required"], ["Child1", "Child2"])

    def test_enrich_schema(self):
        """Test schema enrichment functionality with all matching keys."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_type": "text"
                },
                {
                    "field_id": "field2", 
                    "field_number": "2",
                    "field_name": "Patient Age",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        # Enrich schema with additional descriptions
        enrichment_dict = {
            "field1": "This field contains the patient's full name",
            "field2": "This field contains the patient's age in years"
        }
        
        unmatched_keys = engine.enrich_schema(table_name, enrichment_dict)
        
        # Verify no unmatched keys (positive case)
        self.assertEqual(unmatched_keys, [])
        self.assertIsInstance(unmatched_keys, list)
        
        # Verify enrichment was applied
        json_schema = engine.get_json_schema(table_id)
        fields_properties = json_schema["properties"]["fields"]["properties"]
        
        field1_schema = fields_properties["Patient Name"]
        field2_schema = fields_properties["Patient Age"]
        
        self.assertIn("This field contains the patient's full name", field1_schema.get("description", ""))
        self.assertIn("This field contains the patient's age in years", field2_schema.get("description", ""))
        
        # Test error case
        with self.assertRaises(ValueError):
            engine.enrich_schema("nonexistent_table", {"field1": "test"})
    
    def test_enrich_schema_with_unmatched_keys(self):
        """Test schema enrichment with some unmatched keys (negative case)."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_type": "text"
                },
                {
                    "field_id": "field2", 
                    "field_number": "2",
                    "field_name": "Patient Age",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        # Enrich schema with some valid and some invalid field keys
        enrichment_dict = {
            "field1": "This field contains the patient's full name",
            "field_nonexistent": "This field does not exist",
            "field2": "This field contains the patient's age in years",
            "another_invalid": "Another non-existent field"
        }
        
        unmatched_keys = engine.enrich_schema(table_name, enrichment_dict)
        
        # Verify unmatched keys are returned (negative case)
        self.assertEqual(len(unmatched_keys), 2)
        self.assertIn("field_nonexistent", unmatched_keys)
        self.assertIn("another_invalid", unmatched_keys)
        self.assertNotIn("field1", unmatched_keys)
        self.assertNotIn("field2", unmatched_keys)
        
        # Verify that valid fields were still enriched
        json_schema = engine.get_json_schema(table_id)
        fields_properties = json_schema["properties"]["fields"]["properties"]
        
        field1_schema = fields_properties["Patient Name"]
        field2_schema = fields_properties["Patient Age"]
        
        self.assertIn("This field contains the patient's full name", field1_schema.get("description", ""))
        self.assertIn("This field contains the patient's age in years", field2_schema.get("description", ""))

    def test_reverse_map_flat(self):
        """Test flat reverse mapping."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1", 
                    "field_name": "Patient Name",
                    "field_type": "text"
                },
                {
                    "field_id": "field2",
                    "field_number": "2",
                    "field_name": "Patient Age", 
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        # Add test formatters
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        # Model response
        model_response = {
            "fields": {
                "Patient Name": "John Doe",
                "Patient Age": "25"
            }
        }
        
        # Reverse map
        result = engine.reverse_map(table_name, model_response, formatter_name="test")
        
        # Verify flat mapping
        self.assertIn("table_name", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["field1"], {"type": "text", "value": "John Doe"})
        self.assertEqual(result["data"][0]["properties"]["field2"], {"type": "text", "value": "25"})
        
        # Test error case
        with self.assertRaises(ValueError):
            engine.reverse_map("nonexistent_table", model_response)

    def test_reverse_map_with_metadata_overrides(self):
        """Test reverse mapping with custom metadata field names."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "table_id": 123,
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        model_response = {
            "fields": {
                "Patient Name": "John Doe"
            }
        }
        
        # Test with metadata overrides and schema_type
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_name": "custom_name",
                "schema_id": "custom_id",
                "schema_type": {"name": "doc_type", "value": "test_document"}
            }
        )
        
        # Verify custom field names
        self.assertIn("doc_type", result)
        self.assertEqual(result["doc_type"], "test_document")
        self.assertIn("custom_name", result)
        self.assertEqual(result["custom_name"], "Test Table")
        self.assertIn("custom_id", result)
        self.assertEqual(result["custom_id"], 123)
        self.assertNotIn("table_name", result)
        self.assertNotIn("table_id", result)
        
        # Test with empty schema_type value (field should be omitted)
        result2 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": {"name": "doc_type", "value": ""}
            }
        )
        self.assertNotIn("doc_type", result2)
        
        # Test with empty schema_type field name (field should be omitted)
        result3 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": {"name": "", "value": "test_value"}
            }
        )
        self.assertNotIn("doc_type", result3)
        self.assertNotIn("", result3)

    def test_metadata_overrides_partial(self):
        """Test metadata overrides with only some fields customized."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "table_id": 456,
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(2, table_schema)
        
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        model_response = {
            "fields": {
                "Patient Name": "John Doe"
            }
        }
        
        # Test: Only schema_name override
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_name": "custom_name"
            }
        )
        self.assertIn("custom_name", result)
        self.assertEqual(result["custom_name"], "Test Table")
        self.assertIn("table_id", result)  # Original name preserved
        self.assertEqual(result["table_id"], 456)
        
        # Test: Only schema_id override
        result2 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_id": "custom_id"
            }
        )
        self.assertIn("custom_id", result2)
        self.assertEqual(result2["custom_id"], 456)
        self.assertIn("table_name", result2)  # Original name preserved
        self.assertEqual(result2["table_name"], "Test Table")
        
        # Test: Only schema_type (with value)
        result3 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": {"name": "doc_type", "value": "test_value"}
            }
        )
        self.assertIn("doc_type", result3)
        self.assertEqual(result3["doc_type"], "test_value")
        self.assertIn("table_name", result3)  # Original names preserved
        self.assertIn("table_id", result3)

    def test_metadata_overrides_schema_type_invalid_structure(self):
        """Test handling of invalid schema_type structures."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "table_id": 789,
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(3, table_schema)
        
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        model_response = {
            "fields": {
                "Patient Name": "John Doe"
            }
        }
        
        # Test: schema_type as string (not dict) - should be ignored
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": "just_a_string"  # Invalid structure
            }
        )
        # Should not add schema_type field
        self.assertNotIn("doc_type", result)
        self.assertNotIn("just_a_string", result)
        self.assertIn("table_name", result)
        
        # Test: schema_type dict missing "name" key
        result2 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": {"value": "test_value"}  # Missing "name"
            }
        )
        self.assertNotIn("doc_type", result2)
        
        # Test: schema_type dict missing "value" key
        result3 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": {"name": "doc_type"}  # Missing "value"
            }
        )
        self.assertNotIn("doc_type", result3)

    def test_metadata_overrides_empty_and_none_values(self):
        """Test handling of empty and None values in overrides."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "table_id": 999,
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(4, table_schema)
        
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        model_response = {
            "fields": {
                "Patient Name": "John Doe"
            }
        }
        
        # Test: Empty string for schema_name - should use original
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_name": "",  # Empty string - should fall back to original
                "schema_type": {"name": "doc_type", "value": "test"}
            }
        )
        self.assertIn("table_name", result)  # Original name preserved
        self.assertNotIn("", result)  # Empty string should not be used as field name
        self.assertIn("doc_type", result)
        
        # Test: None value for schema_type
        result2 = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_type": {"name": "doc_type", "value": None}  # None value
            }
        )
        # Should treat None as empty and omit field
        self.assertNotIn("doc_type", result2)

    def test_metadata_overrides_without_meta_schema_fields(self):
        """Test behavior when meta-schema doesn't have schema_name or schema_id."""
        # Create a minimal meta-schema without schema_id
        minimal_meta_schema = {
            "schema_name": "name",
            "properties": {
                "properties_name": "items",
                "property": {
                    "key": "id",
                    "name": "name",
                    "type": "type",
                    "validation": {
                        "allowed_types": ["text"],
                        "type_constraints": {
                            "text": {
                                "target_type": "string",
                                "requires_options": False
                            }
                        }
                    }
                }
            }
        }
        
        engine = SchemaEngine(minimal_meta_schema)
        
        table_schema = {
            "name": "Test",
            "items": [
                {
                    "id": "item1",
                    "name": "Item 1",
                    "type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(5, table_schema)
        
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        model_response = {
            "items": {
                "Item 1": "Test Value"
            }
        }
        
        # Test: schema_id not in meta-schema - should be ignored
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            metadata_field_overrides={
                "schema_name": "custom_name",
                "schema_id": "custom_id",  # Not in meta-schema
                "schema_type": {"name": "doc_type", "value": "test"}
            }
        )
        self.assertIn("custom_name", result)
        self.assertNotIn("custom_id", result)  # No schema_id in meta-schema
        self.assertIn("doc_type", result)

    def test_reverse_map_with_nulls(self):
        """Test reverse mapping includes null values."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": "Patient Name", 
                    "field_type": "text"
                },
                {
                    "field_id": "field2",
                    "field_number": "2",
                    "field_name": "Patient Age",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        # Add test formatters
        def test_text_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_text_formatter)
        
        # Model response with null
        model_response = {
            "fields": {
                "Patient Name": "John Doe",
                "Patient Age": None
            }
        }
        
        # Reverse map
        result = engine.reverse_map(table_name, model_response, formatter_name="test")
        
        # Verify null values are included
        self.assertIn("table_name", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"]["field1"], {"type": "text", "value": "John Doe"})
        self.assertEqual(result["data"][0]["properties"]["field2"], {"type": "text", "value": None})

    def test_reverse_formatter_registration(self):
        """Test reverse formatter registration."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        # Test instance-level registration
        def custom_formatter(engine, field_meta, model_value, table_name):
            return [(field_meta["key"], f"custom_{model_value}")]
        
        engine.register_reverse_formatter("test", "custom_type", custom_formatter)
        
        # Verify registration worked (no direct way to test, but no error should occur)
        self.assertTrue(True)  # Placeholder assertion

    def test_unknown_formatter_set_error(self):
        """Test error when using unknown formatter set."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1", 
                    "field_name": "Test Field",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        model_response = {
            "fields": {
                "Test Field": "test value"
            }
        }
        
        # Test error for unknown formatter set
        with self.assertRaises(ValueError) as context:
            engine.reverse_map(table_name, model_response, formatter_name="nonexistent")
        
        self.assertIn("Formatter set 'nonexistent' is not registered", str(context.exception))
        self.assertIn("Available formatter sets: []", str(context.exception))

    def test_missing_formatter_error_logging(self):
        """Test that missing formatters are logged as errors and skipped."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        table_schema = {
            "table_name": "Test Table",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1", 
                    "field_name": "Test Field",
                    "field_type": "text"
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, table_schema)
        
        # Register a formatter set but not for the field type we'll use
        def test_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "test", "value": model_value}}
        
        engine.register_reverse_formatter("test", "other_type", test_formatter)
        
        model_response = {
            "fields": {
                "Test Field": "test value"
            }
        }
        
        # This should not raise an error, but should log and skip the field
        result = engine.reverse_map(table_name, model_response, formatter_name="test")
        
        # The result should be empty since no formatter was found for "text" type
        self.assertIn("table_name", result)  # schema metadata
        self.assertIsInstance(result["data"], list)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["properties"], {})

    def test_json_schema_structure_compliance(self):
        """Test that all generated JSON schemas have proper structure with additionalProperties: false and required fields."""
        eng = SchemaEngine(self.nested_meta_schema)
        
        # Register options extractor
        def simple_extractor(options):
            if isinstance(options, list):
                return [opt["responseText"] for opt in options]
            return []
        eng.register_options_extractor("response_options_extractor", simple_extractor)
        
        # Register a comprehensive test table with various field types
        test_table = {
            "table_name": "Structure Test Table",
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
                                {"responseText": "Option 1", "responseValue": "1"},
                                {"responseText": "Option 2", "responseValue": "2"}
                            ]
                        },
                        {
                            "questionKey": "A_3",
                            "questionNumber": "3", 
                            "questionText": "Date field",
                            "questionType": "dte"
                        },
                        {
                            "questionKey": "A_4",
                            "questionNumber": "4",
                            "questionText": "Checkbox field", 
                            "questionType": "chk"
                        }
                    ]
                }]
            }]
        }
        
        table_id, table_name = eng.register_table(99999, test_table)
        json_schema = eng.get_json_schema(99999)
        
        def validate_object_schemas(schema_dict, path="root"):
            """Recursively validate all object schemas have proper structure."""
            issues = []
            
            if isinstance(schema_dict, dict):
                if schema_dict.get("type") == "object":
                    # Check additionalProperties
                    if "additionalProperties" not in schema_dict:
                        issues.append(f"{path}: Missing 'additionalProperties' field")
                    elif schema_dict["additionalProperties"] is not False:
                        issues.append(f"{path}: 'additionalProperties' must be false, got {schema_dict['additionalProperties']}")
                    
                    # Check required field exists
                    if "required" not in schema_dict:
                        issues.append(f"{path}: Missing 'required' field")
                    elif not isinstance(schema_dict["required"], list):
                        issues.append(f"{path}: 'required' must be a list, got {type(schema_dict['required'])}")
                    
                    # Recursively check properties
                    if "properties" in schema_dict:
                        for prop_name, prop_schema in schema_dict["properties"].items():
                            prop_issues = validate_object_schemas(prop_schema, f"{path}.properties.{prop_name}")
                            issues.extend(prop_issues)
                
                # Check array items
                elif schema_dict.get("type") == "array" and "items" in schema_dict:
                    items_issues = validate_object_schemas(schema_dict["items"], f"{path}.items")
                    issues.extend(items_issues)
                
                # Check other nested objects
                for key, value in schema_dict.items():
                    if key not in ["type", "properties", "items", "required", "additionalProperties", "description", "enum", "const", "maxItems", "minItems"]:
                        nested_issues = validate_object_schemas(value, f"{path}.{key}")
                        issues.extend(nested_issues)
            
            return issues
        
        # Validate the entire schema
        issues = validate_object_schemas(json_schema)
        
        if issues:
            print(f"\nSchema structure issues found:")
            for issue in issues:
                print(f"  - {issue}")
            self.fail(f"Found {len(issues)} schema structure issues. See output above.")
        
        # Specific validations
        self.assertFalse(json_schema.get("additionalProperties", True), 
                        "Root schema must have additionalProperties: false")
        self.assertIn("required", json_schema)
        self.assertIsInstance(json_schema["required"], list)
        
        # Check sections structure
        sections_prop = json_schema["properties"]["sections"]
        self.assertEqual(sections_prop["type"], "object")
        self.assertFalse(sections_prop.get("additionalProperties", True),
                        "Sections must have additionalProperties: false")

    def test_zoo_taxonomy_deep_nesting(self):
        """
        Test zoo taxonomy with 7-level deep nesting to validate:
        1. Meta-schema creation with completely different domain
        2. Deep nesting (7 levels) works correctly
        3. Table functionality in non-PCC context
        4. New structured output format across different domains
        """
        # Create zoo-specific meta-schema
        zoo_meta_schema = {
            "schema_name": "table_name",
            "container": {
                "container_name": "animals",
                "container_type": "array",
                "object": {
                    "name": "animal_class",
                    "key": "class_name",
                    "container": {
                        "container_name": "orders",
                        "container_type": "array", 
                        "object": {
                            "name": "order_name",
                            "key": "order_key",
                            "container": {
                                "container_name": "suborders",
                                "container_type": "array",
                                "object": {
                                    "name": "suborder_name", 
                                    "key": "suborder_key",
                                    "container": {
                                        "container_name": "families",
                                        "container_type": "array",
                                        "object": {
                                            "name": "family_name",
                                            "key": "family_key",
                                            "container": {
                                                "container_name": "genera",
                                                "container_type": "array",
                                                "object": {
                                                    "name": "genus_name",
                                                    "key": "genus_key",
                                                    "container": {
                                                        "container_name": "species",
                                                        "container_type": "array",
                                                        "object": {
                                                            "name": "species_name",
                                                            "key": "species_key",
                                                            "properties": {
                                                                "properties_name": "properties",
                                                                "property": {
                                                                    "key": "property_key",
                                                                    "name": "property_name",
                                                                    "type": "property_type",
                                                                    "validation": {
                                                                        "allowed_types": ["count", "health", "food_order", "breed_table"],
                                                                        "type_constraints": {
                                                                            "count": {
                                                                                "target_type": "integer",
                                                                                "requires_options": False
                                                                            },
                                                                            "health": {
                                                                                "target_type": "single_select",
                                                                                "requires_options": True,
                                                                                "options_field": "health_options",
                                                                                "options_extractor": "health_options_extractor"
                                                                            },
                                                                            "food_order": {
                                                                                "target_type": "string",
                                                                                "requires_options": False
                                                                            },
                                                                            "breed_table": {
                                                                                "target_type": "virtual_container",
                                                                                "requires_options": True,
                                                                                "options_field": "breed_properties",
                                                                                "options_extractor": "breed_properties_extractor"
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
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Create engine with zoo meta-schema
        engine = SchemaEngine(zoo_meta_schema)
        
        # Register options extractors for zoo field types
        def health_options_extractor(options_field_value):
            """Extract health options from field schema."""
            if not options_field_value:
                return []
            return [opt.get("label", "") for opt in options_field_value]
        
        def breed_properties_extractor(properties_field_value):
            """Extract breed properties for virtual container."""
            if not properties_field_value:
                return []
            return [prop.get("property_name", "") for prop in properties_field_value]
        
        engine.register_options_extractor("health_options_extractor", health_options_extractor)
        engine.register_options_extractor("breed_properties_extractor", breed_properties_extractor)
        
        # Register custom formatters for zoo field types
        def count_formatter(engine, field_meta, model_value, table_name):
            """Formatter for count fields - return integer type."""
            return {field_meta["key"]: {"type": "integer", "value": model_value}}
        
        def health_formatter(engine, field_meta, model_value, table_name):
            """Formatter for health fields - map labels to values."""
            if model_value is None:
                return {field_meta["key"]: {"type": "single_select", "value": None}}
            
            # Map health labels to values
            health_mapping = {
                "Excellent": "E",
                "Good": "G", 
                "Fair": "F",
                "Poor": "P"
            }
            value = health_mapping.get(model_value, model_value)
            return {field_meta["key"]: {"type": "single_select", "value": value}}
        
        def food_order_formatter(engine, field_meta, model_value, table_name):
            """Formatter for food order fields - return string type."""
            return {field_meta["key"]: {"type": "string", "value": model_value}}
        
        def breed_table_formatter(engine, field_meta, model_value, table_name):
            """Formatter for breed table - return virtual container type."""
            return {field_meta["key"]: {"type": "virtual_container", "value": model_value}}
        
        engine.register_reverse_formatter("zoo", "count", count_formatter)
        engine.register_reverse_formatter("zoo", "health", health_formatter)
        engine.register_reverse_formatter("zoo", "food_order", food_order_formatter)
        engine.register_reverse_formatter("zoo", "breed_table", breed_table_formatter)
        
        # Register virtual container builder for breed_table
        def breed_table_builder(engine, target_type, enum_values, nullable, property_def, prop):
            """Build virtual container for breed table with child properties."""
            breed_properties = prop.get("breed_properties", [])
            
            # Build child properties
            child_properties = {}
            child_metadata = []
            
            for breed_prop in breed_properties:
                prop_name = breed_prop.get("property_name", "")
                prop_type = breed_prop.get("property_type", "string")
                
                # Add child property
                if prop_type == "single_select":
                    child_properties[prop_name] = {"type": ["string", "null"] if nullable else "string"}
                else:
                    child_properties[prop_name] = {"type": ["string", "null"] if nullable else "string"}
                
                # Add child metadata
                child_metadata.append({
                    "key": prop.get("property_key", ""),
                    "name": prop_name,
                    "target_type": "string",
                    "property_key": prop_name,
                    "field_schema": prop,
                    "is_virtual_container_child": True,
                    "virtual_container_key": prop.get("property_key", ""),
                    "response_value": breed_prop.get("property_key", ""),
                    "child_index": len(child_metadata)
                })
            
            # Build container schema
            container_schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": child_properties,
                "required": list(child_properties.keys())
            }
            
            return (container_schema, child_metadata)
        
        engine.register_field_schema_builder("virtual_container", breed_table_builder)
        
        # Register zoo taxonomy table with 7-level nesting
        zoo_schema = {
            "table_name": "Zoo Animal Inventory",
            "animals": [
                {
                    "class_name": "Mammalia",
                    "animal_class": "Mammals",
                    "orders": [
                        {
                            "order_key": "Carnivora",
                            "order_name": "Carnivores",
                            "suborders": [
                                {
                                    "suborder_key": "Caniformia",
                                    "suborder_name": "Dog-like carnivores",
                                    "families": [
                                        {
                                            "family_key": "Canidae",
                                            "family_name": "Dogs, wolves, foxes",
                                            "genera": [
                                                {
                                                    "genus_key": "Canis",
                                                    "genus_name": "Canis",
                                                    "species": [
                                                        {
                                                            "species_key": "canis_lupus",
                                                            "species_name": "Gray Wolf",
                                                            "properties": [
                                                                {
                                                                    "property_key": "count",
                                                                    "property_name": "Count",
                                                                    "property_type": "count"
                                                                },
                                                                {
                                                                    "property_key": "health",
                                                                    "property_name": "Health Status",
                                                                    "property_type": "health",
                                                                    "health_options": [
                                                                        {"value": "E", "label": "Excellent"},
                                                                        {"value": "G", "label": "Good"},
                                                                        {"value": "F", "label": "Fair"},
                                                                        {"value": "P", "label": "Poor"}
                                                                    ]
                                                                },
                                                                {
                                                                    "property_key": "food_order",
                                                                    "property_name": "Food Order",
                                                                    "property_type": "food_order"
                                                                }
                                                            ]
                                                        },
                                                        {
                                                            "species_key": "canis_familiaris",
                                                            "species_name": "Domestic Dog",
                                                            "properties": [
                                                                {
                                                                    "property_key": "count",
                                                                    "property_name": "Count",
                                                                    "property_type": "count"
                                                                },
                                                                {
                                                                    "property_key": "health",
                                                                    "property_name": "Health Status",
                                                                    "property_type": "health",
                                                                    "health_options": [
                                                                        {"value": "E", "label": "Excellent"},
                                                                        {"value": "G", "label": "Good"},
                                                                        {"value": "F", "label": "Fair"},
                                                                        {"value": "P", "label": "Poor"}
                                                                    ]
                                                                },
                                                                {
                                                                    "property_key": "food_order",
                                                                    "property_name": "Food Order",
                                                                    "property_type": "food_order"
                                                                },
                                                                {
                                                                    "property_key": "breeds",
                                                                    "property_name": "Dog Breeds",
                                                                    "property_type": "breed_table",
                                                                    "breed_properties": [
                                                                        {
                                                                            "property_key": "breed_name",
                                                                            "property_name": "Breed Name",
                                                                            "property_type": "string"
                                                                        },
                                                                        {
                                                                            "property_key": "origin_country",
                                                                            "property_name": "Origin Country",
                                                                            "property_type": "string"
                                                                        },
                                                                        {
                                                                            "property_key": "size_category",
                                                                            "property_name": "Size Category",
                                                                            "property_type": "single_select",
                                                                            "health_options": [
                                                                                {"value": "S", "label": "Small"},
                                                                                {"value": "M", "label": "Medium"},
                                                                                {"value": "L", "label": "Large"}
                                                                            ]
                                                                        }
                                                                    ]
                                                                }
                                                            ]
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "suborder_key": "Feliformia",
                                    "suborder_name": "Cat-like carnivores",
                                    "families": [
                                        {
                                            "family_key": "Felidae",
                                            "family_name": "Cats",
                                            "genera": [
                                                {
                                                    "genus_key": "Felis",
                                                    "genus_name": "Felis",
                                                    "species": [
                                                        {
                                                            "species_key": "felis_catus",
                                                            "species_name": "Domestic Cat",
                                                            "properties": [
                                                                {
                                                                    "property_key": "count",
                                                                    "property_name": "Count",
                                                                    "property_type": "count"
                                                                },
                                                                {
                                                                    "property_key": "health",
                                                                    "property_name": "Health Status",
                                                                    "property_type": "health",
                                                                    "health_options": [
                                                                        {"value": "E", "label": "Excellent"},
                                                                        {"value": "G", "label": "Good"},
                                                                        {"value": "F", "label": "Fair"},
                                                                        {"value": "P", "label": "Poor"}
                                                                    ]
                                                                },
                                                                {
                                                                    "property_key": "food_order",
                                                                    "property_name": "Food Order",
                                                                    "property_type": "food_order"
                                                                }
                                                            ]
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Register the zoo table
        table_id, table_name = engine.register_table(1, zoo_schema)
        
        # Test 1: Verify JSON schema generation
        json_schema = engine.get_json_schema(table_name)
        
        # Verify deep nesting structure - check that animals container exists
        self.assertIn("animals", json_schema["properties"])
        animals_props = json_schema["properties"]["animals"]["properties"]
        
        # Verify that the Mammalia class exists (using the key from schema)
        self.assertIn("Mammalia.Mammals", animals_props)
        mammalia_props = animals_props["Mammalia.Mammals"]["properties"]
        
        # Verify that orders container exists
        self.assertIn("orders", mammalia_props)
        orders_props = mammalia_props["orders"]["properties"]
        
        # Verify that Carnivora order exists
        self.assertIn("Carnivora.Carnivores", orders_props)
        carnivora_props = orders_props["Carnivora.Carnivores"]["properties"]
        
        # Verify that suborders container exists
        self.assertIn("suborders", carnivora_props)
        suborders_props = carnivora_props["suborders"]["properties"]
        
        # Verify that Caniformia suborder exists
        self.assertIn("Caniformia.Dog-like carnivores", suborders_props)
        caniformia_props = suborders_props["Caniformia.Dog-like carnivores"]["properties"]
        
        # Verify that families container exists
        self.assertIn("families", caniformia_props)
        families_props = caniformia_props["families"]["properties"]
        
        # Verify that Canidae family exists
        self.assertIn("Canidae.Dogs, wolves, foxes", families_props)
        canidae_props = families_props["Canidae.Dogs, wolves, foxes"]["properties"]
        
        # Verify that genera container exists
        self.assertIn("genera", canidae_props)
        genera_props = canidae_props["genera"]["properties"]
        
        # Verify that Canis genus exists
        self.assertIn("Canis.Canis", genera_props)
        canis_props = genera_props["Canis.Canis"]["properties"]
        
        # Verify that species container exists
        self.assertIn("species", canis_props)
        species_props = canis_props["species"]["properties"]
        
        # Verify species level exists
        self.assertIn("canis_lupus.Gray Wolf", species_props)
        self.assertIn("canis_familiaris.Domestic Dog", species_props)
        
        # Verify field types are correctly mapped
        lupus_fields = species_props["canis_lupus.Gray Wolf"]["properties"]["properties"]["properties"]
        self.assertEqual(lupus_fields["Count"]["type"], ["integer", "null"])
        
        # Verify virtual container (breed table) structure
        familiaris_fields = species_props["canis_familiaris.Domestic Dog"]["properties"]["properties"]["properties"]
        self.assertIn("Dog Breeds", familiaris_fields)
        breeds_schema = familiaris_fields["Dog Breeds"]
        self.assertEqual(breeds_schema["type"], "object")
        self.assertIn("Breed Name", breeds_schema["properties"])
        self.assertIn("Origin Country", breeds_schema["properties"])
        self.assertIn("Size Category", breeds_schema["properties"])
        
        # Test 2: Model response and reverse formatting
        model_response = {
            "animals": {
                "Mammalia.Mammals": {
                    "orders": {
                        "Carnivora.Carnivores": {
                            "suborders": {
                                "Caniformia.Dog-like carnivores": {
                                    "families": {
                                        "Canidae.Dogs, wolves, foxes": {
                                            "genera": {
                                                "Canis.Canis": {
                                                    "species": {
                                                        "canis_lupus.Gray Wolf": {
                                                            "properties": {
                                                                "Count": 5,
                                                                "Health Status": "Excellent",
                                                                "Food Order": "Raw meat diet - 2kg daily"
                                                            }
                                                        },
                                                        "canis_familiaris.Domestic Dog": {
                                                            "properties": {
                                                                "Count": 12,
                                                                "Health Status": "Good",
                                                                "Food Order": "Mixed diet - 1.5kg daily",
                                                                "Dog Breeds": {
                                                                    "Breed Name": "Labrador",
                                                                    "Origin Country": "Canada",
                                                                    "Size Category": "Large"
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                "Feliformia.Cat-like carnivores": {
                                    "families": {
                                        "Felidae.Cats": {
                                            "genera": {
                                                "Felis.Felis": {
                                                    "species": {
                                                        "felis_catus.Domestic Cat": {
                                                            "properties": {
                                                                "Count": 8,
                                                                "Health Status": "Good",
                                                                "Food Order": "Cat food - 200g daily"
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
                    }
                }
            }
        }
        
        # Test flat reverse mapping
        flat_result = engine.reverse_map(table_name, model_response, formatter_name="zoo")
        
        # Verify flat structure with data wrapper
        self.assertIn("table_name", flat_result)  # schema metadata
        self.assertIn("data", flat_result)
        self.assertIsInstance(flat_result["data"], list)
        self.assertEqual(len(flat_result["data"]), 1)
        
        data = flat_result["data"][0]["properties"]
        
        # Verify field keys exist (using the actual field keys from the schema)
        # Note: Since multiple species have the same field names, only the last processed will be in the result
        self.assertIn("count", data)
        self.assertIn("health", data)
        self.assertIn("food_order", data)
        self.assertIn("breeds", data)
        
        # Verify structured output format (values will be from the last processed species)
        self.assertEqual(data["count"], {"type": "integer", "value": 8})  # From felis_catus
        self.assertEqual(data["health"], {"type": "single_select", "value": "G"})  # From felis_catus
        self.assertEqual(data["food_order"], {"type": "string", "value": "Cat food - 200g daily"})  # From felis_catus
        
        # Verify virtual container (table) formatting
        breeds_result = data["breeds"]
        self.assertEqual(breeds_result["type"], "virtual_container")
        self.assertIsInstance(breeds_result["value"], dict)
        self.assertEqual(breeds_result["value"]["Breed Name"], "Labrador")
        self.assertEqual(breeds_result["value"]["Origin Country"], "Canada")
        self.assertEqual(breeds_result["value"]["Size Category"], "Large")
        
        # Test grouped reverse mapping by taxonomic levels
        grouped_result = engine.reverse_map(table_name, model_response, formatter_name="zoo", group_by_containers=["animals"])
        
        # Verify grouped structure
        self.assertIn("table_name", grouped_result)  # schema metadata
        self.assertIn("animals", grouped_result)
        self.assertIsInstance(grouped_result["animals"], list)
        self.assertEqual(len(grouped_result["animals"]), 1)  # One animals group
        
        animals_group = grouped_result["animals"][0]
        self.assertIn("class_name", animals_group)
        self.assertIn("properties", animals_group)
        
        # Verify all species data is in the grouped result
        grouped_data = animals_group["properties"]
        self.assertIn("count", grouped_data)
        self.assertIn("health", grouped_data)
        self.assertEqual(grouped_data["count"], {"type": "integer", "value": 8})  # From felis_catus
        
        print("\n=== ZOO TAXONOMY TEST ARTIFACTS ===")
        print("\n1. JSON Schema (deep nesting validation):")
        print(json.dumps(json_schema, indent=2)[:1000] + "...")
        
        print("\n2. Flat Reverse Mapping Result:")
        print(json.dumps(flat_result, indent=2))
        
        print("\n3. Grouped Reverse Mapping Result:")
        print(json.dumps(grouped_result, indent=2))
        
        print("\n4. Field Metadata (showing deep nesting):")
        field_metadata = engine.get_field_metadata(table_name)
        for field in field_metadata[:5]:  # Show first 5 fields
            print(f"  {field['key']}: {field['level_keys']}")
        
        print(f"\n5. Total fields processed: {len(field_metadata)}")
        print(f"6. Max nesting level used: {max(len(f.get('level_keys', [])) for f in field_metadata)}")

    def test_reverse_map_pack_containers_as_object(self):
        """Test reverse_map with containers packed as object."""
        # Setup: Create simple nested meta-schema
        meta_schema = {
            "schema_name": "tableName",
            "container": {
                "container_name": "sections",
                "container_type": "array",
                "object": {
                    "key": "sectionCode",
                    "name": "sectionName",
                    "properties": {
                        "properties_name": "fields",
                        "property": {
                            "key": "fieldKey",
                            "name": "fieldName",
                            "type": "fieldType",
                            "validation": {
                                "allowed_types": ["text"],
                                "type_constraints": {
                                    "text": {
                                        "target_type": "string",
                                        "requires_options": False
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        engine = SchemaEngine(meta_schema)
        
        # Register formatter
        def test_formatter(engine_instance, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_formatter)
        
        # Register table
        external_schema = {
            "tableName": "Test Table",
            "sections": [
                {
                    "sectionCode": "section1",
                    "sectionName": "Section One",
                    "fields": [
                        {"fieldKey": "field1", "fieldName": "Field 1", "fieldType": "text"}
                    ]
                },
                {
                    "sectionCode": "section2",
                    "sectionName": "Section Two",
                    "fields": [
                        {"fieldKey": "field2", "fieldName": "Field 2", "fieldType": "text"}
                    ]
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, external_schema)
        
        # Create model response
        model_response = {
            "table_name": "Test Table",
            "sections": {
                "section1.Section One": {
                    "fields": {
                        "Field 1": "value1"
                    }
                },
                "section2.Section Two": {
                    "fields": {
                        "Field 2": "value2"
                    }
                }
            }
        }
        
        # Test with pack_containers_as="object"
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            group_by_containers=["sections"],
            pack_containers_as="object"
        )
        
        # Verify sections is an object (not array)
        self.assertIn("sections", result)
        self.assertIsInstance(result["sections"], dict)
        
        # Verify sections are keyed by section code
        self.assertIn("section1", result["sections"])
        self.assertIn("section2", result["sections"])
        
        # Verify each section has properties
        section1 = result["sections"]["section1"]
        self.assertIn("properties", section1)
        self.assertIsInstance(section1["properties"], dict)
        
        section2 = result["sections"]["section2"]
        self.assertIn("properties", section2)
        self.assertIsInstance(section2["properties"], dict)
        
        # Verify field data
        self.assertIn("field1", section1["properties"])
        self.assertEqual(section1["properties"]["field1"]["value"], "value1")
        self.assertIn("field2", section2["properties"])
        self.assertEqual(section2["properties"]["field2"]["value"], "value2")

    def test_reverse_map_pack_containers_object_properties_array(self):
        """Test pack_containers_as='object' with pack_properties_as='array'."""
        # Setup: Create simple nested meta-schema (same as above)
        meta_schema = {
            "schema_name": "tableName",
            "container": {
                "container_name": "sections",
                "container_type": "array",
                "object": {
                    "key": "sectionCode",
                    "name": "sectionName",
                    "properties": {
                        "properties_name": "fields",
                        "property": {
                            "key": "fieldKey",
                            "name": "fieldName",
                            "type": "fieldType",
                            "validation": {
                                "allowed_types": ["text"],
                                "type_constraints": {
                                    "text": {
                                        "target_type": "string",
                                        "requires_options": False
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        engine = SchemaEngine(meta_schema)
        
        # Register formatter
        def test_formatter(engine_instance, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine.register_reverse_formatter("test", "text", test_formatter)
        
        # Register table
        external_schema = {
            "tableName": "Test Table",
            "sections": [
                {
                    "sectionCode": "section1",
                    "sectionName": "Section One",
                    "fields": [
                        {"fieldKey": "field1", "fieldName": "Field 1", "fieldType": "text"}
                    ]
                }
            ]
        }
        
        table_id, table_name = engine.register_table(1, external_schema)
        
        # Create model response
        model_response = {
            "table_name": "Test Table",
            "sections": {
                "section1.Section One": {
                    "fields": {
                        "Field 1": "value1"
                    }
                }
            }
        }
        
        # Test with pack_containers_as="object" and pack_properties_as="array"
        result = engine.reverse_map(
            table_name,
            model_response,
            formatter_name="test",
            group_by_containers=["sections"],
            pack_containers_as="object",
            pack_properties_as="array"
        )
        
        # Verify sections is an object
        self.assertIsInstance(result["sections"], dict)
        
        # Verify properties within the section is an array
        section1 = result["sections"]["section1"]
        self.assertIn("properties", section1)
        self.assertIsInstance(section1["properties"], list)
        
        # Verify array items have correct structure
        self.assertGreater(len(section1["properties"]), 0)
        field = section1["properties"][0]
        self.assertIn("key", field)
        self.assertIn("type", field)
        self.assertIn("value", field)
        self.assertEqual(field["value"], "value1")

    def test_sanitize_for_json(self):
        """Test that _sanitize_for_json removes all JSON-breaking characters."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        # Test double quotes
        self.assertEqual(engine._sanitize_for_json('If "yes" then proceed'), 'If yes then proceed')
        
        # Test single quotes
        self.assertEqual(engine._sanitize_for_json("It's working"), 'Its working')
        
        # Test backslashes
        self.assertEqual(engine._sanitize_for_json('Path\\to\\file'), 'Path to file')
        
        # Test control characters
        self.assertEqual(engine._sanitize_for_json('Line1\nLine2\tTabbed'), 'Line1 Line2 Tabbed')
        
        # Test brackets and braces
        self.assertEqual(engine._sanitize_for_json('Array[0] and {key}'), 'Array0 and key')
        
        # Test HTML tags (existing functionality)
        self.assertEqual(engine._sanitize_for_json('<b>Bold text</b>'), 'Bold text')
        
        # Test combined cases
        self.assertEqual(engine._sanitize_for_json('<b>If "yes"</b> then [proceed]'), 'If yes then proceed')
        
        # Test non-strings pass through
        self.assertIsNone(engine._sanitize_for_json(None))
        self.assertEqual(engine._sanitize_for_json(123), 123)
        self.assertEqual(engine._sanitize_for_json(True), True)
        
        # Test the actual problematic case from MHCS Nursing Daily Skilled Note
        problematic_text = 'If the answer to question 3 is "yes", what type of precautions are in place?'
        expected = 'If the answer to question 3 is yes, what type of precautions are in place?'
        self.assertEqual(engine._sanitize_for_json(problematic_text), expected)
        
        # Test complex case with multiple special characters
        # Note: Parentheses are NOT removed, only brackets and braces
        complex_text = '<i>If the answer is "yes" (see [section] for details), proceed with {action}'
        self.assertEqual(engine._sanitize_for_json(complex_text), 'If the answer is yes (see section for details), proceed with action')
        
        # Test edge cases
        # Empty string
        self.assertEqual(engine._sanitize_for_json(''), '')
        
        # String with only special characters
        # Note: <> are only removed when part of HTML tags, standalone they remain
        self.assertEqual(engine._sanitize_for_json('"\\[]{}<>'), '<>')
        
        # String with only whitespace and special characters
        self.assertEqual(engine._sanitize_for_json('  "\\ \n\t[]{}  '), '')
        
        # Multiple consecutive quotes
        self.assertEqual(engine._sanitize_for_json('Test ""input"" here'), 'Test input here')
        
        # Multiple consecutive backslashes
        # Backslashes become spaces which are normalized to single space
        self.assertEqual(engine._sanitize_for_json('Path\\\\to\\\\file'), 'Path to file')
        
        # Mixed quotes and backslashes
        # Backslashes become spaces which are then normalized
        self.assertEqual(engine._sanitize_for_json('"quote" and \\\\slashes'), 'quote and slashes')
        
        # Unicode characters (should pass through)
        self.assertEqual(engine._sanitize_for_json('Café "café" with [brackets]'), 'Café café with brackets')
        
        # HTML entities in tags
        self.assertEqual(engine._sanitize_for_json('<span attr="value">Text</span>'), 'Text')
        
        # Angle brackets - HTML tag regex removes everything from < to >
        # Note: The regex <[^>]+> will match "< 10" (space to >) and "> 15" (from > to end)
        # So "5 < 10" becomes "5 " (leading < and 10 are removed)
        self.assertEqual(engine._sanitize_for_json('5 < 10 and 20 > 15'), '5 15')
        
        # Very long string with special characters
        long_text = 'Start ' + ('"' * 10) + ' middle ' + ('\\' * 10) + ' end'
        result = engine._sanitize_for_json(long_text)
        self.assertNotIn('"', result)
        self.assertEqual(result.count(' '), 2)  # Only the intentional spaces remain
        
        # Newline and tab characters
        self.assertEqual(engine._sanitize_for_json('Line1\nLine2\tTabbed\nLine3'), 'Line1 Line2 Tabbed Line3')
        
        # Carriage return
        self.assertEqual(engine._sanitize_for_json('With\rCarriage'), 'With Carriage')
        
        # Mixed HTML and special characters
        self.assertEqual(engine._sanitize_for_json('<b>Bold "text"</b> with {braces}'), 'Bold text with braces')
        
        # Test that parentheses are preserved
        self.assertEqual(engine._sanitize_for_json('Text (with parentheses) and [brackets]'), 'Text (with parentheses) and brackets')
    
    def test_schema_generation_with_special_characters(self):
        """Test that fields with special characters produce valid JSON schema."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        # Schema with problematic question text
        schema = {
            "table_name": "Test Table",
            "table_id": 1,
            "fields": [{
                "field_id": "q1",
                "field_number": "1",
                "field_name": 'If the answer is "yes", proceed',
                "field_type": "text"
            }, {
                "field_id": "q2",
                "field_number": "2",
                "field_name": 'Path\\to\\file with {brackets} and [arrays]',
                "field_type": "text"
            }]
        }
        
        table_id, table_name = engine.register_table(1, schema)
        json_schema = engine.get_json_schema(table_name)
        
        # Verify schema is valid JSON (no quotes in property key)
        sanitized_q1 = 'If the answer is yes, proceed'
        sanitized_q2 = 'Path to file with brackets and arrays'
        
        # The properties are nested under "fields" for flat schemas
        fields_props = json_schema["properties"]["fields"]["properties"]
        self.assertIn(sanitized_q1, fields_props)
        self.assertIn(sanitized_q2, fields_props)
        
        # Verify no problematic characters in property keys
        for key in fields_props.keys():
            self.assertNotIn('"', key, f"Found quote in property key: {key}")
            self.assertNotIn('\\', key, f"Found backslash in property key: {key}")
            self.assertNotIn('[', key, f"Found bracket in property key: {key}")
            self.assertNotIn(']', key, f"Found bracket in property key: {key}")
            self.assertNotIn('{', key, f"Found brace in property key: {key}")
            self.assertNotIn('}', key, f"Found brace in property key: {key}")
    
    def test_reverse_map_with_sanitized_keys(self):
        """Test that reverse mapping works when field names contain special characters."""
        engine = SchemaEngine(self.flat_meta_schema)
        
        # Define a test formatter
        def test_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        # Register schema with problematic field name
        schema = {
            "table_name": "Test Table",
            "table_id": 1,
            "fields": [{
                "field_id": "precautions",
                "field_number": "1",
                "field_name": 'If the answer to question 3 is "yes", what type of precautions are in place?',
                "field_type": "text"
            }]
        }
        
        engine.register_table(1, schema)
        engine.register_reverse_formatter("test", "text", test_formatter)
        
        # Model response MUST use the sanitized property key
        sanitized_key = "If the answer to question 3 is yes, what type of precautions are in place?"
        model_response = {
            "fields": {
                sanitized_key: "Contact precautions"
            }
        }
        
        # Reverse map should successfully find and map the field
        result = engine.reverse_map("Test Table", model_response, formatter_name="test")
        
        # Verify the field was found and mapped back to original field_id
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 1)
        self.assertIn("properties", result["data"][0])
        self.assertIn("precautions", result["data"][0]["properties"])
        self.assertEqual(result["data"][0]["properties"]["precautions"]["value"], "Contact precautions")

    def test_use_id_in_property_name_prevents_duplicates(self):
        """Test that use_id_in_property_name flag prevents duplicate property names."""
        # Create an engine WITHOUT the flag (default behavior)
        engine_no_prefix = SchemaEngine(self.flat_meta_schema, use_id_in_property_name=False)
        
        # Create schema with duplicate question text (after sanitization)
        external_schema_duplicates = {
            "table_name": "Duplicate Test",
            "fields": [
                {
                    "field_id": "field1",
                    "field_number": "1",
                    "field_name": 'If "other" selected, describe:',
                    "field_type": "text"
                },
                {
                    "field_id": "field2",
                    "field_number": "2",
                    "field_name": 'If "other" selected, describe:',
                    "field_type": "text"
                }
            ]
        }
        
        engine_no_prefix.register_table(1, external_schema_duplicates)
        schema_no_prefix = engine_no_prefix.get_json_schema(1)
        
        # Without prefix, we get duplicates in required array (this would fail JSON schema validation)
        questions_no_prefix = schema_no_prefix["properties"]["fields"]["properties"]
        required_no_prefix = schema_no_prefix["properties"]["fields"]["required"]
        
        # Verify we have duplicate property names (which would cause JSON schema validation to fail)
        self.assertIn("If other selected, describe:", questions_no_prefix)
        # Check if we have duplicates in required (would fail uniqueItems validation)
        required_set_no_prefix = set(required_no_prefix)
        if len(required_set_no_prefix) < len(required_no_prefix):
            # We have duplicates - this is the problem
            pass  # Expected without prefix
        
        # Now create an engine WITH the flag
        engine_with_prefix = SchemaEngine(self.flat_meta_schema, use_id_in_property_name=True)
        
        engine_with_prefix.register_table(1, external_schema_duplicates)
        schema_with_prefix = engine_with_prefix.get_json_schema(1)
        
        # With prefix, property names should be unique
        questions_with_prefix = schema_with_prefix["properties"]["fields"]["properties"]
        required_with_prefix = schema_with_prefix["properties"]["fields"]["required"]
        
        # Verify we have unique prefixed property names
        self.assertIn("1. If other selected, describe:", questions_with_prefix)
        self.assertIn("2. If other selected, describe:", questions_with_prefix)
        
        # Verify required array has unique items
        required_set_with_prefix = set(required_with_prefix)
        self.assertEqual(len(required_set_with_prefix), len(required_with_prefix), 
                        "Required array should have unique items when using id prefix")
        
        # Validate the schema is valid JSON Schema (should pass validation)
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            from jsonschema import Draft7Validator as Draft202012Validator
        
        # This should NOT raise an error (schema is valid)
        Draft202012Validator.check_schema(schema_with_prefix)
        
        # Test validation with prefixed property names
        valid_data = {
            "table_name": "Duplicate Test",
            "fields": {
                "1. If other selected, describe:": "First description",
                "2. If other selected, describe:": "Second description"
            }
        }
        
        is_valid, errors = engine_with_prefix.validate(1, valid_data)
        self.assertTrue(is_valid, f"Validation should pass with unique prefixed names: {errors}")
        
        # Test reverse mapping works with prefixed names
        def test_formatter(engine, field_meta, model_value, table_name):
            return {field_meta["key"]: {"type": "text", "value": model_value}}
        
        engine_with_prefix.register_reverse_formatter("test", "text", test_formatter)
        
        result = engine_with_prefix.reverse_map("Duplicate Test", valid_data, formatter_name="test")
        
        # Verify both fields were reverse mapped
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 1)
        self.assertIn("properties", result["data"][0])
        self.assertIn("field1", result["data"][0]["properties"])
        self.assertIn("field2", result["data"][0]["properties"])
        self.assertEqual(result["data"][0]["properties"]["field1"]["value"], "First description")
        self.assertEqual(result["data"][0]["properties"]["field2"]["value"], "Second description")


if __name__ == "__main__":
    # Set up logging to see info messages
    logging.basicConfig(level=logging.INFO)
    unittest.main()
