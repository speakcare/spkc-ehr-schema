from speakcare_google_drive import GoogleDriveAPI
from speakcare_env import SpeakcareEnv
from speakcare_logging import SpeakcareLogger
from speakcare_enroll_person import SpeakcareEnrollPerson
from speakcare_process import speakcare_process_audio
from speakcare_emr import SpeakCareEmr
from speakcare_emr_utils import EmrUtils
from boto3_session import Boto3Session
from dotenv import load_dotenv
import os
import json
import argparse

load_dotenv()
SpeakcareEnv.prepare_env()

# scopes is read as a string from .env and needs to be converted to a list
GDRIVE_SCOPES_STR = os.getenv("GDRIVE_SCOPES", "[]")
GDRIVE_SCOPES = json.loads(GDRIVE_SCOPES_STR)

GDRIVE_VOICE_SAMPLES_FOLDER_ID = os.getenv("GDRIVE_VOICE_SAMPLES_FOLDER_ID", "none")
GDRIVE_CARE_SESSIONS_FOLDER_ID = os.getenv("GDRIVE_CARE_SESSIONS_FOLDER_ID", "none")
GOOGLE_OAUTH_CREDS_FILE = os.getenv("GOOGLE_OAUTH_CREDS_FILE", "none") 
GDRIVE_DOWNLOAD_DIR =  os.getenv("GDRIVE_DOWNLOAD_DIR", "/tmp/speakcare/gdrive/downloads")
SPEAKCARE_DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")  

