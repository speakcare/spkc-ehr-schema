# My To-Do List

### Speakcare emr
- [x] Add validation to record create and update using the schema
- [x] Create the db folder if not exist
- [x] Allow multi select with partial wrong values
- [x] Fail validation on wrong or missing required fields
- [ ] Support deletion of EMR records
- [ ] Supprot deletion of db records and if connected to EMR delete from EMR


### EMR utils
- [x] work on utils to finish the create record and update record
- [x] Add support for records with sections in utils and in create records
- [x] Add utils for transciprt handling

### Text processing
- [x] Add the converter process from transcript to SpeakCareEmrApi
- [ ] Handle cases of repeated information in the same transcript

### User app
- [x] Add browser extension
- [x] Make browser extension look nice
- [-] Check why extension microphone permission is not requersted automatically
- [x] save and load extension state to/from local storage
- [x] Make the extnesion float and not close when touching the web page

### System
- [-] Add run script to load all the processes
- [x] Add sqlite db browser to the project
- [x] Update the transcription db and connect it to the medical reocords
- [ ] Explore https://docs.cerebrium.ai/v4/examples/realtime-voice-agents
- [x] Change GPT API to use the new structured output using JSON schema
- [ ] Voice callibration
- [ ] Support record with all captured nurses (discuss with Gil)
- [ ] Allow running on transcription output files instead audio

### General
- [x] README file