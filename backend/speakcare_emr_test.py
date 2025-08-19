import sys
import json
import logging
from speakcare_emr import SpeakCareEmr, get_emr_api_instance
from speakcare_logging import SpeakcareLogger
from config import SpeakCareEmrApiconfig

APP_BASE_ID = 'appRFbM7KJ2QwCDb6'



def test_temperatue_record_creation(api: SpeakCareEmr, logger: logging.Logger, patientName: str = 'Karol Smythe', nurseName: str = 'Odrey Hapborn'):
    temperatureRecord = {
        "Units": "Fahrenheit",
        "Temprature": 103,
        "Route": "Tympanic"
    }

    matchedPatientName, patientId, patientEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_patient(patientName)
    logger.info(f'Patient: {patientName} matched with {matchedPatientName} with id {patientId}, emrId {patientEmrId}')
    patient = get_emr_api_instance(SpeakCareEmrApiconfig).get_patient_by_emr_id(patientEmrId)
    logger.info(f'Patient: {json.dumps(patient, indent=4)}')
   
    
    matchedNurseName, nurseId, nurseEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_nurse(nurseName)
    logger.info(f'Nurse: {nurseName} matched with {matchedNurseName} with id {nurseId}, emrId {nurseEmrId}')
   
    if not patientId or not nurseId:
        logger.error('Failed to find patient or nurse')
        return None
    


    record, url, err = get_emr_api_instance(SpeakCareEmrApiconfig).create_simple_record(tableName= SpeakCareEmr.TEMPERATURES_TABLE, record=temperatureRecord, 
                                            patientEmrId=patientEmrId, createdByNurseEmrId=nurseEmrId)
    if not record:
        logger.error(f'Failed to create temperature record: {temperatureRecord} error: {err}')
        return None
    
    logger.info(f'Created temperature record: {record} url is {url}')
    logger.info(f'get_record_url returns {get_emr_api_instance(SpeakCareEmrApiconfig).get_record_url(record["id"], tableName=SpeakCareEmr.TEMPERATURES_TABLE)}')
    return record

def test_progress_note_creation(api: SpeakCareEmr, logger: logging.Logger, patientName: str = 'Karol Smythe', nurseName: str = 'Odrey Hapborn'):

    progressNoteRecord = {
        "Notes": "Patient had temparture above 101, should be tested for Covid-19",
        "Type": "Infection",
        "Status": "Notify doctor"
    }
    matchedPatientName, patientId, patientEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_patient(patientName)
    logger.info(f'Patient: {patientName} matched with {matchedPatientName} with id {patientId}, emrId {patientEmrId}')
    patient = get_emr_api_instance(SpeakCareEmrApiconfig).get_patient_by_emr_id(patientEmrId)
    logger.info(f'Patient: {json.dumps(patient, indent=4)}')
   
    
    matchedNurseName, nurseId, nurseEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_nurse(nurseName)
    logger.info(f'Nurse: {nurseName} matched with {matchedNurseName} with id {nurseId}, emrId {nurseEmrId}')
   
    if not patientId or not nurseId:
        logger.error('Failed to find patient or nurse')
        return None

    
    record, url, err = get_emr_api_instance(SpeakCareEmrApiconfig).create_simple_record(tableName= SpeakCareEmr.PROGRESS_NOTES_TABLE, record=progressNoteRecord, 
                                            patientEmrId=patientEmrId, createdByNurseEmrId=nurseEmrId)
    
    if not record:
        logger.error(f'Failed to create progress notes record: {progressNoteRecord} error: {err}')
        return None
    
    logger.info(f'Created progress notes record: {record} url is {url}')
    logger.info(f'get_record_url returns {get_emr_api_instance(SpeakCareEmrApiconfig).get_record_url(record["id"], tableName=SpeakCareEmr.TEMPERATURES_TABLE)}')
    return record

