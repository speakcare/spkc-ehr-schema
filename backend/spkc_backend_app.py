from flask import Flask, request, render_template_string
from flask_restx import Api, Resource, fields, Namespace, reqparse
from flask_cors import CORS
import json
from dotenv import load_dotenv
import os, sys
from models import RecordState, RecordType, TranscriptState
import logging
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage 
from os_utils import ensure_directory_exists
from backend.spkc_emr_utils import EmrUtils
from backend.spkc_audio import get_input_audio_devices
from speakcare import speakcare_record_and_process_audio, speakcare_process_audio
from backend.spkc_logging import SpeakcareLogger

load_dotenv()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")
APP_PORT = os.getenv("APP_PORT", 5000)

app = Flask(__name__)
# Enable CORS only for localhost:4000 and airtable.com
CORS(app, resources={r"/*": {"origins": ["http://localhost:4000", "https://airtable.com"]}})

app.logger = SpeakcareLogger(__name__)
app.logger.setLevel('DEBUG')
app.debug = True
api = Api(app, version='1.0', title='SpeakCare API', description='API for SpeakCare speech to EMR.', doc='/docs')

@app.route('/hello', methods=['GET'])
def hello():
    #print("Flask route is hit!")  # To ensure the request is processed
    app.logger.debug('Debug message: Saying Hello!')
    return 'Hello, World!\r\n'


