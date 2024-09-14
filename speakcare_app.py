from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from models import Transcripts, MedicalRecords, TranscriptsDBSession, MedicalRecordsDBSession, RecordState, RecordType
from speakcare_emr_utils import get_patient_info, commit_record_to_ehr, discard_record, delete_record, create_medical_record

APP_PORT = 3000

app = Flask(__name__)
api = Api(app, doc='/docs')  # Swagger UI will be available at /docs

# Define a Namespace for the API
ns = Namespace('api', description='Operations related to transcripts and medical records')


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
    'info': fields.Raw(required=True, description='The structured medical data in JSON format'),
    'meta': fields.Raw(readonly=True, description='Additional meta'),
    'state': fields.String(description='State of the record', enum=[state.value for state in RecordState]),  # Convert Enum to string 
    'errors': fields.Raw(readonly=True, description='Errors encountered during processing'),
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
    'info': fields.Raw(required=True, description='The structured medical data in JSON format'),
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
    'meta': fields.Raw(readonly=True, description='Additional session information'),
    'processed': fields.Boolean(readonly=True, description='Processing status', default=False),
    'errors': fields.Raw(readonly=True, description='Errors encountered during processing'),
    'created_time': fields.DateTime(readonly=True, description='Time when the record was created'),  # Add created_time field
    'modified_time': fields.DateTime(readonly=True, description='Time when the record was last modified')  # Add modified_time field
})

transcripts_input_model = ns.model('TranscriptsCreateOrUpdate', {
    'text': fields.String(required=True, description='The raw text from speech-to-text transcription'),
})

@ns.route('/records', '/records/<int:id>')
class MedicalRecordsResource(Resource):
    @ns.doc('get_records')
    @ns.marshal_with(medical_records_get_model)  # Use the updated model for response
    def get(self, id=None):
        """List all medical records or get a specific record by ID"""
        session = MedicalRecordsDBSession()
        if id is None:
            # List all medical records
            records = session.query(MedicalRecords).all()
            return records # Automatically marshaled with the model
        else:
            # Get a specific medical record by ID
            record = session.query(MedicalRecords).get(id)
            if not record:
                return jsonify({'error': f'Record {id} not found'}), 404
            return record

    @ns.doc('create_record') 
    @ns.expect(medical_records_post_model)
    def post(self):
        """Add a new medical record"""
        session = MedicalRecordsDBSession()
        data = request.json
        response, status_code, record_id = create_medical_record(session, data)
        return jsonify(response), status_code
        # new_record = MedicalRecords(
        #     type= RecordType(data['type']),  # Convert to Enum
        #     table_name=data['table_name'],
        #     patient_name=data['patient_name'],
        #     nurse_name=data['nurse_name'],   
        #     data=data['data'],
        #     transcript_id = data.get('transcript_id', None)
        # )
        # session.add(new_record)
        # session.commit()
        # return jsonify({'message': 'Medical record added successfully', 'id': new_record.id}), 201
        

    @ns.doc('update_record')
    @ns.expect(medical_records_patch_model)
    def patch(self, id):
        """Update the state of a medical record by ID"""
        session = MedicalRecordsDBSession()
        record = session.query(MedicalRecords).get(id)
        if not record:
            return jsonify({'error': f'Record id {id} not found'}), 404
        data = request.json
        # Update fields only if they are present in the request
        if 'patient_name' in data:
            record.patient_name = data['patient_name']
        if 'nurse_name' in data:
            record.nurse_name = data['nurse_name']
        if 'data' in data:
            record.data = data['data']

        session.commit()
        return jsonify({'message': 'Medical record updated successfully', 'id': id})
    
    @ns.doc('delete_record')
    def delete(self, id):
        """Permanently delete a record by ID"""
        session = MedicalRecordsDBSession()
        record = session.query(MedicalRecords).get(id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404
        
        # Call the delete logic
        response, status_code = delete_record(session, record)
        session.commit()
        return jsonify(response), status_code


# Define separate endpoints for custom actions
@ns.route('/records/<int:id>/commit')
class CommitRecordResource(Resource):
    @ns.doc('apply_record')
    def post(self, id):
        """Commit a record by ID"""
        session = MedicalRecordsDBSession()
        record = session.query(MedicalRecords).get(id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404
        response, status_code = commit_record_to_ehr(record)
        session.commit()
        return jsonify(response), status_code


@ns.route('/records/<int:id>/discard')
class DiscardRecordResource(Resource):
    @ns.doc('discard_record')
    def post(self, id):
        """Discard a record by ID"""
        session = MedicalRecordsDBSession()
        record = session.query(MedicalRecords).get(id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404
        response, status_code = discard_record(record)
        session.commit()
        return jsonify(response), status_code


@ns.route('/transcripts')
class TranscriptsResource(Resource):
    @ns.doc('get_transcripts')
    @ns.marshal_with(transcripts_get_model)  # Use the updated model for response
    def get(self, id=None):
        """List all transcripts or get a specific transcript by ID"""
        session = TranscriptsDBSession()
        if id is None:
            # List all transcripts
            transcripts = session.query(Transcripts).all()
            return transcripts
        else:
            # Get a specific transcript by ID
            transcript = session.query(Transcripts).get(id)
            if not transcript:
                return jsonify({'error': f'Transcript id {id} not found'}), 404
            return transcript
    
    @ns.doc('create_transcript')
    @ns.expect(transcripts_input_model)
    def post(self):
        """Add a new transcript"""
        session = TranscriptsDBSession()
        data = request.json
        new_transcript = Transcripts(
            text = data['transcript']
        )
        session.add(new_transcript)
        session.commit()
        return jsonify({'message': 'Transcript added successfully', 'id': new_transcript.id}), 201

    @ns.doc('update_transcript')
    @ns.expect(transcripts_input_model, validate=True)  # Use PATCH model with optional fields
    def patch(self, id):
        """Update a transcript by ID"""
        session = TranscriptsDBSession()
        transcript = session.query(Transcripts).get(id)
        if not transcript:
            return jsonify({'error': f'Transcript id {id} not found'}), 404
        
        data = request.json

        # Update fields only if they are present in the request
        if 'text' in data:
            transcript.text = data['text']
                
        session.commit()
        return jsonify({'message': 'Transcript updated successfully'})
    

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
            return jsonify({'error': 'Name query parameter is required'}), 400
        
        """Get patient information by name"""
        patient_info = get_patient_info(name)
        if not patient_info:
            return jsonify({'error': f'Patient {name} not found'}), 404
        return patient_info  # Response will be formatted according to patient_info_model


# Register the namespace with the API
api.add_namespace(ns)

if __name__ == '__main__':
    app.run(debug=True, port=APP_PORT)