def test_falls_risk_creation(api: SpeakCareEmr, logger: logging.Logger, 
                             patientName: str = 'Karol Smythe', 
                             creatingNurseName: str = 'Odrey Hapborn',
                             updatingNurseName: str = 'Jessiqa Elba',
                             signingNurseName: str = 'Rebeka Jones'):


    matchedPatientName, patientId, patientEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_patient(patientName)
    logger.info(f'Patient: {patientName} matched with {matchedPatientName} with id {patientId}, emrId {patientEmrId}')
    patient = get_emr_api_instance(SpeakCareEmrApiconfig).get_patient_by_emr_id(patientEmrId)
    logger.info(f'Patient: {json.dumps(patient, indent=4)}')
   
    
    matchedNurseName, nurseId, nurseEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_nurse(creatingNurseName)
    logger.info(f'Nurse: {creatingNurseName} matched with {matchedNurseName} with id {nurseId}, emrId {nurseEmrId}')
   
    if not patientId or not nurseId:
        logger.error('Failed to find patient or nurse')
        return None
    
    # Try firs with wrong status name
    fallRiskRecord = {
        "Status": "Old"
    }
    # This should fail
    assementRecord, url, err = get_emr_api_instance(SpeakCareEmrApiconfig).create_multi_section_record(SpeakCareEmr.FALL_RISK_SCREEN_TABLE, fallRiskRecord, patientEmrId=patientEmrId, createdByNurseEmrId=nurseEmrId)
    if not assementRecord:
        logger.error(f'Correctly failed to create fall risk assessment {fallRiskRecord} error: {err}')

    # now set correct status name
    fallRiskRecord["Status"] = "New"
    assementRecord, url, err = get_emr_api_instance(SpeakCareEmrApiconfig).create_multi_section_record(SpeakCareEmr.FALL_RISK_SCREEN_TABLE, fallRiskRecord, patientEmrId=patientEmrId, createdByNurseEmrId=nurseEmrId)
    if not assementRecord:
        logger.error(f'Wrongly failed to create fall risk assessment {fallRiskRecord} error: {err}')
        return None
    
    logger.info(f'Created fall risk assessment: {assementRecord} url is {url}')

    matchedNurseName, nurseId, nurseEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_nurse(updatingNurseName)
    logger.info(f'Updating Nurse: {updatingNurseName} matched with {matchedNurseName} with id {nurseId}, emrId {nurseEmrId}')
    if not patientId or not nurseId:
        logger.error('Failed to find patient or nurse')
        return None
    
    fallRiskSectionRecord = {
        "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS": "INTERMITTENT CONFUSION (4 points)",
        "HISTORY OF FALLS (Past 3 Months)": "1 - 2 FALLS in past 3 months (2 points)",
        "URINE ELIMINATION STATUS": "REGULARLY INCONTINENT (4 points)",
        "VISION STATUS": "PUR (with or without glasses) (2 points)",
        "GAIT/BALANCE/AMBULATION": [
          "Balance problem while standing/walking (1 point)",        
          "Change in gait pattern when walking (i.e. shuffling) (1 point)"
        ],
        "MEDICATIONS": "NONE of these medications taken currently or within last 7 days (0 points)",
        "MEDICATIONS CHANGES": "Yes (1 additional point)",
        "PREDISPOSING DISEASES": "1 - 2 PRESENT (2 points)",
        "Total score": 19
    }
    assessSection1Record, url, err = get_emr_api_instance(SpeakCareEmrApiconfig).create_record_section(SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE, record=fallRiskSectionRecord,
                                                                   patientEmrId=patientEmrId, assessmentId= assementRecord['id'], createdByNurseEmrId= nurseEmrId)
    if not assessSection1Record:
        logger.error(f'Correctly failed to create fall risk section {SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE} data {fallRiskRecord} error: {err}')

    # fix the error
    fallRiskSectionRecord['VISION STATUS'] = "POOR (with or without glasses) (2 points)"
    assessSection1Record, url, err = get_emr_api_instance(SpeakCareEmrApiconfig).create_record_section(SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE, record=fallRiskSectionRecord,
                                                                   patientEmrId=patientEmrId, assessmentId= assementRecord['id'], createdByNurseEmrId= nurseEmrId)
    
    if not assessSection1Record:
        logger.error(f'Wrongly failed to create fall risk section {SpeakCareEmr.FALL_RISK_SCREEN_SECTION_1_TABLE} data {fallRiskRecord} error: {err}')
        return None
    
    logger.info(f'Created fall risk assessment section: {assessSection1Record}')
        

    matchedNurseName, nurseId, nurseEmrId = get_emr_api_instance(SpeakCareEmrApiconfig).match_nurse(signingNurseName)
    logger.info(f'Signing Nurse: {signingNurseName} matched with {matchedNurseName} with id {nurseId}')
    assementRecord, err = get_emr_api_instance(SpeakCareEmrApiconfig).sign_assessment(SpeakCareEmr.FALL_RISK_SCREEN_TABLE, assessmentId= assementRecord['id'], signedByNurseEmrId =nurseEmrId)
    if not assementRecord:
        logger.error(f'Failed to sign fall risk assessment: {assementRecord} error: {err}')
        return None
    logger.info(f'Signed fall risk assessment: {assementRecord} url is {get_emr_api_instance(SpeakCareEmrApiconfig).get_record_url(assementRecord["id"], tableName=SpeakCareEmr.FALL_RISK_SCREEN_TABLE)}')

    return assementRecord

