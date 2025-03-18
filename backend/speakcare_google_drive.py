import os
import json
import pickle
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from os_utils import os_ensure_directory_exists
from speakcare_logging import SpeakcareLogger
from dotenv import load_dotenv

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = "1-BBK1nZDtV_zr0VeqYRnka62x86_oy_I"
CREDS_FILE = "/Users/orifinkelman/.google/auth/credentials.json"
LOCAL_DIR = "/tmp/speakcare/temp"


load_dotenv()
#SCOPES = os.getenv("GDRIVE_SCOPES", "[]")
GOOGLE_OAUTH_CREDS_FILE = os.getenv("GOOGLE_OAUTH_CREDS_FILE", "none") 

scopes_str = os.getenv("GDRIVE_SCOPES", "[]")
SCOPES = json.loads(scopes_str)

class GoogleDriveAPI:

    def __init__(self, scopes: list):
        self.scopes = scopes
        self.service = None
        self.logger = SpeakcareLogger(GoogleDriveAPI.__name__)
        self.logger.info(f"Google Drive API initialized with scopes: {scopes}")

    def authenticate(self, creds_file):
        self.logger.info(f"Authenticating with Google Drive API using credentials file: {creds_file}")
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        return creds

    def list_files(self, folder_id):
        # Query to list files in a specific folder.
        query = f"'{folder_id}' in parents and trashed=false"
        # results = service.files().list(q=query, fields="files(id, name)").execute()
        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        self.logger.info(f"Raw API response: {results}")
        items = results.get('files', [])
        return items



    def download_file(self, file_id, file_name, mime_type):
        # Check if the file is a Google native file.
        if mime_type.startswith("application/vnd.google-apps."):
            # Decide which export MIME type to use based on the native file type.
            if mime_type == "application/vnd.google-apps.document":
                export_mime_type = "application/pdf"  # or use DOCX: application/vnd.openxmlformats-officedocument.wordprocessingml.document
                extension = ".pdf"
            elif mime_type == "application/vnd.google-apps.spreadsheet":
                export_mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                extension = ".xlsx"
            elif mime_type == "application/vnd.google-apps.presentation":
                export_mime_type = "application/pdf"
                extension = ".pdf"
            else:
                # For other Google native types, default to PDF.
                export_mime_type = "application/pdf"
                extension = ".pdf"
            self.logger.info(f"File '{file_name}' is a native Google file ({mime_type}). Exporting as {export_mime_type}...")
            request = self.service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            file_name += extension
        else:
            self.logger.info(f"File '{file_name}' is a binary file. Downloading directly...")
            request = self.service.files().get_media(fileId=file_id)
        
        fh = io.FileIO(file_name, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                self.logger.info(f"Downloading {file_name}: {int(status.progress() * 100)}%")
        self.logger.info(f"Downloaded file: {file_name}")

def main():
    gDriveApi = GoogleDriveAPI(SCOPES)
    gDriveApi.authenticate(CREDS_FILE)

    # Replace with your Google Drive folder ID.
    folder_id = FOLDER_ID
    files = gDriveApi.list_files(folder_id)
    
    if not files:
        print("No files found in the folder.")
    else:
        print("Files found:")
        os_ensure_directory_exists(LOCAL_DIR)

        for f in files:
            mime_type = f.get('mimeType', 'unknown')
            print(f"{f['name']} (ID: {f['id']})  MimeType: {mime_type}")
            gDriveApi.download_file(f['id'], os.path.join(LOCAL_DIR, f['name']), mime_type)

if __name__ == '__main__':
    main()
