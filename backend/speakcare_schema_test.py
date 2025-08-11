import unittest
from datetime import datetime
from speakcare_schema import AirtableSchema, AirtableFieldTypes
import json
import copy
from deepdiff import DeepDiff


class TestValidations(unittest.TestCase):

    def setUp(self):
        self.valid_temperature_schema = {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleSelect', "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "(required)"},
                {"name": "Temperature", "type": 'number', "options": {"precision": "1"}, "description": "(required)"},
                {"name": "Route", "type": 'singleSelect', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}]}}
            ]
        }
        self.invalid_schema = {
            "name": "invalidRecord",
            "fields": [
                {"name": "Units", "type": 'singleLineText'},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'singleSelect', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}]}}
            ]
        }

    def test_init_valid_schema(self):
        self.maxDiff = None
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        schema_dict = schema.get_json_schema()
        print("schema: ", json.dumps(schema_dict, indent=4))
        self.assertEqual(schema.table_name, "temperatureRecord")

    def test_init_invalid_schema(self):
        # test wrong name
        with self.assertRaises(ValueError) as context:
             AirtableSchema("temperatureRecord", self.invalid_schema)
        self.assertTrue("Table name 'temperatureRecord' does not match the name in the schema 'invalidRecord'" in str(context.exception))
        # test number field without options
        with self.assertRaises(ValueError) as context:
             AirtableSchema("invalidRecord", self.invalid_schema)
        self.assertTrue("Error creating schema for table 'invalidRecord' for field name 'Temperature'" in str(context.exception))

    def test_validate_record_valid(self):
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            "Units": "Fahrenheit",
            "Temperature": 103,
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_record_invalid_field(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][1]["description"] = ""
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Units": "Fahrenheit",
            "Temperature": "high",
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Field is None or failed validation 'Temperature' in table temperatureRecord: Value 'high' cannot be converted to a number." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)

    def test_validate_record_invalid_required_field(self):
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            "Units": "Fahrenheit",
            "Temperature": "high",
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for a required field 'Temperature' in table temperatureRecord: Value 'high' cannot be converted to a number." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)


    def test_validate_record_extra_field(self):
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            "Units": "Fahrenheit",
            "Temperature": "103",
            "Route": "Tympanic",
            "Time": "12:00"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid) # extra field is ignored
        self.assertEqual(len(errors), 1) # we still get an error for the extra field

    def test_validate_record_missing_unrequired_field(self):
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            "Temperature": 103,
            "Units": "Fahrenheit",
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_record_missing_required_field(self):
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            "Temperature": 103,
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertEqual(errors[0], "Validation error: Required field 'Units' in table temperatureRecord is missing.")

    def test_validate_partial_record_missing_required_field(self):
        # In partial udpate we allow missing required fields
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            # Units is missing
            "Temperature": 103,
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_partial_record(record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_single_select_wrong_value(self):
        schema = AirtableSchema("temperatureRecord", self.valid_temperature_schema)
        record = {
            "Temperature": 103,
            "Units": "Kelvin",
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record, errors=errors)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)   

    def test_validate_multi_select_correct_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Axilla"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)        
    
    def test_validate_multi_select_incorrect_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Axilla", "Forehead", "Rectal"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Validation warning for field 'Route' in table temperatureRecord: Multi select validation errors: Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        # check the route includes only valid values
        self.assertEqual(valid_fields["Route"], ["Tympanic", "Axilla", "Rectal"])

    def test_validate_multi_select_incorrect_required_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "(required)"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Axilla", "Forehead", "Rectal"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Validation warning for field 'Route' in table temperatureRecord: Multi select validation errors: Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertEqual(valid_fields["Route"], ["Tympanic", "Axilla", "Rectal"])

    def test_validate_multi_select_incorrect_multiple_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "(required)"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Ear", "Axilla", "Forehead", "Rectal", "Mouth"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Validation warning for field 'Route' in table temperatureRecord: Multi select validation errors:" in errors[0], errors[0])
        self.assertTrue("Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Ear' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Mouth' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertEqual(valid_fields["Route"], ["Tympanic", "Axilla", "Rectal"]) 

    def test_validate_multi_select_no_valid_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Ear", "Forehead", "Mouth"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Field is None or failed validation 'Route' in table temperatureRecord: Multi select validation errors:" in errors[0], errors[0])
        self.assertTrue("Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Ear' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Mouth' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(valid_fields.get("Route", None))

    def test_validate_multi_select_no_valid_required_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "(required)"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Ear", "Forehead", "Mouth"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for a required field 'Route' in table temperatureRecord: Multi select validation errors:" in errors[0], errors[0])
        self.assertTrue("Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Ear' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Mouth' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(valid_fields.get("Route", None))
        

    def test_validate_multi_select_not_a_list_required(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "(required)"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for a required field 'Route' in table temperatureRecord: Multi select validation errors:" in errors[0], errors[0])
        self.assertTrue("Argumment 'Tympanic' is not a valid multi select list option." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(valid_fields.get("Route", None))

    def test_validate_date_correct_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateField", "type": "date"}
            ]
        })
        record = {"DateField": "2023-10-01"}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_date_incorrect_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateField", "type": "date"}
            ]
        })
        record = {"DateField": "01-10-2023"}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Date validation error: Value '01-10-2023' is not a valid ISO date." in errors[0])
        self.assertEqual(len(errors), 1)

    def test_validate_date_incorrect_required_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateField", "type": "date", "description": "(required)"}
            ]
        })
        record = {"DateField": "01-10-2023"}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Date validation error: Value '01-10-2023' is not a valid ISO date." in errors[0])
        self.assertEqual(len(errors), 1)



    def test_validate_date_time_correct_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateTimeField1", "type": "dateTime"},
                {"name": "DateTimeField2", "type": "dateTime"},
            ]
        })
        record = {
            "DateTimeField1": "2023-10-01T12:00:00Z",
            "DateTimeField2": "2023-10-01T12:00:00+00:00"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_date_time_incorrect_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateTimeField", "type": "dateTime"}
            ]
        })
        dateTimeString = "2023-10-01 25:00:00"
        record = {"DateTimeField": dateTimeString}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue(f"Date-time validation error: Value '{dateTimeString}' is not a valid ISO date-time." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)


    def test_validate_percent_correct_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "PercentField", "type": "percent", "options": {"precision": "1"}}
            ]
        })
        record = {"PercentField": 85}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_percent_incorrect_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "PercentField", "type": "percent", "options": {"precision": "1"}}
            ]
        })
        record = {"PercentField": 150}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Field is None or failed validation 'PercentField' in table testSchema: Percent validation error: Value '150' is not a valid percent (0-100)." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        
    def test_validate_percent_incorrect_required_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "PercentField", "type": "percent", "options": {"precision": "1"}, "description": "(required)"}
            ]
        })
        record = {"PercentField": 150}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for a required field 'PercentField' in table testSchema: Percent validation error: Value '150' is not a valid percent (0-100)." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)

    def test_validate_checkbox_correct_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CheckboxField1", "type": "checkbox"},
                {"name": "CheckboxField2", "type": "checkbox"}
            ]
        })
        record = {
            "CheckboxField1": True,
            "CheckboxField2": False
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_checkbox_incorrect_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CheckboxField", "type": "checkbox"}
            ]
        })
        record = {"CheckboxField": "yes"}
        errors = []
        is_all_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_all_valid, json.dumps(errors))
        self.assertEqual(len(errors), 1)

    def test_validate_checkbox_incorrect_required_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CheckboxField", "type": "checkbox", "description": "(required)"}
            ]
        })
        record = {"CheckboxField": "yes"}
        errors = []
        is_all_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_all_valid, json.dumps(errors))
        self.assertEqual(len(errors), 1)



    def test_validate_currency_correct_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CurrencyField", "type": "currency", "options": {"precision": "1"}}
            ]
        })
        record = {"CurrencyField": 100.50}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_currency_incorrect_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CurrencyField", "type": "currency"}
            ]
        })
        record = {"CurrencyField": "one hundred"}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Currency validation error: Value 'one hundred' cannot be converted to a float." in errors[0])

    def test_validate_currency_incorrect_required_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CurrencyField", "type": "currency", "description": "(required)"}
            ]
        })
        record = {"CurrencyField": "one hundred"}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Currency validation error: Value 'one hundred' cannot be converted to a float." in errors[0], errors[0])        




    def test_validate_section_correct_value(self):
        main_schema = AirtableSchema("testSchema", {
            "name": "testSchema"
        })
        section1_schema = AirtableSchema("section1", {
            "name": "section1",
            "fields": [
                {"name": "DateTimeField1", "type": "dateTime"},
                {"name": "DateTimeField2", "type": "dateTime"},
            ]
        })
        section2_schema = AirtableSchema("section2", {
            "name": "section2",
            "fields": [
                {"name": "DateTimeField1", "type": "dateTime"},
                {"name": "DateTimeField2", "type": "dateTime"},
            ]
        })

        main_schema.add_section("section1", section1_schema)
        main_schema.add_section("section2", section2_schema)

        record = {
            "DateTimeField1": "2023-10-01T12:00:00Z",
            "DateTimeField2": "2023-10-01T12:00:00+00:00"
        }
        errors = []

        is_valid, valid_fields = main_schema.get_section("section1").validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0, errors)

        is_valid, valid_fields = main_schema.get_section("section2").validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0, errors)


    def test_validate_section_incorrect_value(self):

        main_schema = AirtableSchema("testSchema", {
            "name": "testSchema"
        })
        section1_schema = AirtableSchema("section1", {
            "name": "section1",
            "fields": [
                {"name": "DateTimeField", "type": "dateTime"}
            ]
        })
        section2_schema = AirtableSchema("section2", {
            "name": "section2",
            "fields": [
                {"name": "DateTimeField", "type": "dateTime"}
            ]
        })

        main_schema.add_section("section1", section1_schema)
        main_schema.add_section("section2", section2_schema)

        dateTimeString = "2023-10-01 25:00:00"
        record = {"DateTimeField": dateTimeString}
        errors = []
        is_valid, valid_fields = main_schema.get_section("section1").validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        expected_error = f"Date-time validation error: Value '{dateTimeString}' is not a valid ISO date-time."
        self.assertTrue(expected_error in errors[0], errors[0])
        self.assertEqual(len(errors), 1, errors)

        dateTimeString = "2023-10-01T12:00:00+00:00"
        record = {"DateTimeField": dateTimeString}
        is_valid, valid_fields = main_schema.get_section("section2").validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        # make sure only the previous error still listed and no new errors for this section
        self.assertTrue(expected_error in errors[0], errors[0])
        self.assertEqual(len(errors), 1, errors)







