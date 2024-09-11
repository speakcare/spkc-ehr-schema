from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from models import Transcripts, MedicalRecords, TranscriptsDBSession, MedicalRecordsDBSession

APP_PORT = 3000

app = Flask(__name__)
api = Api(app, doc='/docs')  # Swagger UI will be available at /docs

# Define a Namespace for the API
ns = Namespace('api', description='Operations related to transcripts and medical records')
api.add_namespace(ns)

# Define the MedicalRecords model for API documentation
medical_records_model = ns.model('MedicalRecords', {
    'data': fields.Raw(required=True, description='The structured medical data in JSON format'),
    'meta': fields.Raw(description='Additional meta'),
    'state': fields.String(description='State of the record', default='new')
})

# Define the Transcripts model for API documentation
transcripts_model = ns.model('Transcripts', {
    'text': fields.String(required=True, description='The raw text from speech-to-text'),
    'meta': fields.Raw(description='Additional session information'),
    'processed': fields.Boolean(description='Processing status', default=False)
})

@ns.route('/records', '/records/<int:id>')
class MedicalRecordsResource(Resource):
    @ns.doc('get_records')
    def get(self, id=None):
        """List all medical records or get a specific record by ID"""
        session = MedicalRecordsDBSession()
        if id is None:
            # List all medical records
            records = session.query(MedicalRecords).all()
            return jsonify([{'id': r.id, 'data': r.data, 'meta': r.meta, 'state': r.state} for r in records])
        else:
            # Get a specific medical record by ID
            record = session.query(MedicalRecords).get(id)
            if not record:
                return jsonify({'error': 'Record not found'}), 404
            return jsonify({'id': record.id, 'data': record.data, 'meta': record.meta, 'state': record.state})

    @ns.doc('create_record') 
    @ns.expect(medical_records_model)
    def post(self):
        """Add a new medical record"""
        session = MedicalRecordsDBSession()
        data = request.json
        new_record = MedicalRecords(
            data=data['data'],
            meta=data.get('meta', {}),
            state=data.get('state', 'new')
        )
        session.add(new_record)
        session.commit()
        return jsonify({'message': 'Medical record added successfully', 'id': new_record.id}), 201

    @ns.doc('update_record')
    @ns.expect(medical_records_model, validate=True)
    def patch(self, id):
        """Update the state of a medical record by ID"""
        session = MedicalRecordsDBSession()
        record = session.query(MedicalRecords).get(id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404
        data = request.json
        record.state = data.get('state', record.state)
        session.commit()
        return jsonify({'message': 'Medical record updated successfully'})


@ns.route('/transcripts')
class TranscriptsResource(Resource):
    @ns.doc('get_transcripts')
    def get(self, id=None):
        """List all transcripts or get a specific transcript by ID"""
        session = TranscriptsDBSession()
        if id is None:
            # List all transcripts
            transcripts = session.query(Transcripts).all()
            return jsonify([{'id': t.id, 'text': t.text, 'meta': t.meta, 'processed': t.processed} for t in transcripts])
        else:
            # Get a specific transcript by ID
            transcript = session.query(Transcripts).get(id)
            if not transcript:
                return jsonify({'error': 'Transcript not found'}), 404
            return jsonify({'id': transcript.id, 'text': transcript.text, 'meta': transcript.meta, 'processed': transcript.processed})
    
    @ns.doc('create_transcript')
    @ns.expect(transcripts_model)
    def post(self):
        """Add a new transcript"""
        session = TranscriptsDBSession()
        data = request.json
        new_transcript = Transcripts(
            text=data['text'],
            meta=data.get('meta', {}),
            processed=data.get('processed', False)
        )
        session.add(new_transcript)
        session.commit()
        return jsonify({'message': 'Transcript added successfully', 'id': new_transcript.id}), 201


# Register the namespace with the API
api.add_namespace(ns)

if __name__ == '__main__':
    app.run(debug=True, port=APP_PORT)