@app.route('/redoc')
def redoc():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="ie=edge">
            <title>Redoc API Docs</title>
            <!-- Link to the locally hosted favicon -->
            <link rel="icon" href="{{ url_for('static', filename='img/favicon.ico') }}" type="image/x-icon">
            <!-- Redoc CDN script -->
            <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
        </head>
        <body>
            <redoc spec-url="/swagger.json"></redoc>
            <script>
                Redoc.init("/swagger.json")
            </script>
        </body>
        </html>
    ''')    

# Define a Namespace for the API
ns = Namespace('api', description='All SpeakCare API endpoints')


# Define the MedicalRecords model for API documentation
medical_records_get_model = ns.model('MedicalRecordsGet', {
    'id': fields.Integer(description='The unique identifier of the record'),
    'emr_record_id': fields.String(readonly=True, description='External EMR record ID'),
    'emr_url': fields.String(readonly=True, description='URL to the EMR record'),
    'type': fields.String(description='Type of record', enum=[record_type.value for record_type in RecordType]),  # Convert Enum to string
    'table_name': fields.String(description='Table name in the external EMR system'),
    'patient_name': fields.String(description='Name of the patient'),
    'patient_id': fields.String(readonly=True, description='External EMR patient ID'),
    'nurse_name': fields.String(description='Name of the nurse'),
    'nurse_id': fields.String(readonly=True, description='External EMR nurse ID'),
    'fields': fields.Raw(required=True, description='The structured medical data in JSON format'),
    'state': fields.String(description='State of the record', enum=[state.value for state in RecordState]),  # Convert Enum to string 
    'errors': fields.List(fields.String, readonly=True, description='Errors encountered during processing'),
    'created_time': fields.DateTime(readonly=True, description='Time when the record was created'),  # Add created_time field
    'modified_time': fields.DateTime(readonly=True, description='Time when the record was last modified'),  # Add modified_time field
    'transcript_id': fields.Integer(description='ID of the transcript that created this record')
})

 
medical_records_post_model = ns.model('MedicalRecordsCreate', {
    'type': fields.String(required=True, description='Type of record', enum=[record_type.value for record_type in RecordType]),  # Convert Enum to string
    'table_name': fields.String(required=True, description='Table name in the external EMR system'),
    'patient_name': fields.String(required=True, description='Name of the patient'),
    'patient_id': fields.String(description='External EMR patient ID'),
    'nurse_name': fields.String(required=True, description='Name of the nurse'),
    'nurse_id': fields.String(description='External EMR nurse ID'),
    'fields': fields.Raw(required=True, description='The structured medical data in JSON format'),
    'transcript_id': fields.Integer(description='ID of the transcript that created this record')
})

medical_records_patch_model = ns.model('MedicalRecordsUpdate', {
    'patient_name': fields.String(description='Name of the patient'),
    'patient_id': fields.String(description='External EMR patient ID'),
    'nurse_name': fields.String(description='Name of the nurse'),
    'nurse_id': fields.String(description='External EMR nurse ID'),
    'info': fields.Raw(description='The structured medical data in JSON format'), 
})


# Define the Transcripts model for API documentation
transcripts_get_model = ns.model('TranscriptsGet', {
    'id': fields.Integer(readonly=True, escription='The unique identifier of the transcript'),
    'text': fields.String(required=True, description='The raw text from speech-to-text transcription'),
    'state': fields.String(description='State of the transcript', enum=[state.value for state in TranscriptState]),  # Convert Enum to string 
    'errors': fields.List(fields.String, readonly=True, description='Errors encountered during processing'),
    'created_time': fields.DateTime(readonly=True, description='Time when the record was created'),  # Add created_time field
    'modified_time': fields.DateTime(readonly=True, description='Time when the record was last modified')  # Add modified_time field
})

transcripts_input_model = ns.model('TranscriptsCreate', {
    'text': fields.String(required=True, description='The raw text from speech-to-text transcription'),
})

@ns.route('/records', '/records/<int:id>')
class MedicalRecordsResource(Resource):
    @ns.doc('get_records')
    @ns.param('state', 'Get only records with a specific state', enum=[state.value for state in RecordState])
    @ns.param('table_name', 'Get only records from a specific table', type=str)
    @ns.marshal_with(medical_records_get_model)  # Use the updated model for response
    def get(self, id=None):
        """List all medical records or get a specific record by ID"""
        if id is None:
            state_param = request.args.get('state', default=None, type=str)
            table_name_param = request.args.get('table_name', default=None, type=str)
        
            # Convert state_param to RecordState if provided
            state = None
            if state_param:
                try:
                    state = RecordState[state_param.upper()]
                except KeyError:
                    return {"error": "Invalid state parameter"}, 400
            # List all medical records
            records, error = EmrUtils.get_all_records(state=state, table_name=table_name_param)
            if records is None:
                return {'error': f'Error fetching all records. {error}'}, 400
                
            elif not records:
                return [], 200
            else:   
                return records, 200 # Automatically marshaled with the model
        else:
            # Get a specific medical record by ID
            record, err = EmrUtils.get_record(id)
            if not record:
                return {'error': f'Record {id} not found. {err}'}, 404
            return record

    @ns.doc('create_record') 
    @ns.expect(medical_records_post_model)
    def post(self):
        """Add a new medical record"""
        data = request.json
        record_id , record_state, response = EmrUtils.create_record(data)
        if record_id and record_state != RecordState.ERRORS:
            return response, 201
        elif record_id: # errors
            return response, 422 # Unprocessable Entity (due to semantic errors)
        else:
            return response, 400
        

    @ns.doc('update_record')
    @ns.expect(medical_records_patch_model)
    def patch(self, id):
        """Update the state of a medical record by ID"""
        data = request.json
        success, response = EmrUtils.update_record(data, id)
        if success:
            return response, 200
        else:
            return response, 400
    
    @ns.doc('delete_record')
    def delete(self, id):
        """Permanently delete a record by ID"""
        deleted, response = EmrUtils.delete_record(id)
        if deleted:
            return response, 204
        else:
            return response, 400


# Define separate endpoints for custom actions
@ns.route('/records/<int:id>/commit')
class CommitRecordResource(Resource):
    @ns.doc('commit_record')
    def post(self, id):
        """Commit a record to EMR by ID"""
        emr_record_id, record_state, response = EmrUtils.commit_record_to_emr(record_id=id)
        if emr_record_id:
            return response, 201
        else:
            return response, 400


@ns.route('/records/<int:id>/discard')
class DiscardRecordResource(Resource):
    @ns.doc('discard_record')
    def post(self, id):
        """Discard a record by ID"""
        success, response = EmrUtils.discard_record(id)
        if success:
            return response, 204
        else:
            return response, 400


@ns.route('/transcripts')
class TranscriptsResource(Resource):
    @ns.doc('get_transcripts')
    @ns.marshal_with(transcripts_get_model)  # Use the updated model for response
    @ns.param('state', 'Get only transcripts with a specific state', enum=[state.value for state in TranscriptState])
    @ns.param('text_limit', 'Limit the length of the text field in the response', type=int)
    def get(self, id=None):
        """List all transcripts or get a specific transcript by ID"""
        # Get query parameters
        if id is None:
            state_param = request.args.get('state', default=None, type=str)
            text_limit_param = request.args.get('text_limit', default=200, type=int)
            
            # Convert state_param to TranscriptState if provided
            state = None
            if state_param:
                try:
                    state = TranscriptState[state_param.upper()]
                except KeyError:
                    return {"error": "Invalid state parameter"}, 400
            # List all transcripts
            transcripts, err = EmrUtils.get_all_transcripts(text_limit=text_limit_param, state=state)
            if transcripts is None:
                return {'error': f'Error fetching all transcripts. {err}'}, 400
            elif not transcripts:
                return [], 200
            return transcripts
        else:
            # Get a specific transcript by ID
            transcript, err = EmrUtils.get_transcript(id)
            if not transcript:
                return {'error': f'Transcript id {id} not found. Error: {err}'}, 404
            return transcript
    
    @ns.doc('create_transcript')
    @ns.expect(transcripts_input_model)
    def post(self):
        """Add a new transcript"""
        data = request.json
        transcript = data['transcript']
        new_transcript, response = EmrUtils.add_transcript(text=transcript)
        if not new_transcript:
            return {'error': f'Error creating transcript. {response}'}, 400            
        return {'message': 'Transcript added successfully', 'id': new_transcript.id}, 201

    @ns.doc('update_transcript')
    @ns.expect(transcripts_input_model, validate=True)  # Use PATCH model with optional fields
    def patch(self, id):
        return {'error': '"Method not allowed"'}, 405
        """Update a transcript by ID"""
    
    @ns.doc('delete_transcript')
    def delete(self, id):
        """Permanently delete a transcript by ID"""
        deleted, response = EmrUtils.delete_transcript(id)
        if deleted:
            return response, 204
        else:
            return response, 400
        
# Define the models for Swagger documentation
patient_info_model = ns.model('PatientInfo', {
        'emr_patient_id': fields.String(description='Unique patient ID in the EMR'),
        'patient_id':fields.String(description='Unique patient ID'),
        'correct_name': fields.String(description='Patient\'s name as it appears in the EMR'),
        'date_of_birth': fields.Date(description='Patient\'s date of birth'),
        'gender':fields.String(description='Patient\' gender'),
        'department': fields.String(description='dpartment'),
        'admission_date': fields.Date(description='Patient\'s admission date'),
        'photo' : fields.Raw(description='JSON Array of URLs and metadata for attachments')
})

# Define other models like transcripts_get_model, transcripts_input_model, and transcripts_patch_model...

# Patient Info Endpoint
@ns.route('/patient')
class PatientResource(Resource):
    @ns.doc('get_patient_info')
    @ns.param('name', 'The name of the patient to fetch information for')
    @ns.marshal_with(patient_info_model)  # Document the response with the defined model
    def get(self):
        name = request.args.get('name')
        if not name:
            return {'error': 'Name query parameter is required'}, 400
        
        """Get patient information by name"""
        patient_info = EmrUtils.get_patient_info(name)
        if not patient_info:
            return {'error': f'Patient {name} not found'}, 404
        return patient_info  # Response will be formatted according to patient_info_model

@ns.route('/table-names')
class TableNamesResource(Resource):
    @ns.doc('get_emr_table_names')
    #@ns.marshal_with(audio_devices_model)  # Document the response with the defined model
    def get(self):
        
        """Get EMR table names"""
        table_names = EmrUtils.get_table_names()
        return {'table_names': table_names}, 200


# Define the models for Swagger documentation
audio_devices_model = ns.model('AudioInputDevices', {
        'name': fields.String(description='Unique audio device name'),
        'index':fields.String(description='Unique audio device index')
})

# Define other models like transcripts_get_model, transcripts_input_model, and transcripts_patch_model...

# Patient Info Endpoint
@ns.route('/audio-devices')
class AudioDeviceResource(Resource):
    @ns.doc('get_input_audio_devices')
    @ns.marshal_with(audio_devices_model)  # Document the response with the defined model
    def get(self):
        
        """Get auido device information"""
        device_info = get_input_audio_devices()
        return device_info, 200  # Response will be formatted according to audio_devices_model



process_audio_model = ns.model('ProcessAudio', {
    'output_file_prefix': fields.String(required=False, default='output', description='Prefix for the output file'),
    'recording_duration': fields.Integer(required=False, default=30, description='Duration of the recording in seconds'),
    'table_name': fields.String(required=True, description='Name of the table to store data'),
    'audio_device': fields.Integer(required=True, description='Audio device index'),
    'dryrun': fields.Boolean(required=False, default=False, description='Run without actually processing the audio')
})

@ns.route('/record-and-process-audio')
class RecordAndProcessAudioResource(Resource):
    @ns.doc('record_and_process_audio')
    @ns.expect(process_audio_model) # Use the updated model for response
    def post(self):

        # Extract JSON data from request body
        data = request.json
        
        # Extract parameters with default values if not provided
        output_file_prefix = data.get('output_file_prefix', 'output')
        recording_duration = int(data.get('duration', 30))
        table_name = data.get('table_name', None)
        audio_device = int(data.get('audio_device', None))
        dryrun = bool(data.get('dryrun', False))
        
        app.logger.debug(f"POST: process-audio received: output_file_prefix={output_file_prefix}, recording_duration={recording_duration}, table_name={table_name}, audio_device={audio_device}, dryrun={dryrun}")
        record_id, err = speakcare_record_and_process_audio(output_file_prefix=output_file_prefix, recording_duration=recording_duration, table_name=table_name, audio_device=audio_device, dryrun=dryrun)

        if record_id:
            app.logger.info(f"Audio processed successfully. Record ID: {record_id}")
            return {'message': f'Audio processed successfully. New record id: {record_id}'}, 201
        else:
            app.logger.error(f"Error processing audio: {err}")
            return err, 400
        

audio_parser = api.parser()
audio_parser.add_argument('audio_file', location='files', type=FileStorage, required=True, help='The audio file to be uploaded')
audio_parser.add_argument('table_name', location='form', type=str, action='append', required=True, help='Name of the tables to store converted data')


@ns.route('/process-audio')
class ProcessAudioResource(Resource):
    @ns.doc('process_audio')
    @ns.expect(audio_parser)
    def post(self):

        # Get the file from the request
        dirname = './out/audio'
        args = audio_parser.parse_args()
        audio_file = args['audio_file']
        if audio_file and audio_file.filename == '':
            return {'error': 'No file provided'}, 400
        
        # Secure the filename and save the file (modify as needed)
        filename = secure_filename(audio_file.filename)
        audio_local_filename = os.path.join(dirname, filename)
        ensure_directory_exists(dirname)

        # Get other form fields
        table_names = args['table_name']

        app.logger.debug(f"POST: process-audio received: audio_filename={audio_local_filename}, table_names={table_names}")
        
        audio_file.save(audio_local_filename)
        app.logger.debug(f"Audio file saved as {audio_local_filename}")

        # Now, you have both the audio file and the other data fields
        record_ids, err = speakcare_process_audio(audio_files=[audio_local_filename], tables=table_names)
        if record_ids:
            app.logger.info(f"Audio file {audio_local_filename} processed successfully. Create {len(record_ids)} records. IDs: {record_ids}")
            return {'message': f'Audio processed successfully. New record ids: {record_ids}'}, 201
        else:
            app.logger.error(f"Error processing audio file {audio_local_filename}: {err}")
            return err, 400
       
# Register the namespace with the API
api.add_namespace(ns)

# Initialize the database
# no need to create it as it is created by a pre-init script
EmrUtils.init_db(db_directory=DB_DIRECTORY, create_db=False)

if __name__ == '__main__':
    # for debug purposes allow running the app from the command line
    try:
        app.run(debug=True,host='::', port=APP_PORT)
    except KeyboardInterrupt as e:
        app.logger.info(f'API server exited by user. ({e})')
    except Exception as e:
        app.logger.error(f'API server exited with error: {e}')
    finally:
        EmrUtils.cleanup_db(delete_db_files=False)