class TestJsonSchema(unittest.TestCase):

    def test_valid_json_schema(self):
        airtable_schema = {
            "name": "test_table",
            "fields": [
                {"name": "Notes", "type": AirtableFieldTypes.MULTI_LINE_TEXT, "description": "optional"},
                {"name": "Title", "type": AirtableFieldTypes.SINGLE_LINE_TEXT, "description": "optional"},
                {"name": "Units", "type": AirtableFieldTypes.SINGLE_SELECT, "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "(required)"},
                {"name": "Temperature", "type": AirtableFieldTypes.NUMBER, "options": {"precision": "1"}, "description": "(required)"},
                {"name": "Route", "type": AirtableFieldTypes.MULTI_SELECT, "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "(required)"},
                {"name": "Date", "type": AirtableFieldTypes.DATE, "description": "(required)"},
                {"name": "DateTime", "type": AirtableFieldTypes.DATE_TIME, "description": "(required)"},
                {"name": "Percent", "type": AirtableFieldTypes.PERCENT, "options": {"precision": "2"}, "description": "(required)"},
                {"name": "Percent0", "type": AirtableFieldTypes.PERCENT, "options": {"precision": "0"}},
                {"name": "Percent00", "type": AirtableFieldTypes.PERCENT},
                {"name": "Checkbox", "type": AirtableFieldTypes.CHECKBOX, "description": "(required)"},
                {"name": "Currency", "type": AirtableFieldTypes.CURRENCY, "description": "(required)"}
            ]
        }

        expected_json_schema = {
                "title": "test_table",
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string", "const": "test_table", "description": "The name of the Airtable table"
                    },
                    "patient_name": {
                        "type": ["string", "null"], "description": "The name of the patient"
                    },
                    "fields": {
                        "type": ["object", "null"],
                        "properties": {
                            "Notes": {
                                "type": ["string", "null"], "description": "optional: Multi-line text"
                            },
                            "Title": {
                                "type": ["string", "null"], "description": "optional: Single line text"
                            },
                            "Units": {
                                "type": ["string", "null"], "enum": ["Fahrenheit", "Celsius", None],
                                "description": 
                                "(required): Select one of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"
                            },
                            "Temperature": {
                                "type": ["number", "null"],"description": "(required): Must be a number with 1 decimal precision"
                            },
                            "Route": {
                                "type": ["array", "null"], "items": { "type": ["string", "null"], "enum": ["Tympanic","Oral","Rectal","Axilla"]},
                                "description": 
                                "(required): Select one or more of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"
                            },
                            "Date": {
                                "type": ["string", "null"],"description": "(required): ISO 8601 date (YYYY-MM-DD)"
                            },
                            "DateTime": {
                                "type": ["string", "null"],"description": "(required): ISO 8601 date-time (YYYY-MM-DDTHH:MM:SSZ)"
                            },
                            "Percent": {
                                "type": ["number", "null"],"description": "(required): Percentage - must be a number between 0 and 100 with 2 decimal precision"
                            },
                            "Percent0": {
                                "type": ["number", "null"],"description": "Percentage - must be a number between 0 and 100 with 0 decimal precision"
                            },
                            "Percent00": {
                                "type": ["number", "null"],"description": "Percentage - must be a number between 0 and 100 with 0 decimal precision"
                            },
                            "Checkbox": {
                                "type": "boolean","description": "(required)"
                            },
                            "Currency": {
                                "type": ["number", "null"],"description": "(required): Currency - must be a number with 0 decimal precision"
                            }
                        },
                        "required": [
                            # all fields MUST be in the required list, even if not required by model
                            "Notes","Title","Units","Temperature","Route","Date","DateTime","Percent","Percent0","Percent00","Checkbox","Currency"
                        ],
                        "additionalProperties": False
                    },
                },
                "required": ["table_name","patient_name","fields"],
                "additionalProperties": False
            }

        schema = AirtableSchema("test_table", airtable_schema)
        json_schema = schema.get_json_schema()
        print("json_schema: ", json.dumps(json_schema, indent=4))
        self.assertTrue(json_schema)
        diff = DeepDiff(json_schema, expected_json_schema, ignore_order=True)
        self.assertEqual(diff, {}, diff)
    
    def test_valid_json_schema_with_sections(self):

        main_schema = {
            "name": "test_table"
        }

        section1_schema = {
            "name": "section1",
            "fields": [
                {"name": "Notes", "type": AirtableFieldTypes.MULTI_LINE_TEXT, "description": "optional"},
                {"name": "Title", "type": AirtableFieldTypes.SINGLE_LINE_TEXT, "description": "optional"},
                {"name": "Units", "type": AirtableFieldTypes.SINGLE_SELECT, "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "(required)"},
                {"name": "Temperature", "type": AirtableFieldTypes.NUMBER, "options": {"precision": "1"}, "description": "(required)"},
                {"name": "Route", "type": AirtableFieldTypes.MULTI_SELECT, "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "(required)"},
                {"name": "Date", "type": AirtableFieldTypes.DATE, "description": "(required)"},
                {"name": "DateTime", "type": AirtableFieldTypes.DATE_TIME, "description": "(required)"},
            ]
        }
        section2_schema = {
            "name": "section2",
            "fields": [
                {"name": "Percent", "type": AirtableFieldTypes.PERCENT, "options": {"precision": "2"}, "description": "optional"},
                {"name": "Percent0", "type": AirtableFieldTypes.PERCENT, "options": {"precision": "0"}},
                {"name": "Percent00", "type": AirtableFieldTypes.PERCENT},
                {"name": "Checkbox", "type": AirtableFieldTypes.CHECKBOX, "description": "(required)"},
                {"name": "Currency", "type": AirtableFieldTypes.CURRENCY, "description": "(required)"}
            ]
        }


        expected_json_schema = {
                "title": "test_table",
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string", "const": "test_table", "description": "The name of the Airtable table"
                    },
                    "patient_name": {
                        "type": ["string", "null"], "description": "The name of the patient"
                    },
                    "sections": {
                        "type": "object",
                        "properties": {
                            "section1": {
                                "title": "section1",
                                "type": "object",
                                "properties": {
                                    "fields": {        
                                        "type": ["object", "null"],
                                        "properties": {
                                            "Notes": {
                                                "type": ["string", "null"], "description": "optional: Multi-line text"
                                            },
                                            "Title": {
                                                "type": ["string","null"], "description": "optional: Single line text"
                                            },
                                            "Units": {
                                                "type": ["string", "null"], "enum": ["Fahrenheit", "Celsius", None],
                                                "description": 
                                                "(required): Select one of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"
                                            },
                                            "Temperature": {
                                                "type": ["number", "null"],"description": "(required): Must be a number with 1 decimal precision"
                                            },
                                            "Route": {
                                                "type":["array", "null"], "items": { "type": ["string", "null"], "enum": ["Tympanic","Oral","Rectal","Axilla"]},
                                                "description": 
                                                "(required): Select one or more of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null"
                                            },
                                            "Date": {
                                                "type": ["string", "null"], "description": "(required): ISO 8601 date (YYYY-MM-DD)"
                                            },
                                            "DateTime": {
                                                "type": ["string", "null"], "description": "(required): ISO 8601 date-time (YYYY-MM-DDTHH:MM:SSZ)"
                                            }
                                        },
                                        "required": ["Notes", "Title", "Units", "Temperature","Route","Date","DateTime"],
                                        "additionalProperties": False
                                    },

                                },
                                "required": ["fields"],
                                "additionalProperties": False
                            },
                            "section2": {
                                "title": "section2",
                                "type": "object",
                                "properties": {
                                    "fields": {        
                                        "type": ["object", "null"],
                                        "properties": {
                                            "Percent": {
                                                "type": ["number", "null"],"description": "optional: Percentage - must be a number between 0 and 100 with 2 decimal precision"
                                            },
                                            "Percent0": {
                                                "type": ["number", "null"],"description": "Percentage - must be a number between 0 and 100 with 0 decimal precision"
                                            },
                                            "Percent00": {
                                                "type": ["number", "null"],"description": "Percentage - must be a number between 0 and 100 with 0 decimal precision"
                                            },
                                            "Checkbox": {
                                                "type": "boolean","description": "(required)"
                                            },
                                            "Currency": {
                                                "type": ["number", "null"],"description": "(required): Currency - must be a number with 0 decimal precision"
                                            }
                                        },
                                        "required": ["Percent", "Percent0", "Percent00", "Checkbox","Currency"],
                                        "additionalProperties": False
                                    },

                                },
                                "required": ["fields"],
                                "additionalProperties": False
                            }
                        },
                        "required": ["section1"],
                        "additionalProperties": False
                    },
                },
                "required": ["table_name","patient_name","sections"],
                "additionalProperties": False
            }

        schema = AirtableSchema("test_table", main_schema)
        schema.add_section(section_name="section1", section_schema=AirtableSchema("section1", section1_schema), required=True)
        schema.add_section(section_name="section2", section_schema=AirtableSchema("section2", section2_schema), required=False)
        json_schema = schema.get_json_schema()
        #print(json.dumps(json_schema, indent=4))
        self.assertTrue(json_schema)
        diff = DeepDiff(json_schema, expected_json_schema, ignore_order=True)
        self.assertEqual(diff, {}, diff)

if __name__ == '__main__':
    unittest.main()