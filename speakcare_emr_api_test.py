import sys
import json
import logging
from speakcare_emr_api import SpeakCareEmrApi

APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

def main(argv):    

    # Initialize logging
    logging.basicConfig()
    logger = logging.getLogger("speackcare.emr.api")
    logger.setLevel(logging.INFO)
    logger.propagate = True

    APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

    api = SpeakCareEmrApi(baseId=APP_BASE_ID, logger=logger)
    api.load_tables()
    api.load_patients()
    api.load_nurses()


    ### Patients ### 
    patients = {
        "Carol Smith": "rec4RsEGnKxO43ntl",
        "Alice Johnson": "recBmJYY6rB8Ufxjl",
        "Bob Williams": "recWya4qhPh1KZIor",
        "Eve Davis": "rechoUGdH6iLCpPDl",
        "John Doe": "recuGGwjlzPbDNFBW"
    }

    ### Nurses ###
    nurses = {
        "Audrey Hepburn":  "recQS1niZVmFu5Jmq",
        "Jessica Alba":    "recVmeNQcsWUkbB41",
        "Sara Foster":     "rechjFqtbZ35X8ayu", 
        "Rebecca Jones":   "reciAkTnOef0vLuCx",
        "Jannet Collines": "recmdxKo2PKcu64DQ"
    }


    temperatureRecord = {
        "Units": "Fahrenheit",
        "Temprature": 103,
        "Route": "Tympanic"
    }

    api.load_patients()
    api.load_nurses()
    patientName = 'Karol Smythe'
    matchedPatientName, patientId = api.lookup_patient(patientName)
    logger.info(f'Patient: {patientName} matched with {matchedPatientName} with id {patientId}')
   
    nurseName = 'Odrey Hapborn'
    matchedNurseName, nurseId = api.lookup_nurse(nurseName)
    logger.info(f'Nurse: {nurseName} matched with {matchedNurseName} with id {nurseId}')
   
    if not patientId or not nurseId:
        logger.error('Failed to find patient or nurse')
        return
    
    record, url = api.create_medical_record(tableName= SpeakCareEmrApi.TEMPERATURES_TABLE, record=temperatureRecord, 
                              patientId= patientId, createdByNurseId=nurseId)
    logger.info(f'Created temperature record: {record} url is {url}')
    logger.info(f'get_record_url returns {api.get_record_url(record["id"], tableName=SpeakCareEmrApi.TEMPERATURES_TABLE)}')

    return



    assementRecord = api.create_assessment(SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE, patientId= patientId, createdByNurseId=nurseId)
    logger.info(f'Created fall risk assessment: {assementRecord}')

    fallRiskSectionRecord = {
        "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "INTERMITTENT CONFUSION (4 points)",
        "HISTORY OF FALLS (Past 3 Months)": "1 - 2 FALLS in past 3 months (2 points)",
        "URINE ELIMINATION STATUS": "REGULARLY INCONTINENT (4 points)",
        "VISION STATUS": "POOR (with or without glasses) (2 points)",
        "GAIT/BALANCE/AMBULATION": [
          "Balance problem while standing/walking (1 point)",        
          "Change in gait pattern when walking (i.e. shuffling) (1 point)"
        ],
        "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
        "MEDICATIONS CHANGES": "Yes (1 additional point)",
        "PREDISPOSING DISEASES": "1 - 2 PRESENT (2 points)",
        "Total score": 19
    }
    
    nurseName = 'Rebeka Jones'
    matchedNurseName, nurseId = api.lookup_nurse(nurseName)
    logger.info(f'Updating Nurse: {nurseName} matched with {matchedNurseName} with id {nurseId}')
    if not patientId or not nurseId:
        logger.error('Failed to find patient or nurse')
        return
    
    assessSection1Record = api.create_assessment_section(SpeakCareEmrApi.FALL_RISK_SCREEN_SECTION_1_TABLE, record=fallRiskSectionRecord,
                                                         assessmentId= assementRecord['id'], createdByNurseId=nurseId)
    logger.info(f'Created fall risk assessment section: {assessSection1Record}')
        
    nurseName = 'Jessiqa Elba'
    matchedNurseName, nurseId = api.lookup_nurse(nurseName)
    logger.info(f'Signing Nurse: {nurseName} matched with {matchedNurseName} with id {nurseId}')
    assementRecord = api.sign_assessment(SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE, assessmentId= assementRecord['id'], signedByNurseId=nurseId)
    logger.info(f'Signed fall risk assessment: {assementRecord} url is {api.get_record_url(assementRecord["id"], tableName=SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE)}')







    # fallRiskWriteableFields = api.get_record_create_schema(tableName=SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE)
    # print(f'Fall Risk Screen Record Create Schema: {json.dumps(fallRiskWriteableFields, indent=4)}')

    # bloodPressuresTableSchema = api.get_table_schema(tableName=SpeakCareEmrApi.BLOOD_PRESSURES_TABLE)
    # bloodPressuresTableId = bloodPressuresTableSchema['id']
    # print(f'{SpeakCareEmrApi.BLOOD_PRESSURES_TABLE} Table schema: {json.dumps(bloodPressuresTableSchema, indent=4)}')
    # bloodPressuresTableSchema = api.get_table_schema(tableId=bloodPressuresTableId)
    # print(f'{SpeakCareEmrApi.BLOOD_PRESSURES_TABLE} Table schema: {json.dumps(bloodPressuresTableSchema, indent=4)}')

    # bloodPressuresTableWritableFields = api.get_table_writable_fields(tableId=bloodPressuresTableId)
    # print(f'{SpeakCareEmrApi.BLOOD_PRESSURES_TABLE} Table writable fields: {json.dumps(bloodPressuresTableWritableFields, indent=4)}')

    # fallsRiskScreenTableSchema = api.get_table_schema(tableName=SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE)
    # fallsRiskScreenTableId = fallsRiskScreenTableSchema['id']
    # print(f'{SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE} Table {fallsRiskScreenTableId} schema: {json.dumps(fallsRiskScreenTableSchema, indent=4)}')
    # fallsRiskTableWritableFields = api.get_table_writable_fields(tableId=fallsRiskScreenTableId)
    # print(f'{SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE} Table writable fields: {json.dumps(fallsRiskTableWritableFields, indent=4)}')

    # patientsWritableFields = api.get_record_create_schema(tableName=SpeakCareEmrApi.PATIENTS_TABLE)
    # print(f'{SpeakCareEmrApi.PATIENTS_TABLE} Record Create Schema: {json.dumps(patientsWritableFields, indent=4)}')

    # blablaWrtiableFields = api.get_record_create_schema(tableName='blabla')
    # print(f'blabla Record Create Schema: {json.dumps(blablaWrtiableFields, indent=4)}')

    # patientTableId = api.get_table_schema(tableName=SpeakCareEmrApi.PATIENTS_TABLE)['id']
    # print(f'Patient table id: {patientTableId}')
    # patientsWritableFields = api.get_record_create_schema(tableId=patientTableId)
    # print(f'{SpeakCareEmrApi.PATIENTS_TABLE} Record Create Schema: {json.dumps(patientsWritableFields, indent=4)}')


    #print(f'Tables type is {type(tables)})')
    #print(f'Tables (type={type(tables)}): {json.dumps(tables, indent=4)}')
    # weightRecord = WeightRecord(patientId='recWya4qhPh1KZIor', nurseId='recVmeNQcsWUkbB41',  weight=170)
    # print(f'Weight record: {weightRecord}')
    # print(f'Weight record JSON: {weightRecord.to_json()}')
    # weights = [weightRecord.to_dict()]
    # print(f'Weights: {weights}')
    #api.create_records(WeightRecord.WEIGHTS_TABLE_ID, weights)
    #record = api.create_record(WeightRecord.WEIGHTS_TABLE_ID, weightRecord.to_dict())
    #print(f'Created weight record: {record}')

    # weightRecords = [WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=170).to_dict(), 
    #                  WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=165).to_dict(),
    #                  WeightRecord(patientId='recuGGwjlzPbDNFBW', nurseId='rechjFqtbZ35X8ayu',  weight=175).to_dict()]
    
    # records = api.create_records_batch(WeightRecord.WEIGHTS_TABLE_ID, weightRecords)
    # print(f'Created weight records for patientId=recuGGwjlzPbDNFBW recrods: {records}')


   # progressNoteRecord = {
    #     "Notes": "Patient had temparture above 101, should be tested for Covid-19",
    #     "Type": "Infection",
    #     "Status": "Notify doctor"
    # }

    # record = api.create_medical_record(tableName= SpeakCareEmrApi.PROGRESS_NOTES_TABLE, record=progressNoteRecord,
    #                                    patientId= patients["Carol Smith"], createdByNurseId=nurses["Audrey Hepburn"])
    
    # print(f'Created progress note record: {record}')
    
if __name__ == "__main__":
    main(sys.argv[1:])