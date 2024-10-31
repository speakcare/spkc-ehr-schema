import unittest
from datetime import datetime
#from airtable_schema import AirtableSchema, FieldTypes
from speakcare_airtable_schema import AirtableSchema, AirtableFieldTypes
import json
import copy
from deepdiff import DeepDiff


class TestValidations(unittest.TestCase):

    def setUp(self):
        self.valid_temperature_schema = {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleSelect', "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "required"},
                {"name": "Temperature", "type": 'number', "options": {"precision": "1"}, "description": "required"},
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
        self.assertTrue("Validation error for field 'Temperature': Value 'high' cannot be converted to a number." in errors[0], errors[0])
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
        self.assertTrue("Validation error for field 'Temperature': Value 'high' cannot be converted to a number." in errors[0], errors[0])
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
        self.assertEqual(errors[0], "Validation error: Required field 'Units' is missing.")

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
        self.assertTrue("Validation warning for field 'Route': Multi select validation errors: Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        # check the route includes only valid values
        self.assertEqual(valid_fields["Route"], ["Tympanic", "Axilla", "Rectal"])

    def test_validate_multi_select_incorrect_required_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "required"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Axilla", "Forehead", "Rectal"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Validation warning for field 'Route': Multi select validation errors: Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertEqual(valid_fields["Route"], ["Tympanic", "Axilla", "Rectal"])

    def test_validate_multi_select_incorrect_multiple_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "required"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Ear", "Axilla", "Forehead", "Rectal", "Mouth"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertTrue(is_valid)
        self.assertTrue("Validation warning for field 'Route': Multi select validation errors:" in errors[0], errors[0])
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
        self.assertTrue("Validation error for field 'Route': Multi select validation errors:" in errors[0], errors[0])
        self.assertTrue("Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Ear' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Mouth' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(valid_fields.get("Route", None))

    def test_validate_multi_select_no_valid_required_values(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "required"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Ear", "Forehead", "Mouth"]
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for field 'Route': Multi select validation errors:" in errors[0], errors[0])
        self.assertTrue("Value 'Forehead' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Ear' is not a valid choice." in errors[0], errors[0])
        self.assertTrue("Value 'Mouth' is not a valid choice." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(valid_fields.get("Route", None))
        

    def test_validate_multi_select_not_a_list_required(self):
        table_schema = copy.deepcopy(self.valid_temperature_schema)
        table_schema["fields"][2] = {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "required"}
        schema = AirtableSchema("temperatureRecord", table_schema)
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": "Tympanic"
        }
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for field 'Route': Multi select validation errors:" in errors[0], errors[0])
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
                {"name": "DateField", "type": "date", "description": "required"}
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
        self.assertTrue("Validation error for field 'PercentField': Percent validation error: Value '150' is not a valid percent (0-100)." in errors[0], errors[0])
        self.assertEqual(len(errors), 1)
        
    def test_validate_percent_incorrect_required_value(self):
        schema = AirtableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "PercentField", "type": "percent", "options": {"precision": "1"}, "description": "required"}
            ]
        })
        record = {"PercentField": 150}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Validation error for field 'PercentField': Percent validation error: Value '150' is not a valid percent (0-100)." in errors[0], errors[0])
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
                {"name": "CheckboxField", "type": "checkbox", "description": "required"}
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
                {"name": "CurrencyField", "type": "currency", "description": "required"}
            ]
        })
        record = {"CurrencyField": "one hundred"}
        errors = []
        is_valid, valid_fields = schema.validate_record(record=record, errors=errors)
        self.assertFalse(is_valid)
        self.assertTrue("Currency validation error: Value 'one hundred' cannot be converted to a float." in errors[0], errors[0])        


class TestJsonSchema(unittest.TestCase):

    def test_valid_json_schema(self):
        airtable_schema = {
            "name": "test_table",
            "fields": [
                {"name": "Notes", "type": AirtableFieldTypes.MULTI_LINE_TEXT, "description": "optional"},
                {"name": "Title", "type": AirtableFieldTypes.SINGLE_LINE_TEXT, "description": "optional"},
                {"name": "Units", "type": AirtableFieldTypes.SINGLE_SELECT, "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "required"},
                {"name": "Temperature", "type": AirtableFieldTypes.NUMBER, "options": {"precision": "1"}, "description": "required"},
                {"name": "Route", "type": AirtableFieldTypes.MULTI_SELECT, "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}, "description": "required"},
                {"name": "Date", "type": AirtableFieldTypes.DATE, "description": "required"},
                {"name": "DateTime", "type": AirtableFieldTypes.DATE_TIME, "description": "required"},
                {"name": "Percent", "type": AirtableFieldTypes.PERCENT, "options": {"precision": "2"}, "description": "required"},
                {"name": "Percent0", "type": AirtableFieldTypes.PERCENT, "options": {"precision": "0"}},
                {"name": "Percent00", "type": AirtableFieldTypes.PERCENT},
                {"name": "Checkbox", "type": AirtableFieldTypes.CHECKBOX, "description": "required"},
                {"name": "Currency", "type": AirtableFieldTypes.CURRENCY, "description": "required"}
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
                        "type": "string", "description": "The name of the patient"
                    },
                    "fields": {
                        "type": "object",
                        "properties": {
                            "Notes": {
                                "type": "string", "description": "Multi-line text: optional"
                            },
                            "Title": {
                                "type": "string", "description": "Single line text: optional"
                            },
                            "Units": {
                                "type": "string", "enum": ["Fahrenheit", "Celsius"],"description": "required"
                            },
                            "Temperature": {
                                "type": "number","multipleOf": 0.1, "description": "required"
                            },
                            "Route": {
                                "type": "array", "items": { "type": "string", "enum": ["Tympanic","Oral","Rectal","Axilla"]},"description": "required"
                            },
                            "Date": {
                                "type": "string","format": "date","description": "ISO 8601 date (YYYY-MM-DD): required"
                            },
                            "DateTime": {
                                "type": "string","format": "date-time","description": "ISO 8601 date-time (YYYY-MM-DDTHH:MM:SSZ): required"
                            },
                            "Percent": {
                                "type": "number", "multipleOf": 0.01, "minimum": 0,"maximum": 100,"description": "Percentage (0-100): required"
                            },
                            "Percent0": {
                                "type": "number","multipleOf": 1,"minimum": 0,"maximum": 100, "description": "Percentage (0-100)"
                            },
                            "Percent00": {
                                "type": "number","multipleOf": 1,"minimum": 0,"maximum": 100, "description": "Percentage (0-100)"
                            },
                            "Checkbox": {
                                "type": "boolean","description": "required"
                            },
                            "Currency": {
                                "type": "number","multipleOf": 1,"description": "Currency: required"
                            }
                        },
                        "required": ["Units", "Temperature","Route","Date","DateTime","Percent","Checkbox","Currency"],
                        "additionalProperties": False
                    },
                    "required": ["table_name","patient_name","fields"],
                    "additionalProperties": False
                }
            }

        schema = AirtableSchema("test_table", airtable_schema)
        json_schema = schema.get_json_schema()
        self.assertTrue(json_schema)
        diff = DeepDiff(json_schema, expected_json_schema, ignore_order=True)
        self.assertEqual(diff, {}, diff)

if __name__ == '__main__':
    unittest.main()