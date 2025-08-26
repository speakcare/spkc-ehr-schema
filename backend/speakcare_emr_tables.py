import os, sys

from dotenv.main import logger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.speakcare_env import SpeakcareEnv

SpeakcareEnv.load_env()


class SpeakCareEmrTables:

    @classmethod
    def is_test_env(cls):
        return len(cls.get_person_table_prefix()) > 0

    @classmethod
    def is_test_table_rewrite_required(cls):
        return os.getenv('PERSON_TEST_TABLE_REWRITE', 'false').lower() == 'true'
    
    @classmethod
    def get_person_table_prefix(cls):
        return os.getenv('PERSON_TEST_TABLE_PREFIX', 'Test')
    
    # Table names
    
    """
      The followoing are table names as they appear in the Airtable database 
      Every table that should be accessed by the API should be added here
      The table names should be exactly as they appear in the Airtable database
      #TODO: load tables dynamically from the API
    """
    ### People ###
    def PATIENTS_TABLE(self): 
        return f'{self.get_person_table_prefix()}_Patients' if self.get_person_table_prefix() else 'Patients'
    def NURSES_TABLE(self):
        return f'{self.get_person_table_prefix()}_Nurses' if self.get_person_table_prefix() else 'Nurses'

    DOCTORS_TABLE = 'Doctors'
    
    ### Medical Records ###
    VITALS_TABLE = 'Vitals'
    def TEST_WEIGHTS_TABLE(self):
        return f'{self.get_person_table_prefix()}_Weights' if self.get_person_table_prefix() else 'Weights'

    def TEST_BLOOD_PRESSURES_TABLE(self):
        return f'{self.get_person_table_prefix()}_Blood Pressures' if self.get_person_table_prefix() else 'Blood Pressures'
        
    BLOOD_PRESSURES_TABLE = 'Blood Pressures'
    WEIGHTS_TABLE = 'Weights'
    BLOOD_SUGARS_TABLE = 'Blood Sugars'
    HEIGHTS_TABLE = 'Heights'
    TEMPERATURES_TABLE = 'Temperatures'
    O2_SATURATIONS_TABLE = 'O2 Saturations'
    PULSES_TABLE = 'Pulses'
    RESPIRATION_TABLE = 'Respiration'
    EPISODES_TABLE = 'Episodes'
    PROGRESS_NOTES_TABLE = 'Progress Notes'
    
    ### Assessments ###
    # Admission
    ADMISSION_TABLE = 'Admission'
    ADMISSION_SECTION_1_DEMOGRAPHCS_TABLE   = 'Admission: SECTION 1. DEMOGRAPHICS'
    ADMISSION_SECTION_2_VITALS_TABLE        = 'Admission: SECTION 2. VITALS-ALLERGIES'
    ADMISSION_SECTION_3_SKIN_TABLE          = 'Admission: SECTION 3. SKIN CONDITION'
    ADMISSION_SECTION_4_PHYSICAL_TABLE      = 'Admission: SECTION 4. PHYSICAL / ADL / COMMUNICATION STATUS'
    ADMISSION_SECTION_5_BOWEL_BLADDER_TABLE = 'Admission: SECTION 5. BOWEL-BLADDER EVALUATION'
    ADMISSION_SECTION_6_PSYCHOSOCIAL_TABLE  = 'Admission: SECTION 6. PSYCHOSOCIAL ASPECTS'
    ADMISSION_SECTION_7_DISCHARGE_TABLE     = 'Admission: SECTION 7. DISCHARGE EVALUATION'
    ADMISSION_SECTION_8_FACILITY_TABLE      = 'Admission: SECTION 8. ORIENTATION TO FACILITY'

    # Fall Risk Screen
    def FALL_RISK_SCREEN_TABLE(self):
        return f'{self.get_person_table_prefix()}_Fall Risk Screen' if self.get_person_table_prefix() else 'Fall Risk Screen'
    def FALL_RISK_SCREEN_SECTION_1_TABLE(self):
        return f'{self.get_person_table_prefix()}_Fall Risk Screen: SECTION 1' if self.get_person_table_prefix() else 'Fall Risk Screen: SECTION 1'


    # Harmony (Holy Name) tables
    HARMONY_VITALS_TABLE = 'Harmony Vitals'
    LABOR_ADMISSION_SECTION_1_TABLE='Labor Admission Section 1'
    #LABOR_ADMISSION_SECTION_2_TABLE='Labor Admission Section 2'
    LABOR_ADMISSION_SECTION_3_TABLE='Labor Admission Section 3'
    LABOR_ADMISSION_SECTION_4_TABLE='Labor Admission Section 4'
    LABOR_ADMISSION_SECTION_5_TABLE='Labor Admission Section 5'
    MED_SRG_NURSING_ASSESSMENT_TABLE='Harmony Med/Surg Nursing Assessment'
    CRITICAL_CARE_NURSING_ASSESSMENT_TABLE='Harmony Critical Care Nursing Assessment'
    SPORT_PERFORMANCE_ASSESSMENT_1='Sport Performance Assessment 1'

    SPORT_PERFORMANCE_ASSESSMENT_2='Sport Performance Assessment 2'
    SPORT_2_TEST='Sport Performance Assessment 2 Test'
    STAR_EXCURSION_BALANCE_TEST_L_FOOT_BALANCE_R_FOOT_REACH = 'STAR EXCURSION BALANCE TEST L FOOT BALANCE - R FOOT REACH'
    STAR_EXCURSION_BALANCE_TEST_R_FOOT_BALANCE_L_FOOT_REACH = 'STAR EXCURSION BALANCE TEST R FOOT BALANCE - L FOOT REACH'
    HAND_STAR_EXCURSION_BALANCE_TEST_L_FOOT_BALANCE_R_HAND_REACH='HAND STAR EXCURSION BALANCE TEST L FOOT BALANCE - R HAND REACH'
    HAND_STAR_EXCURSION_BALANCE_TEST_R_FOOT_BALANCE_L_HAND_REACH='HAND STAR EXCURSION BALANCE TEST R FOOT BALANCE - L HAND REACH'

    SPORT_PERFORMANCE_ASSESSMENT_3='Sport Performance Assessment 3'
    SPORT_3_TEST='Sport Performance Assessment 3 Test'
    GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_ANTERIOR='GLOBAL/INTEGRATED ASSESSMENT 3DMAPS - LIMITING AREAS - ANTERIOR'
    GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_LATERAL_OS='GLOBAL/INTEGRATED ASSESSMENT 3DMAPS - LIMITING AREAS - LATERAL OS'
    GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_LATERAL_SS='GLOBAL/INTEGRATED ASSESSMENT 3DMAPS - LIMITING AREAS - LATERAL SS'
    GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_POSTERIOR='GLOBAL/INTEGRATED ASSESSMENT 3DMAPS - LIMITING AREAS - POSTERIOR'
    GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_ROTATIONAL_OS='GLOBAL/INTEGRATED ASSESSMENT 3DMAPS - LIMITING AREAS - ROTATIONAL OS'
    GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_ROTATIONAL_SS='GLOBAL/INTEGRATED ASSESSMENT 3DMAPS - LIMITING AREAS - ROTATIONAL SS'

    SPORT_PERFORMANCE_ASSESSMENT_4='Sport Performance Assessment 4'
    LOCAL_ASSESSMENT_ENDURANCE='LOCAL ASSESSMENT - ENDURANCE'
    LOCAL_ASSESSMENT_STABILITY='LOCAL ASSESSMENT - STABILITY'
    LOCAL_ASSESSMENT_STRENGTH='LOCAL ASSESSMENT - STRENGTH'

    HARMONY_EXAM_SECTION_1_TABLE = 'Harmony.ExamSection_1'
    HARMONY_EXAM_SECTION_2_TABLE = 'Harmony.ExamSection_2'
    HARMONY_EXAM_SECTION_3_TABLE = 'Harmony.ExamSection_3'
    HARMONY_SAFETY_STATUS_SECTION_TABLE = 'Harmony.SafetyStatusSection'
    HARMONY_TREATMENTS_SECTION_TABLE = 'Harmony.TreatmentsSection'

    # Grove (Millennial) tables
    GROVE_ASSESSMENT_DETAILS_TABLE = 'Grove_Assessment_Details'
    GROVE_ASSESSMENT_DETAILS_FALL_TABLE = 'Grove_Assessment_Details_Fall'
    MHCS_NURSING_DAILY_SKILLED_NOTE_TABLE = 'MHCS.Nursing_Daily_Skilled_Note'
    MHCS_ADMISSION_DETAILS_TABLE = 'MHCS.Admission_Details'
    MHCS_EINTERACT_EVALUATION_TABLE = 'MHCS.eINTERACT_Change_in_Condition_Evaluation'
    MHCS_NEUROLOGICAL_EVALUATION_TABLE = 'MHCS.Neurological_Evaluation'


    MHCS_ADMISSION_AIMS_TABLE = "MHCS.Admission_AIMS"
    MHCS_ADMISSION_ALCOHOL_TOBACCO_USE_TABLE = "MHCS.Admission_Alcohol_Tobacco_Use"
    MHCS_ADMISSION_BRADEN_TABLE = "MHCS.Admission_Braden"
    MHCS_ADMISSION_EDUCATION_TABLE = "MHCS.Admission_Education"
    MHCS_ADMISSION_ELOPEMENT_TABLE = "MHCS.Admission_Elopement"
    MHCS_ADMISSION_ENABLER_BED_RAIL_SCREEN_TABLE = "MHCS.Admission_Enabler_Bed_Rail_Screen"
    MHCS_ADMISSION_EVALUATION_OF_BODY_SYSTEMS_TABLE_1 = "MHCS.Admission_Evaluation_of_Body_Systems_1"
    MHCS_ADMISSION_EVALUATION_OF_BODY_SYSTEMS_TABLE_2 = "MHCS.Admission_Evaluation_of_Body_Systems_2"
    MHCS_ADMISSION_FALL_SCREEN_TABLE = "MHCS.Admission_Fall_Screen"
    MHCS_ADMISSION_INFECTIONS_TABLE = "MHCS.Admission_Infections"
    MHCS_ADMISSION_INTERVENOUS_ACCESS_DEVICES_TABLE = "MHCS.Admission_Intravenous_Access_Devices"
    MHCS_ADMISSION_MEDICATIONS_TABLE = "MHCS.Admission_Medications"
    MHCS_ADMISSION_PAIN_TABLE = "MHCS.Admission_Pain"


    
    

    # TODO: Table and sections names need to be loaded dyanically from the API
    """
      The followoing are the list of tables that we are actively supporting in the API
      In order for a table to be accessed by the API, it should be added to this list
      # TODO: Table and sections names need to be loaded dyanically from the API
    """
    def EMR_TABLES(self):
        return [
            self.PATIENTS_TABLE(),
            self.NURSES_TABLE(),
            self.DOCTORS_TABLE,
            self.EPISODES_TABLE, 
            self.PROGRESS_NOTES_TABLE,
            self.ADMISSION_TABLE,
            self.FALL_RISK_SCREEN_TABLE(),
            self.VITALS_TABLE,
            self.HARMONY_VITALS_TABLE,
            self.LABOR_ADMISSION_SECTION_1_TABLE,
            # self.LABOR_ADMISSION_SECTION_2_TABLE,
            self.LABOR_ADMISSION_SECTION_3_TABLE,
            self.LABOR_ADMISSION_SECTION_4_TABLE,
            self.LABOR_ADMISSION_SECTION_5_TABLE,
            self.MED_SRG_NURSING_ASSESSMENT_TABLE,
            self.CRITICAL_CARE_NURSING_ASSESSMENT_TABLE,
            self.SPORT_PERFORMANCE_ASSESSMENT_1,
            self.SPORT_PERFORMANCE_ASSESSMENT_2,
            self.SPORT_PERFORMANCE_ASSESSMENT_3,
            self.SPORT_PERFORMANCE_ASSESSMENT_4,
            self.SPORT_2_TEST,
            self.SPORT_3_TEST,

            # Harmony
            self.HARMONY_EXAM_SECTION_1_TABLE,
            self.HARMONY_EXAM_SECTION_2_TABLE,
            self.HARMONY_EXAM_SECTION_3_TABLE,
            self.HARMONY_SAFETY_STATUS_SECTION_TABLE,
            self.HARMONY_TREATMENTS_SECTION_TABLE,
            
            # Grove
            self.GROVE_ASSESSMENT_DETAILS_TABLE,
            self.GROVE_ASSESSMENT_DETAILS_FALL_TABLE,
            self.MHCS_NURSING_DAILY_SKILLED_NOTE_TABLE,
            self.MHCS_ADMISSION_DETAILS_TABLE,
            self.MHCS_EINTERACT_EVALUATION_TABLE,
            self.MHCS_NEUROLOGICAL_EVALUATION_TABLE,
            self.MHCS_ADMISSION_AIMS_TABLE,
            self.MHCS_ADMISSION_ALCOHOL_TOBACCO_USE_TABLE,
            self.MHCS_ADMISSION_BRADEN_TABLE,
            self.MHCS_ADMISSION_EDUCATION_TABLE,
            self.MHCS_ADMISSION_ELOPEMENT_TABLE,
            self.MHCS_ADMISSION_ENABLER_BED_RAIL_SCREEN_TABLE,
            self.MHCS_ADMISSION_EVALUATION_OF_BODY_SYSTEMS_TABLE_1,
            self.MHCS_ADMISSION_EVALUATION_OF_BODY_SYSTEMS_TABLE_2,
            self.MHCS_ADMISSION_FALL_SCREEN_TABLE,
            self.MHCS_ADMISSION_INFECTIONS_TABLE,
            self.MHCS_ADMISSION_INTERVENOUS_ACCESS_DEVICES_TABLE,
            self.MHCS_ADMISSION_MEDICATIONS_TABLE,
            self.MHCS_ADMISSION_PAIN_TABLE,
            
            # WEIGHTS_TABLE, 
            # BLOOD_PRESSURES_TABLE, 
            # BLOOD_SUGARS_TABLE, 
            # HEIGHTS_TABLE, 
            # TEMPERATURES_TABLE,
            # O2_SATURATIONS_TABLE,
            # PULSES_TABLE,
            # RESPIRATION_TABLE
        ]

    """
      The followoing are the dictionary of multi-section tables.
      A table that has sections should be added to this dict with its sections as a list.
      #TODO: load tables dynamically from the API
    """
    def TABLE_SECTIONS(self):
        return { 
            self.ADMISSION_TABLE: [
                self.ADMISSION_SECTION_1_DEMOGRAPHCS_TABLE, 
                self.ADMISSION_SECTION_2_VITALS_TABLE, 
                self.ADMISSION_SECTION_3_SKIN_TABLE, 
                self.ADMISSION_SECTION_4_PHYSICAL_TABLE, 
                self.ADMISSION_SECTION_5_BOWEL_BLADDER_TABLE, 
                self.ADMISSION_SECTION_6_PSYCHOSOCIAL_TABLE,
                self.ADMISSION_SECTION_7_DISCHARGE_TABLE,
                self.ADMISSION_SECTION_8_FACILITY_TABLE
            ],            
            self.FALL_RISK_SCREEN_TABLE(): [self.FALL_RISK_SCREEN_SECTION_1_TABLE()],
            self.VITALS_TABLE: [
                self.WEIGHTS_TABLE,
                self.BLOOD_PRESSURES_TABLE,
                self.BLOOD_SUGARS_TABLE,
                self.HEIGHTS_TABLE,
                self.TEMPERATURES_TABLE,
                self.O2_SATURATIONS_TABLE,
                self.PULSES_TABLE,
                self.RESPIRATION_TABLE
            ],
            self.SPORT_2_TEST: [
                self.STAR_EXCURSION_BALANCE_TEST_L_FOOT_BALANCE_R_FOOT_REACH,
                self.STAR_EXCURSION_BALANCE_TEST_R_FOOT_BALANCE_L_FOOT_REACH,
                self.HAND_STAR_EXCURSION_BALANCE_TEST_L_FOOT_BALANCE_R_HAND_REACH,
                self.HAND_STAR_EXCURSION_BALANCE_TEST_R_FOOT_BALANCE_L_HAND_REACH,
            ],

            # SPORT_PERFORMANCE_ASSESSMENT_2: [
            #     STAR_EXCURSION_BALANCE_TEST_L_FOOT_BALANCE_R_FOOT_REACH,
            #     STAR_EXCURSION_BALANCE_TEST_R_FOOT_BALANCE_L_FOOT_REACH,
            #     HAND_STAR_EXCURSION_BALANCE_TEST_L_FOOT_BALANCE_R_HAND_REACH,
            #     HAND_STAR_EXCURSION_BALANCE_TEST_R_FOOT_BALANCE_L_HAND_REACH,
            # ],
            
            # SPORT_PERFORMANCE_ASSESSMENT_3: [
            self.SPORT_3_TEST: [
                self.GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_ANTERIOR,
                self.GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_LATERAL_OS,
                self.GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_LATERAL_SS,
                self.GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_POSTERIOR,
                self.GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_ROTATIONAL_OS,
                self.GLOBAL_INTEGRATED_ASSESSMENT_3DMAPS_LIMITING_AREAS_ROTATIONAL_SS,
            ],
            # SPORT_PERFORMANCE_ASSESSMENT_4: [
            #     LOCAL_ASSESSMENT_ENDURANCE,
            #     LOCAL_ASSESSMENT_STABILITY,
            #     LOCAL_ASSESSMENT_STRENGTH,
            # ]
    }

    def PERSON_TABLES(self):
        return [self.PATIENTS_TABLE(), self.NURSES_TABLE(), self.DOCTORS_TABLE]
    
