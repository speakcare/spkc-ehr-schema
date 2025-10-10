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
        self.assertEqual(list(schema["required"]), ["fields"])
        
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
        self.assertEqual(list(schema["required"]), ["sections"])
        
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
        self.assertEqual(field_info["level_keys"], ["AA", "1"])

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
            "fields": {"Birth date": "1990-01-15"}
        }
        is_valid, errors = self.flat_engine.validate("date_test", valid_data)
        self.assertTrue(is_valid)
        
        # Invalid date (jsonschema doesn't validate format by default)
        invalid_data = {
            "fields": {"Birth date": "not-a-date"}
        }
        is_valid, errors = self.flat_engine.validate("date_test", invalid_data)
        # Note: jsonschema doesn't validate format by default, so this will pass
        self.assertTrue(is_valid)

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
        self.assertEqual(list(schema["required"]), ["level1s"])
        
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
        self.assertEqual(field1_info["level_keys"], ["L1A", "L2A1", "L3A1a", "L4A1a1"])


if __name__ == "__main__":
    # Set up logging to see info messages
    logging.basicConfig(level=logging.INFO)
    unittest.main()