def test_get_single_table_schema(api: SpeakCareEmr, logger: logging.Logger, tableName):
    tableSchema = get_emr_api_instance(SpeakCareEmrApiconfig).get_table_json_schema(tableName=tableName)
    logger.info(f'{tableName} Table schema: {json.dumps(tableSchema, indent=4)}')
    return

def test_get_tables_schemas(api: SpeakCareEmr, logger: logging.Logger, tableName: str = None):

    tableNames = get_emr_api_instance(SpeakCareEmrApiconfig).get_emr_table_names()
    logger.info(f'Table names: {tableNames}')

    if tableName and tableName in tableNames:
        logger.info(f'Getting schema for table {tableName}')
        test_get_single_table_schema(api, logger, tableName)
        return
    elif tableName and tableName not in tableNames:
        logger.error(f'Table {tableName} not found')
        return
    else: # get schema for all tables
        logger.info(f'Getting schema for all tables')
        for _tableName in tableNames:
            test_get_single_table_schema(api, logger, _tableName)
        
    return

    ### Patients ### 
# patients = {
#         "Carol Smith": "rec4RsEGnKxO43ntl",
#         "Alice Johnson": "recBmJYY6rB8Ufxjl",
#         "Bob Williams": "recWya4qhPh1KZIor",
#         "Eve Davis": "rechoUGdH6iLCpPDl",
#         "John Doe": "recuGGwjlzPbDNFBW"
#     }

#     ### Nurses ###
# nurses = {
#         "Audrey Hepburn":  "recQS1niZVmFu5Jmq",
#         "Jessica Alba":    "recVmeNQcsWUkbB41",
#         "Sara Foster":     "rechjFqtbZ35X8ayu", 
#         "Rebecca Jones":   "reciAkTnOef0vLuCx",
#         "Jannet Collines": "recmdxKo2PKcu64DQ"
#     }
def main(argv):    

    # Initialize logging
    testLogger = SpeakcareLogger('api_test')

    api = get_emr_api_instance(SpeakCareEmrApiconfig)
    if not api:
        testLogger.error('Failed to initialize EMR API')
        raise Exception('Failed to initialize EMR API')

    test_temperatue_record_creation(api, testLogger, patientName='Bob Wiliams')
    test_falls_risk_creation(api, testLogger, patientName='Jon Do')
    test_progress_note_creation(api, testLogger, patientName='Eve Davise', nurseName='Janet Kollines')

    # test_get_tables_schemas(api, testLogger, SpeakCareEmrApi.TEMPERATURES_TABLE)
    # test_get_tables_schemas(api, testLogger, SpeakCareEmrApi.PROGRESS_NOTES_TABLE)
    # test_get_tables_schemas(api, testLogger, SpeakCareEmrApi.FALL_RISK_SCREEN_TABLE)
    # test_get_tables_schemas(api, testLogger, SpeakCareEmrApi.ADMISSION_ASSESSMENTS_TABLE)
    # test_get_tables_schemas(api, testLogger, tableName=SpeakCareEmrApi.EPISODES_TABLE)
    # test_get_tables_schemas(api, testLogger, tableName=SpeakCareEmrApi.PROGRESS_NOTES_TABLE)
    # test_get_tables_schemas(api, testLogger, tableName=SpeakCareEmrApi.PROGRESS_NOTES_TABLE, writeableOnly=False)
    # test_get_tables_schemas(api, testLogger, tableName=SpeakCareEmr.WEIGHTS_TABLE)
    # test_get_single_table_schema(api, testLogger, tableName=SpeakCareEmrApi.PATIENTS_TABLE, writeableOnly=False)


if __name__ == "__main__":
    main(sys.argv[1:])