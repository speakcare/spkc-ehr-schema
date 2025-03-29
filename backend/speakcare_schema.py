from enum import Enum as PyEnum
from datetime import datetime
import logging
import copy
import json
from speakcare_logging import SpeakcareLogger
import traceback



# Logger setup
schema_logger = SpeakcareLogger(__name__)

class AirtableFieldTypes(PyEnum):
    NUMBER = 'number'
    SINGLE_LINE_TEXT = 'singleLineText'
    MULTI_LINE_TEXT = 'multilineText'
    SINGLE_SELECT = 'singleSelect'
    MULTI_SELECT = 'multipleSelects'
    DATE = 'date'
    DATE_TIME = 'dateTime'
    PERCENT = 'percent'
    CHECKBOX = 'checkbox'
    CURRENCY = 'currency'

class JsonSchemaTypes(PyEnum):
    STRING = 'string'
    NUMBER = 'number'
    ARRAY = 'array'
    BOOLEAN = 'boolean'
    OBJECT = 'object'
    NULL = 'null'


def precision_to_multiple_of(precision):
    """
    Converts a precision value to a multiple of value
    """
    precision = int(precision)
    return 10**-precision


"""
Field validation fucntion regsitry and schema creation registry
They are defined outside of the class as they need to be callable at import time and it is not possible to define
them as class static members, as the class itself is not yet fully defined at the time of the decorator call
"""

_field_validation_functions_registry = {}
_field_schema_function_registry = {}



