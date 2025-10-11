"""
Tests for SchemaConverterEngine.

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

from schema_converter_engine import SchemaConverterEngine


class TestSchemaConverterEngine(unittest.TestCase):
    """Test cases for SchemaConverterEngine."""

    def setUp(self):
        """Set up test fixtures."""
        # Meta-schema language definition for flat tables
        self.flat_meta_schema = {
            "schema_name": "table_name",
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
                                "target_type": "singleSelect",
                                "requires_options": True,
                                "options_field": "field_options"
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
                                "target_type": "singleSelect",
                                "requires_options": True,
                                "options_field": "field_options",
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
                                                "target_type": "singleSelect",
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
        
        self.flat_engine = SchemaConverterEngine(self.flat_meta_schema)
        self.nested_engine = SchemaConverterEngine(self.nested_meta_schema)
        
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

        self.flat_engine.register_table("patient_assessment", external_schema)
        
        # Check table is registered
        self.assertIn("patient_assessment", self.flat_engine.list_tables())
        
        # Get JSON schema
        schema = self.flat_engine.get_json_schema("patient_assessment")
        
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
        self.assertEqual(props["Patient gender"]["enum"], ["Male", "Female", "Other"])

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

        self.nested_engine.register_table("mds_assessment", external_schema)
        
        schema = self.nested_engine.get_json_schema("mds_assessment")
        
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
        self.assertEqual(gender_props["Gender selection"]["enum"], ["Male", "Female"])

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

        self.flat_engine.register_table("complex_test", external_schema)
        
        schema = self.flat_engine.get_json_schema("complex_test")
        fields_container = schema["properties"]["fields"]
        priority_field = fields_container["properties"]["Priority Level"]
        
        self.assertEqual(priority_field["type"], ["string", "null"])
        self.assertEqual(priority_field["enum"], ["High", "Medium", "Low"])

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
        self.flat_engine.register_table("test_table", external_schema)
        
        # Re-registration should log info and replace
        with patch('schema_converter_engine.logger') as mock_logger:
            self.flat_engine.register_table("test_table", external_schema)
            mock_logger.info.assert_called_with("Re-registering table_id=%s; replacing previous schema", "test_table")
        
        # Verify replacement
        schema = self.flat_engine.get_json_schema("test_table")
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

        self.nested_engine.register_table("key_test", external_schema)
        
        # Get field index
        table_record = self.nested_engine._tables["key_test"]
        field_index = table_record["field_index"]
        
        # Verify level keys are captured
        self.assertEqual(len(field_index), 1)
        field_info = field_index[0]
        self.assertEqual(field_info["key"], "AA1")
        self.assertEqual(field_info["id"], "1")
        self.assertEqual(field_info["name"], "Test question")
        self.assertEqual(field_info["level_keys"], ["AA", "1", "questions"])

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

        self.flat_engine.register_table("validation_test", external_schema)
        
        # Valid data
        valid_data = {
            "table_name": "Validation Test",
            "fields": {
                "Full name": "John Doe",
                "Age in years": 30,
                "Gender": "M"
            }
        }
        
        is_valid, errors = self.flat_engine.validate("validation_test", valid_data)
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

        self.flat_engine.register_table("validation_test", external_schema)
        
        # Invalid data
        invalid_data = {
            "table_name": "Validation Test",
            "fields": {
                "Full name": "John Doe",
                "Age in years": "not_a_number",  # Wrong type
                "Gender": "X"  # Not in enum
            }
        }
        
        is_valid, errors = self.flat_engine.validate("validation_test", invalid_data)
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

        self.flat_engine.register_table("date_test", external_schema)
        
        # Valid date
        valid_data = {
            "table_name": "Date Test",
            "fields": {"Birth date": "1990-01-15"}
        }
        is_valid, errors = self.flat_engine.validate("date_test", valid_data)
        self.assertTrue(is_valid)
        
        # Invalid date (jsonschema doesn't validate format by default)
        invalid_data = {
            "table_name": "Date Test",
            "fields": {"Birth date": "not-a-date"}
        }
        is_valid, errors = self.flat_engine.validate("date_test", invalid_data)
        # Note: jsonschema doesn't validate format by default, but our custom validator does
        # So this will fail validation due to custom date validator
        self.assertFalse(is_valid)
        self.assertIn("Invalid ISO date format", errors[0])

    def test_unknown_table_errors(self):
        """Test errors for unknown table operations."""
        with self.assertRaises(KeyError):
            self.flat_engine.get_json_schema("unknown_table")
        
        with self.assertRaises(KeyError):
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
            self.flat_engine.register_table("error_test", external_schema)
        
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
            SchemaConverterEngine(invalid_meta_schema_1)
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
            SchemaConverterEngine(invalid_meta_schema_2)
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
            SchemaConverterEngine(invalid_meta_schema_3)
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
                                                            'rad': {'target_type': 'singleSelect', 'requires_options': True, 'options_field': 'level5_options'},
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

        engine = SchemaConverterEngine(meta_schema)

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

        engine.register_table('comprehensive_nested_form', external_schema)
        schema = engine.get_json_schema('comprehensive_nested_form')
        
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
        self.assertEqual(field_props["Third field"]["enum"], ["Option A1", "Option A2", "Option A3"])
        
        # Verify field metadata collection
        table_record = engine._tables["comprehensive_nested_form"]
        field_index = table_record["field_index"]
        self.assertEqual(len(field_index), 6)  # Total fields across all containers
        
        # Check specific field metadata
        field1_info = next(f for f in field_index if f["key"] == "field1")
        self.assertEqual(field1_info["key"], "field1")
        self.assertEqual(field1_info["id"], "1")
        self.assertEqual(field1_info["name"], "First field")
        self.assertEqual(field1_info["level_keys"], ["L1A", "L2A1", "L3A1a", "L4A1a1", "level5s"])

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
        
        self.flat_engine.register_table("test_string_table", test_schema)
        
        # Value "abc" passes JSON schema but fails custom validator
        data = {
            "table_name": "Test String",
            "fields": {"Name Field": "abc"}
        }
        
        is_valid, errors = self.flat_engine.validate("test_string_table", data)
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
        
        engine = SchemaConverterEngine(test_meta)
        
        # Register custom checkbox builder (Yes/No instead of boolean)
        def checkbox_yes_no_builder(engine, target_type, field_schema, nullable):
            return {
                "type": ["string", "null"] if nullable else "string",
                "enum": ["Yes", "No", None] if nullable else ["Yes", "No"],
                "description": "Select Yes or No"
            }
        
        engine.register_schema_field_builder("boolean", checkbox_yes_no_builder)
        
        # Register table with boolean field
        table_schema = {
            "name": "Test Table",
            "fields": [
                {"field_name": "active", "field_type": "checkbox", "field_id": "active_id"}
            ]
        }
        
        engine.register_table("test_checkbox_table", table_schema)
        json_schema = engine.get_json_schema("test_checkbox_table")
        
        # Verify custom builder was used
        active_field = json_schema["properties"]["fields"]["properties"]["active"]
        self.assertEqual(active_field["enum"], ["Yes", "No", None])
        self.assertIn("Select Yes or No", active_field["description"])

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
        self.flat_engine.register_validator("singleSelect", single_select_validator_with_options)
        
        # Register a test table with singleSelect field
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
        
        self.flat_engine.register_table("test_single_select", test_schema)
        
        # Test with valid choice
        valid_data = {
            "table_name": "Test Single Select",
            "fields": {"Priority Level": "High"}
        }
        
        is_valid, errors = self.flat_engine.validate("test_single_select", valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test with invalid choice
        invalid_data = {
            "table_name": "Test Single Select", 
            "fields": {"Priority Level": "Unknown"}  # Not in choices
        }
        
        is_valid, errors = self.flat_engine.validate("test_single_select", invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("'Unknown' is not one of ['High', 'Medium', 'Low']", errors[0])

    def test_custom_builder_with_field_schema_access(self):
        """Test that custom builders can access field_schema for schema generation."""
        def percent_with_precision_builder(engine, target_type, field_schema, nullable):
            # Access field details from schema
            field_name = field_schema.get("field_name", "Percent")  # Use field_name from meta-schema
            precision = field_schema.get("precision", 2)  # Default 2 decimal places
            
            return {
                "type": ["number", "null"] if nullable else "number",
                "minimum": 0,
                "maximum": 100,
                "multipleOf": 10 ** -precision,
                "description": f"{field_name}: Percentage with {precision} decimal precision"
            }
        
        # Create new engine and register custom builder
        test_meta = copy.deepcopy(self.flat_meta_schema)
        engine = SchemaConverterEngine(test_meta)
        engine.register_schema_field_builder("percent", percent_with_precision_builder)
        
        # Register table with percent field that has precision info
        table_schema = {
            "name": "Test Table",
            "fields": [
                {"field_name": "accuracy", "field_type": "percent", "precision": 3, "field_id": "accuracy_id"}
            ]
        }
        
        engine.register_table("test_percent_table", table_schema)
        json_schema = engine.get_json_schema("test_percent_table")
        
        # Verify custom builder was used with field-specific precision
        accuracy_field = json_schema["properties"]["fields"]["properties"]["accuracy"]
        self.assertEqual(accuracy_field["multipleOf"], 0.001)  # 10^-3
        self.assertIn("accuracy: Percentage with 3 decimal precision", accuracy_field["description"])

    def test_custom_properties_name_field_path(self):
        """Test that field paths use the correct properties_name from meta-schema."""
        # Create meta-schema with custom properties_name
        custom_meta = copy.deepcopy(self.flat_meta_schema)
        custom_meta["properties"]["properties_name"] = "custom_fields"  # Change from "fields"
        
        engine = SchemaConverterEngine(custom_meta)
        
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
        
        engine.register_table("test_custom_props", table_schema)
        
        # Check that the field was registered
        field_index = engine._tables["test_custom_props"]["field_index"]
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
        
        self.flat_engine.register_table("test_text_table", test_schema)
        
        # Test with valid string data
        valid_data = {
            "table_name": "Test Text",
            "fields": {"Text Field": "Some text"}
        }
        
        is_valid, errors = self.flat_engine.validate("test_text_table", valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test with invalid string data (should fail JSON schema validation)
        invalid_data = {
            "table_name": "Test Text",
            "fields": {"Text Field": 123}  # Wrong type
        }
        
        is_valid, errors = self.flat_engine.validate("test_text_table", invalid_data)
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
        
        self.flat_engine.register_table("test_text_table", table_schema)
        json_schema = self.flat_engine.get_json_schema("test_text_table")
        
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
        
        self.flat_engine.register_table("test_metadata_table", test_schema)
        
        # Get field index from the registered table
        field_index = self.flat_engine._tables["test_metadata_table"]["field_index"]
        
        # Find a field with all metadata
        field_meta = field_index[0]  # First field
        
        # Verify all expected metadata fields are present
        expected_fields = {"key", "level_keys", "target_type", "field_schema"}
        self.assertTrue(expected_fields.issubset(set(field_meta.keys())))
        
        # Verify field_schema contains original field definition
        field_schema = field_meta["field_schema"]
        self.assertIn("field_name", field_schema)
        self.assertIn("field_type", field_schema)


if __name__ == "__main__":
    # Set up logging to see info messages
    logging.basicConfig(level=logging.INFO)
    unittest.main()