class SpeakcarePilot:

    def __init__(self):
        self.logger = SpeakcareLogger(SpeakcarePilot.__name__)
        self.gDriveApi = GoogleDriveAPI(GDRIVE_SCOPES)
        self.gDriveApi.authenticate(GOOGLE_OAUTH_CREDS_FILE)
        self.boto3Session = Boto3Session(SpeakcareEnv.get_working_dirs())
        

    def sync_from_gdrive_to_s3(self, gdrive_folder_id, s3_folder_key): 
        self.logger.info(f"Syncing S3 folder {s3_folder_key} with Google Drive folder {gdrive_folder_id}")
        s3_files = self.boto3Session.s3_list_folder(s3_folder_key)
        gDriveFiles = self.gDriveApi.list_files(gdrive_folder_id)

        # Create a dictionary for quick lookup of S3 files by name
        s3_files_dict = {os.path.basename(s3_file): s3_file for s3_file in s3_files}
        uploaded_files = []

        try:
            binaryFiles = [f for f in gDriveFiles 
                   if not f.get('mimeType', '').startswith("application/vnd.google-apps")]
            for gDriveFile in binaryFiles:
                gDrive_file_name = gDriveFile['name']
                gDrive_file_size = int(gDriveFile.get('size', 0))
                gDrive_file_last_modified = gDriveFile.get('modifiedTime', 0)

                s3_file = s3_files_dict.get(gDrive_file_name)
                if s3_file:
                    if (gDrive_file_size and (self.boto3Session.s3_get_object_size(s3_file) != gDrive_file_size)) or \
                        (gDrive_file_last_modified and (self.boto3Session.s3_get_object_last_modified(s3_file) < gDrive_file_last_modified)):
                            self.logger.info(f"File '{gDrive_file_name}' has modified in Google Drive")
                            s3_file_key = self.copy_gdrive_file_to_s3(gDriveFile, s3_folder_key)
                            uploaded_files.append(s3_file_key)
                    else:
                        self.logger.info(f"File '{gDrive_file_name}' is up-to-date in S3 folder '{s3_folder_key}'")
                        
                else:
                    self.logger.info(f"Uploading new file '{gDrive_file_name}' to S3 folder '{s3_folder_key}'")
                    s3_file_key = self.copy_gdrive_file_to_s3(gDriveFile, s3_folder_key)
                    uploaded_files.append(s3_file_key)
                    
        except Exception as e:
            self.logger.log_exception(f"Error syncing S3 folder {s3_folder_key} with Google Drive folder {gdrive_folder_id}", e)
        
        return uploaded_files
    
    
    def copy_gdrive_file_to_s3(self, gDriveFile, s3_folder_key):
        try:
            gdrive_file_name = gDriveFile['name']
            gdrive_file_id = gDriveFile['id']
            gdrive_file_mime_type = gDriveFile.get('mimeType', 'unknown')
            download_file_name = f"{SpeakcareEnv.get_local_downloads_dir()}/{gdrive_file_name}"
            self.logger.debug(f"Downloading file '{gdrive_file_id}' from Google Drive to '{download_file_name}'")
            self.gDriveApi.download_file(gdrive_file_id, download_file_name, gdrive_file_mime_type)
            s3_file_key = f"{s3_folder_key}/{gdrive_file_name}"
            self.logger.debug(f"Uploading file '{gdrive_file_id}' to S3 '{s3_file_key}'")
            self.boto3Session.s3_upload_file(download_file_name, s3_file_key)
            self.logger.debug(f"Deleting local file '{download_file_name}'")
            os.remove(download_file_name)
            return self.boto3Session.s3_get_file_path(s3_file_key)
        except Exception as e:
            self.logger.log_exception(f"Error copying file '{gdrive_file_name}' to S3 folder '{s3_folder_key}'", e)
            return None
   
    
    def sync_voice_sample_files(self):
        return self.sync_from_gdrive_to_s3(GDRIVE_VOICE_SAMPLES_FOLDER_ID, SpeakcareEnv.get_voice_samples_dir())
    
    def sync_care_session_files(self):
        return self.sync_from_gdrive_to_s3(GDRIVE_CARE_SESSIONS_FOLDER_ID, SpeakcareEnv.get_care_sessions_dir())


    def enroll_new_persons(self):
        persons_voice_samples = self.sync_voice_sample_files()
        self.logger.info(f"Enrolling persons from voice samples: {persons_voice_samples}")
        enroller = SpeakcareEnrollPerson()
        enrolled_persons = []
        try:
            for voice_sample in persons_voice_samples:
                person = enroller.enroll_person(voice_sample)
                if person:
                    enrolled_persons.append(person)
        except Exception as e:
            self.logger.log_exception(f"Error enrolling persons from voice samples: {persons_voice_samples}", e)
        finally:
            self.logger.info(f"Enrolled {len(enrolled_persons)} persons from voice samples: {persons_voice_samples}")
            return enrolled_persons

    def process_new_care_sessions(self):
        care_session_files = self.sync_care_session_files()
        self.logger.info(f"Processing care sessions: {care_session_files}")
        try:
            for care_session in care_session_files:
                record_ids, response = speakcare_process_audio([care_session], [SpeakCareEmr.HARMONY_VITALS_TABLE, SpeakCareEmr.LABOR_ADMISSION_TABLE])
                if record_ids:
                    self.logger.info(f"Processed care session {care_session} resulting record_ids: {record_ids}. response: {response}")
                else:
                    self.logger.error(f"Error processing care session {care_session}. response: {response}")
        except Exception as e:
            self.logger.log_exception(f"Error processing care sessions: {care_session_files}", e)

     


TEST_FOLDER_ID = "1Gh1rI3E7O_XqBqP-VKmi2hrbkRqGC4_O"
def main():

    parser = argparse.ArgumentParser(description='Speakcare speech to EMR.')
    # Add arguments
    parser.add_argument('-e', '--enroll', action='store_true',
                        help='Enroll new persons from voice samples')
    parser.add_argument('-p', '--process', action='store_true',
                        help='Process new care sessions')

    EmrUtils.init_db(db_directory=SPEAKCARE_DB_DIRECTORY, create_db=True)
    pilot = SpeakcarePilot()

    args = parser.parse_args()
    if args.enroll:
        enrolled = pilot.enroll_new_persons()
        print(f"Enrolled {enrolled}")
    
    if args.process:
        pilot.process_new_care_sessions()
    
if __name__ == '__main__':
    main()
        