class AirtableSchema:
    """
    A class to create a canonical SpeakCare JSON schema from an Airtable schema
    This adheres to the current OpenAI schema format with the existing restrictions.
    As the OpenAI JSON schema support imrpoves with time, we will be able to add more features to the schema and remove restrictions
    """

    """
    Registry staitc methods to register and get the field validation functions and field schema functions
    """
    @staticmethod
    def __register_validation_function(field_type):
        def decorator(func):
            _field_validation_functions_registry[field_type] = func
            return func
        return decorator
    
    @staticmethod
    def __get_validation_function(field_type):
        return _field_validation_functions_registry.get(field_type)

    @staticmethod
    def __register_field_type_schema(field_type):
        def decorator(func):
            _field_schema_function_registry[field_type] = func
            return func
        return decorator

    @staticmethod
    def __get_field_schema_function(field_type):
        return _field_schema_function_registry.get(field_type)


    def __init__(self, table_name, table_schema, is_person_table=False):
        if table_name != table_schema.get("name"):
            raise ValueError(f"Table name '{table_name}' does not match the name in the schema '{table_schema.get('name')}'")

        self.field_registry = {}
        self.sections = {}
        self.logger = schema_logger
        self.table_name = table_name
        self.json_schema = {}
        self.is_person_table = is_person_table
        self.__create_table_schema(table_schema)
        self.logger.debug(f"Created schema for table '{self.table_name}'.") 
        
    """
    Internal methods that are fired automatically when the class is instantiated to create the 
    schema for the specific record and register the field valdiation functions
    """           
    def __create_table_schema(self, table_schema):
        """
        Create a canonical schema from an Airtable schema
        """
        # Build the JSON schema 
        fields = table_schema.get("fields", None)
        self.logger.debug(f"Creating schema for table '{self.table_name}' with fields: {fields}")
        self.json_schema['title'] = self.table_name
        self.json_schema['type'] = JsonSchemaTypes.OBJECT.value
        # All schemas will have these properties: table_name, patient_name, fields
        self.json_schema['properties'] = { 
            "table_name": {
                "type": JsonSchemaTypes.STRING.value,
                "const": self.table_name,
                "description": "The name of the Airtable table"
            },
        }
        # self.json_schema['required'] = ["table_name", "patient_name"]
        self.json_schema['required'] = ["table_name"]
        
        # person records (patient, nurse, doctor, etc) don't have a person_name field as they are the person
        if not self.is_person_table:
            # regular record add person names here
            self.json_schema['properties']['patient_name'] = {
                "type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value],
                "description": "The name of the patient"
            }
            self.json_schema['required'].append('patient_name')
            # add here nurses when I am ready
            # self.json_schema['properties']['nurses_names'] = {
            #     "type": [JsonSchemaTypes.ARRAY.value, JsonSchemaTypes.NULL.value],
            #     "items": {"type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value]},
            #     "description": "Array of the names of all the nurses in the transcription that actively participated in the conversation" 
            # }
            # self.json_schema['required'].append('nurses_names')

            
        self.json_schema['additionalProperties'] = False
        # initialize the field registry
        if fields:
            self.json_schema['required'].append('fields')
            self.__create_field_registry(fields) 
        
    def add_section(self, section_name, section_schema: "AirtableSchema", required: bool = False):
        """
        Add a section to the schema
        """
        if not section_schema:
            return
        
        if not section_name == section_schema.table_name:
            raise ValueError(f"Table '{self.table_name}' failed to add section '{section_name}' as it is different than in the schema '{section_schema.table_name}'")
        
        if not self.json_schema['properties'].get('sections', None):
            # addin the first section
            self.json_schema['properties']['sections'] = {
                "type": JsonSchemaTypes.OBJECT.value,
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
            self.json_schema['required'].append('sections')

        self.sections[section_name] = section_schema
        section_json_schema = copy.deepcopy(section_schema.get_json_schema())
        if 'patient_name' in section_json_schema['properties']:
            # we don't need the patient_name in the section schema
            del section_json_schema['properties']['patient_name']
            section_json_schema['required'].remove('patient_name')

        if 'table_name' in section_json_schema['properties']:
            # we don't need the table_name in the section schema as we have it in the section name
            del section_json_schema['properties']['table_name']
            section_json_schema['required'].remove('table_name')
            
        self.json_schema['properties']['sections']['properties'][section_name] = section_json_schema
        if required:
            self.json_schema['properties']['sections']['required'].append(section_name)
        

    def get_section(self, section_name):
        return self.sections.get(section_name, None)    

    def __create_field_registry(self, fields=None):
        if not fields:
            return
        properties = {}
        required = []
        #fields = self.table_schema.get("fields", [])
        for i, field in enumerate(fields):
            field_name = field.get("name")
            field_type = AirtableFieldTypes(field.get("type"))  # if type is not in FieldTypes, it will raise an error
            prop_schema, err = self.__create_property_schema(field_type, field)
            if not prop_schema:
                error_message = f"Error creating schema for table '{self.table_name}' for field name '{field_name}' field {field}. error: {err}"
                self.logger.error(error_message)
                raise ValueError(error_message)
            
            properties[field_name] = prop_schema
            
            field_options = field.get("options", {})
            field_description = field.get("description", "")
            is_required = "required" in field_description.lower()
            # all fields must be set to required in json schema for OpenAI
            required.append(field_name) 
            self.field_registry[field_name] = {
                "type": field_type,
                "options": field_options,
                "required": is_required
            }
        
        schema_fields = {}
        schema_fields["type"] = [JsonSchemaTypes.OBJECT.value, JsonSchemaTypes.NULL.value]
        schema_fields["properties"] = properties
        schema_fields["required"] = required
        schema_fields["additionalProperties"] = False
        self.json_schema['properties']['fields'] = schema_fields



    def __validate_field(self, field_type: AirtableFieldTypes, value, options=None):
        """
        Takes a field name and a value and validates that it adheres to the schema
        """
        #global _field_validation_functions_registry 
        if value is None:
            error_message = "Field value is None"
            return None, error_message
            
        try:
            #validation_function = _field_validation_functions_registry.get(field_type)
            validation_function = self.__get_validation_function(field_type)
            if validation_function:
                return validation_function(self, value, options)
            else:
                error_message = f"No validation function found for field type '{field_type}' in table {self.table_name}."
                self.logger.error(error_message)
                return None, error_message
        except Exception as e:
            error_message = f"Validation function error: {e}"
            self.logger.error(error_message)
            return None, error_message

    def __create_property_schema(self, field_type: AirtableFieldTypes, airtable_schema: dict):
        field_schema_function = self.__get_field_schema_function(field_type)
        if field_schema_function:
            try:
                return field_schema_function(self, airtable_schema), ""
            except Exception as e:
                error_message = f"Field schema function error: {e}"
                self.logger.error(error_message)
                return None, error_message
        else:
            error_message = f"No schema function found for field type '{field_type}' in table {self.table_name}."
            self.logger.error(error_message)
            return None, error_message


    def __validate_record(self, record,  errors, checkRequired: bool=True):
        """
        Takes a record and validates that it adheres to this schema
        For record update validation, set checkRequired to False as we allow partial updates
        """
        
        validated_fields = {}
        all_valid = True
        try:
            # Check for required fields only if checkRequired is True
            if checkRequired:
                for field_name, field_info in self.field_registry.items():
                    if field_info.get("required") and field_name not in record:
                        error_message = f"Validation error: Required field '{field_name}' in table {self.table_name} is missing."
                        self.logger.error(error_message)
                        errors.append(error_message)
                        all_valid = False
            
            # Validate each field in the record
            if not record:
                error_message = f"Validation warning: Record for table {self.table_name} is empty."
                self.logger.warning(error_message)
                errors.append(error_message)
            else:
                for field_name, field_value in record.items():
                    if field_name in self.field_registry:
                        field_info = self.field_registry[field_name]
                        field_type = AirtableFieldTypes(field_info["type"])
                        field_options = field_info["options"]
                        validated_value, error_message = self.__validate_field(field_type, field_value, field_options)
                        if validated_value is not None:
                            validated_fields[field_name] = validated_value
                            if error_message:
                                error_message = f"Validation warning for field '{field_name}' in table {self.table_name}: {error_message}"
                                self.logger.warning(error_message)
                                errors.append(error_message)
                        elif field_info.get("required"):
                            error_message = f"Validation error for a required field '{field_name}' in table {self.table_name}: {error_message}"
                            self.logger.error(error_message)
                            errors.append(error_message)
                            all_valid = False
                        else:
                            error_message = f"Field is None or failed validation '{field_name}' in table {self.table_name}: {error_message}"
                            self.logger.debug(error_message)
                            errors.append(error_message)
                            
                    else:
                        error_message = f"Field name '{field_name}' does not exist in the schema of table {self.table_name}."
                        self.logger.error(error_message)
                        errors.append(error_message)
                        # Here we don't set is_valid to False as we can silently ignore fields that are not in the schema
            
            return all_valid, validated_fields
        except Exception as e:
            error_message = f"Validation error: {e}"
            self.logger.log_exception(self.logger, "Validation error", e)
            errors.append(error_message)
            return False, validated_fields


    """ 
    Field type schema functions 
    For each type provide a function that validates the field and a function that converts 
    from Airtable schema to the SpeakCare canonical JSON schema
    
    Add here any filed type that needs to be supported
    """


    ### Number field schema
    @__register_validation_function(AirtableFieldTypes.NUMBER)
    def __validate_number(self, value, options=None):
        """
        Validates a number field
        """
        try:
            if isinstance(value, (int, float)):
                return value, ""

            # Check if the value is a string that can be converted to a number
            if isinstance(value, str):
                try:
                    # Attempt to convert the string to a float
                    float_val = float(value)
                    return float_val, ""
                except ValueError:
                    raise ValueError(f"Value '{value}' cannot be converted to a number.")

            # Raise an exception for all other types
            raise ValueError(f"Invalid type for number field: {type(value)}")
        except Exception as e:
            self.logger.error(f"Number validation error: {e}")
            return None, str(e)
        
    @__register_field_type_schema(AirtableFieldTypes.NUMBER)
    def __number_schema(self, airtable_schema: dict):
        hint = f"Must be a number with {airtable_schema.get('options').get('precision')} decimal precision"
        description = f'{airtable_schema.get("description")}: {hint}' if airtable_schema.get("description") else hint
        return {
            "type": [JsonSchemaTypes.NUMBER.value, JsonSchemaTypes.NULL.value],
            "description": description
        }


    ### Single line text field schema
    @__register_validation_function(AirtableFieldTypes.SINGLE_LINE_TEXT)        
    def __validate_single_line_text(self, value, options=None):
        """
        Validates a single line text field
        """
        if isinstance(value, str) and '\n' not in value:
            return value, ""
        else:
            error_message = f"Single line text validation error: Value '{value}' is not a valid single line string."
            self.logger.error(error_message)
            return None, error_message
        
    @__register_field_type_schema(AirtableFieldTypes.SINGLE_LINE_TEXT)
    def __single_line_text_schema(self, airtable_schema: dict):
        return {
            "type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value],
            "description": "Single line text" if airtable_schema.get('description') is None else f"{airtable_schema.get('description')}: Single line text" 
        }


    ### Multi line text field schema
    @__register_validation_function(AirtableFieldTypes.MULTI_LINE_TEXT)
    def __validate_multi_line_text(self, value, options=None):
        """
        Validates a multi line text field
        """
        if isinstance(value, str):
            return value, ""
        else:
            error_message = f"Multi line text validation error: Value '{value}' is not a valid multi line string."
            self.logger.error(error_message)
            return None, error_message
        

    @__register_field_type_schema(AirtableFieldTypes.MULTI_LINE_TEXT)
    def __multi_line_text_schema(self, airtable_schema: dict):
        return {
            "type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value],
            "description": "Multi-line text" if airtable_schema.get('description') is None else f"{airtable_schema.get('description')}: Multi-line text" 
        }

    ### Single select field schema
    @__register_validation_function(AirtableFieldTypes.SINGLE_SELECT)
    def __validate_single_select(self, value, options=None):
        """
        Validates a single select field
        """
        if not isinstance(value, str) or options is None:
            error_message = f"Single select validation error: Value '{value}' is not a valid single select option."
            self.logger.error(error_message)
            return None, error_message
        for choice in options.get("choices", []):
            if choice.get("name") == value:
                return value, ""
        error_message = f"Single select validation error: Value '{value}' is not a valid choice."
        self.logger.error(error_message)
        return None, error_message
    
    @__register_field_type_schema(AirtableFieldTypes.SINGLE_SELECT)
    def __single_select_schema(self, airtable_schema: dict):
        hint = "Select one of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null" 
        enum_values = [choice["name"] for choice in airtable_schema.get("options", {}).get("choices", [])]
        enum_values.append(None)
        return {
            "type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value],
            "enum": enum_values,
            "description": f"{hint}" if airtable_schema.get('description') is None else f"{airtable_schema.get('description')}: {hint}",
        }

    ### Multi select field schema
    @__register_validation_function(AirtableFieldTypes.MULTI_SELECT)
    def __validate_multi_select(self, value, options=None):
        """
        Validates a multi select field
        """
        error_prefix = "Multi select validation errors:"
        error_message = None
        if not isinstance(value, list) or options is None:
            error_message = error_prefix + f" Argumment '{value}' is not a valid multi select list option."
            self.logger.error(error_message)
            return None, error_message
        allowed_choices = {choice.get("name") for choice in options.get("choices", [])}
        validated_values_list = []
        for item in value:
            if isinstance(item, str) and item in allowed_choices:
                validated_values_list.append(item)
            else: #if not isinstance(item, str) or item not in allowed_choices:
                err = f" Value '{item}' is not a valid choice."
                self.logger.warning(error_prefix + err)
                error_message = (error_message + err) if error_message else (error_prefix + err)
        if len(validated_values_list) == 0:
            err = " No valid choices found."
            error_message = (error_message + err) if error_message else (error_prefix + err)
            self.logger.info(error_message)
            return None, error_message
        return validated_values_list, error_message
    
    
    @__register_field_type_schema(AirtableFieldTypes.MULTI_SELECT)
    def __multi_select_schema(self, airtable_schema: dict):
        hint = "Select one or more of the valid enum options if and only if you are absolutely sure of the answer. If you are not sure, please select null" 
        enum_values = [choice["name"] for choice in airtable_schema.get("options", {}).get("choices", [])]
        return {
            "type": [JsonSchemaTypes.ARRAY.value, JsonSchemaTypes.NULL.value],
            "items": {"type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value], "enum": enum_values},
            "description": f"{hint}" if airtable_schema.get('description') is None else f"{airtable_schema.get('description')}: {hint}"
        }


    ### Date field schema
    @__register_validation_function(AirtableFieldTypes.DATE)
    def __validate_date(self, value, options=None):
        """
        Validates that the string is in ISO date format (YYYY-MM-DD)
        """
        if not isinstance(value, str):
            error_message = f"Date validation error: Value '{value}' is not a string."
            self.logger.error(error_message)
            return None, error_message
        try:
            datetime.fromisoformat(value)
            return value, ""
        except ValueError:
            error_message = f"Date validation error: Value '{value}' is not a valid ISO date."
            self.logger.error(error_message)
            return None, error_message

    @__register_field_type_schema(AirtableFieldTypes.DATE)
    def __date_schema(self, airtable_schema: dict):
        format = "ISO 8601 date (YYYY-MM-DD)"
        return {
            "type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value],
            "description": format if airtable_schema.get('description') is None else f"{airtable_schema.get('description')}: {format}"
        }

    ### Date-time field schema
    @__register_validation_function(AirtableFieldTypes.DATE_TIME)
    def __validate_date_time(self, value, options=None):
        """
        Validates a date_time field
        """
        if not isinstance(value, str):
            error_message = f"Date-time validation error: Value '{value}' is not a string."
            self.logger.error(error_message)
            return None, error_message

        # Replace 'Z' with '+00:00' to use datetime.fromisoformat
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'

        try:
            # Attempt to parse the string with datetime.fromisoformat()
            datetime.fromisoformat(value)
            return value, ""
        except ValueError:
            error_message = f"Date-time validation error: Value '{value}' is not a valid ISO date-time."
            self.logger.error(error_message)
            return None, error_message    
        
    @__register_field_type_schema(AirtableFieldTypes.DATE_TIME)
    def __date_time_schema(self, airtable_schema: dict):
        format = "ISO 8601 date-time (YYYY-MM-DDTHH:MM:SSZ)"
        return {
            "type": [JsonSchemaTypes.STRING.value, JsonSchemaTypes.NULL.value],
            "description": format if airtable_schema.get('description') is None else f"{airtable_schema.get('description')}: {format}"
        }
        
    ### Percent field schema
    @__register_validation_function(AirtableFieldTypes.PERCENT)
    def __validate_percent(self, value, options=None):
        """
        Validates that the value is a percentage (0 to 100 inclusive).
        The value can be a string that represents a number.
        """

        if isinstance(value, str):
            try:
                # convert the string to a float
                value = float(value)
            except ValueError:
                error_message = f"Percent validation error: Value '{value}' cannot be converted to a percent."
                self.logger.error(error_message)
                return False, error_message
        if isinstance(value, (int, float)) and 0 <= value <= 100:
            decimal = value / 100
            return decimal, ""
        else:
            error_message = f"Percent validation error: Value '{value}' is not a valid percent (0-100)."
            self.logger.error(error_message)
            return None, error_message
        
    @__register_field_type_schema(AirtableFieldTypes.PERCENT)
    def __percent_schema(self, airtable_schema: dict):
        hint = f"Percentage - must be a number between 0 and 100 with {airtable_schema.get('options', {}).get('precision', 0)} decimal precision"
        description = f'{airtable_schema.get("description")}: {hint}' if airtable_schema.get("description") else hint
        return {
            "type": [JsonSchemaTypes.NUMBER.value, JsonSchemaTypes.NULL.value],
            "description": description
        }    
    ### Checkbox field schema
    @__register_validation_function(AirtableFieldTypes.CHECKBOX)
    def __validate_checkbox(self, value, options=None):
        """
        Validates that the value is a boolean.
        """
        if isinstance(value, bool):
            return value, ""
        else:
            error_message = f"Checkbox validation error: Value '{value}' is not a valid boolean for checkbox."
            self.logger.error(error_message)
            return None, error_message
        
    @__register_field_type_schema(AirtableFieldTypes.CHECKBOX)
    def __checkbox_schema(self, airtable_schema: dict):
        return {
            "type": JsonSchemaTypes.BOOLEAN.value,
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }

    @__register_validation_function(AirtableFieldTypes.CURRENCY)
    def __validate_currency(self, value, options=None):
        """
        Validates that the value is a number or a string convertible to a number.
        """
        if isinstance(value, (int, float)):
            return True, ""
        elif isinstance(value, str):
            try:
                float(value)
                return value, ""
            except ValueError:
                error_message = f"Currency validation error: Value '{value}' cannot be converted to a float."
                self.logger.error(error_message)
                return None, error_message
        else:
            error_message = f"Currency validation error: Invalid type for currency field: {type(value)}"
            self.logger.error(error_message)
            return None, error_message
        

    ### Currency field schema
    @__register_field_type_schema(AirtableFieldTypes.CURRENCY)
    def __currency_schema(self, airtable_schema: dict):
        hint = f"Currency - must be a number with {airtable_schema.get('options', {}).get('precision', 0)} decimal precision"
        description = f'{airtable_schema.get("description")}: {hint}' if airtable_schema.get("description") else hint
        return {
            "type": [JsonSchemaTypes.NUMBER.value, JsonSchemaTypes.NULL.value],
            "description": description
        }   


    """ 
    Class external interfacce for the calling code
    """
    def get_json_schema(self):
        return self.json_schema
    
    def get_name(self):
        return self.table_name
        
    def validate_record(self, record,  errors, checkRequired: bool=True):
        """
        Validates the record and enforce required fields
        """
        return self.__validate_record(record, errors, checkRequired)
       
    def validate_partial_record(self, record, errors):
        """
        Validates a partial record update, do not enforce required fields
        """
        return self.__validate_record(record, errors=errors, checkRequired=False)
