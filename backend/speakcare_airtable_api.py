import os, sys

from dotenv.main import logger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pyairtable import Api as AirtableApi
import json
import logging
import requests
from speakcare_schema import AirtableSchema
import copy
from typing import Dict
from backend.speakcare_env import SpeakcareEnv

# Load the .env file
SpeakcareEnv.load_env()
AIRTABLE_APP_BASE_ID = os.getenv('AIRTABLE_APP_BASE_ID')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')

class SpeakCareAirtableApi():


    METADATA_BASE_URL = 'https://api.airtable.com/v0/meta/bases'
    API_BASE_URL = 'https://api.airtable.com/v0'
    WEB_APP_BASE_URL = 'https://airtable.com'

    def __init__(self,config, logger: logging.Logger):
        self.apiKey = AIRTABLE_API_KEY
        self.api = AirtableApi(self.apiKey)
        self.appBaseId = config.get('baseId')
        self.logger = logger
        self.tablesSchemaUrl = f'{self.METADATA_BASE_URL}/{self.appBaseId}/tables'
        self.apiBaseUrl = f'{self.API_BASE_URL}/{self.appBaseId}/'
        self.webBaseUrl = f'{self.WEB_APP_BASE_URL}/{self.appBaseId}/'
        self.tables = {}

    def retreive_all_tables_schema(self):
        authHeader = f'Bearer {self.apiKey}'
        _headers = {
                    'Authorization': authHeader
                }
        response = self._api_get(self.tablesSchemaUrl, headers=_headers)
        data = response.json()  # Convert the JSON response to a dictionary
        tables = data.get("tables", []) 
        self.logger.debug(f"Retrieved {len(tables)} tables")
        self.logger.debug(f"Tables: {json.dumps(tables, indent=2)}")
        return tables

    def load_table(self, tableId):
        self.tables[tableId] = self.api.table(self.appBaseId, tableId)

    def create_table(self, table:dict):
        authHeader = f'Bearer {self.apiKey}'
        _headers = {
                    'Authorization': authHeader,
                    'Content-Type': 'application/json'
                }
        response = self._api_post(baseUrl= self.tablesSchemaUrl, dictBody=table, headers=_headers)
        return response.json()

    # def get_table(self, table):
    #     return self.api.table(self.appBaseId, table)

    def get_table_records(self, tableId):
        if tableId not in self.tables:
            self.logger.error(f'get_table_records: table {tableId} not loaded')
            return None
        return self.tables[tableId].all()

    def create_record(self, tableId, record):
        record = self.api.table(self.appBaseId, tableId).create(record)
        if record:
            url = f'{self.webBaseUrl}{tableId}/{record["id"]}'
            return record, url
        else:
            self.logger.error(f'Failed to create record {record} in table {tableId}')
            return None, None
    
    def update_record(self, tableId, recordId, record):
        if tableId not in self.tables:
            self.logger.debug(f'update_record: updating record {recordId} in a non-loaded table {tableId}')
            return self.api.table(self.appBaseId, tableId).get(recordId)
        return self.api.table(self.appBaseId, tableId).update(record_id=recordId, fields=record)

    def get_record(self, tableId, recordId):
        if tableId not in self.tables:
            self.logger.debug(f'get_record: getting record {recordId} from a non-loaded table {tableId}')
            return self.api.table(self.appBaseId, tableId).get(recordId)
        else:
            return self.tables[tableId].get(recordId)

    def delete_record(self, tableId, recordId):
        if tableId not in self.tables:
            self.logger.debug(f'delete_record: deleting record {recordId} from a non-loaded table {tableId}')
            return self.api.table(self.appBaseId, tableId).get(recordId)
        return self.tables[tableId].delete(recordId)

    def get_table_url(self, tableId=None, tableName=None):
        if tableId:
            _tableId = tableId
        elif tableName:
            _tableId = self.get_table_id(tableName)
        else:
            return None
        
        return f'{self.webBaseUrl}{_tableId}'
    
    def get_record_url(self, recordId, tableId=None, tableName=None):
        if tableId:
            _tableId = tableId
        elif tableName:
            _tableId = self.get_table_id(tableName)
        else:
            return None
        return f'{self.webBaseUrl}{_tableId}/{recordId}'        
    
    def _api_post(self, baseUrl=None, body=None, dictBody=None, tableId="", params=None, headers=None):

        url = os.path.join(baseUrl, tableId) if tableId else baseUrl
        self.logger.debug(f'API: Sending POST to endpoint \"{url}\" with:\n headers {headers} body: {body} dictBody: {dictBody} uriParams {params}')
        response = requests.post(url, data=body, json=dictBody, params=params, headers=headers)#, cert=self.cert)
        
        if (response.status_code != 200):
            self.logger.error(f'API: POST to tableId \"{tableId}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response
        
    def _api_get(self, baseUrl=None, body=None, tableId="", params=None, headers=None):

        url = os.path.join(baseUrl, tableId) if tableId else baseUrl
        self.logger.debug(f'API: Sending GET to endpoint \"{url}\" with:\n headers {headers} body: {body} uriParams {params}')
        
        response = requests.get(url, data=body, params=params, headers=headers)
        
        
        if (response.status_code != 200):
            self.logger.error(f'API: GET to endpoint \"{url}\" with payload {body} returned status code {response.status_code} response: {response.text}')

        return response
