import os
from decimal import Decimal
from enum import Enum as PyEnum
from datetime import datetime
from botocore.exceptions import ClientError
from speakcare_common import SpeakcareLogger
from boto3_session import Boto3Session
from backend.speakcare_voice_embedder import VoiceEmbedder


class SpeakerRole(PyEnum):
    PATIENT = 'Patient'
    NURSE = 'Nurse'
    UNKNOWN = 'Unknown'


class SpeakcareEmbeddings:

    UNKNOWN_SPEAKER = 'Unknown'

    def __init__(self, 
                 vocoder: VoiceEmbedder, 
                 matching_similarity_threshold: float =0.75, 
                 addition_similarity_threshold: float =0.95
                 ):
        try:
            self.logger = SpeakcareLogger(type(self).__name__)
            self.b3session = Boto3Session.get_single_instance()
            self.speakers_table_name = self.b3session.dynamo_get_table_name("speakers")
            self.vocoder: VoiceEmbedder = vocoder
            self.matching_similarity_threshold: float = float(matching_similarity_threshold)
            self.addition_similarity_threshold: float = float(addition_similarity_threshold)
            self.known_speakers = self.__fetch_all_speakers()
            self.logger.info(f'Initialized with {len(self.known_speakers)} known speakers.')
            self.logger.info(f'matching_similarity_threshold: {self.matching_similarity_threshold}. addition_similarity_threshold: {self.addition_similarity_threshold}')
        except Exception as e:
            self.logger.log_exception(f"Initialization error:", e)
            raise e

    def __fetch_all_speakers(self):
        """Fetch all embeddings from a DynamoDB table."""
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        response = table.scan()
        return {item['Name']: item for item in response['Items']}
       

    def get_speaker(self, speaker_name):
        return self.known_speakers.get(speaker_name, None)  
    
    def get_speaker_role(self, speaker_name) -> SpeakerRole:
        if speaker_name in self.known_speakers:
            return SpeakerRole(self.known_speakers[speaker_name].get('Role', SpeakerRole.UNKNOWN.value))
        else:
            return SpeakerRole.UNKNOWN
    
    def __create_or_update_speaker(self, speaker_embedding, speaker_role: SpeakerRole, speaker_name):
        """Match or create a new speaker in the speakers table."""
        # Check for identical embeddings
        try:
            for known_speaker_name, speaker in self.known_speakers.items():
                embeddings = speaker.get('EmbeddingVectors', [])
                role = speaker.get('Role', '')
                for idx, known_embedding in enumerate(embeddings):
                    embedding_vector = self.vocoder.convert_from_decimal_list(known_embedding) 
                    similarity = self.vocoder.similarity(speaker_embedding, embedding_vector)
                    if self.vocoder.isidenticial(speaker_embedding, embedding_vector):
                        if known_speaker_name != speaker_name:
                            self.logger.warning(f"Colliding embedding found for speaker '{role}': '{known_speaker_name}' and new speaker '{speaker_role.value}': '{speaker_name}'. No changes made.")
                            return speaker, "collision"
                        else:
                            self.logger.info(f"Identical embedding found for speaker '{role}': '{known_speaker_name}'. No changes made.")
                            return speaker, "identical"
                    elif similarity >= self.addition_similarity_threshold and known_speaker_name != speaker_name:
                        self.logger.warning(f"High similarity found between new speaker {speaker_name} and existing speaker {known_speaker_name} with similarity {similarity}")

            # Add the new embedding to the speaker
            if speaker_name in self.known_speakers:
                speaker = self.__add_embedding_to_speaker(speaker_name, speaker_embedding)
                self.logger.info(f"Added new embedding to existing speaker: {speaker_name}")
                return speaker, "added"
            else:
                speaker = self.__add_new_speaker(speaker_name, speaker_embedding, speaker_role)
                self.logger.info(f"New speaker created: {speaker_name}")
                return speaker, "created"
        except Exception as e:
            self.logger.log_exception(f"Create or update speaker error", e)
            return None, "error"

    
    def find_best_match(self, speaker_embedding):
        """Find best match."""
        try:
            self.logger.debug(f"Matching speaker embedding against {len(self.known_speakers)} known speakers")
            best_match = None
            highest_similarity = -1
            for known_speaker_name, speaker in self.known_speakers.items():
                embeddings = speaker.get('EmbeddingVectors', [])
                role = speaker.get('Role', '')
                self.logger.debug(f"Checking speaker {known_speaker_name} with {len(embeddings)} embeddings")
                for known_embedding in embeddings:
                    embedding_vector = self.vocoder.convert_from_decimal_list(known_embedding)
                    similarity = self.vocoder.similarity(speaker_embedding, embedding_vector)
                    self.logger.debug(f"cosine similarity: {similarity} with '{known_speaker_name}' role: '{role}'")
                    if similarity >= self.matching_similarity_threshold:
                        self.logger.debug(f"Found high similarity: {similarity} with '{known_speaker_name}' role: '{role}'")
                        if similarity > highest_similarity:
                            best_match = speaker
                            highest_similarity = similarity

            if best_match:
                self.logger.debug(f"Match found: '{best_match['Name']}' with similarity {highest_similarity}")
                return best_match, "matched", highest_similarity
            else:
                self.logger.debug(f"No match found.")
                return None, "unmatched", 0
        except Exception as e:
            self.logger.log_exception(f"Find best match error", e)
            return None, "error", 0
  

    def __add_embedding_to_speaker(self, speaker_name, embedding):
        """Add a new embedding to an existing speaker."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(self.speakers_table_name)

        item = table.get_item(Key={'Name': speaker_name}).get('Item')
        if item:
            if 'EmbeddingVectors' not in item:
                item['EmbeddingVectors'] = [embedding_decimal]
            else:
                item['EmbeddingVectors'].append(embedding_decimal)
            table.put_item(Item=item)
            self.logger.info(f"Added new embedding to speaker {speaker_name} in table {self.speakers_table_name}")
            return item
        else:
            self.logger.error(f"Speaker {speaker_name} not found in table {self.speakers_table_name}")
            return None
        
 

    def __add_new_speaker(self, speaker_name, embedding, speaker_role: SpeakerRole):
        """Save speaker embedding to DynamoDB."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        item = {
            "EmbeddingVectors": [embedding_decimal],
            "Name": speaker_name,
            "Role": speaker_role.value,
            "Timestamp": datetime.now().isoformat()
        }
        table.put_item(Item=item)
        self.logger.info(f"Saved embedding for {speaker_name} in table {self.speakers_table_name}")
        return item


    def delete_embedding_from_dynamodb(self, speaker_name, embedding_index=None):
        """Delete speaker embedding from DynamoDB."""
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        try:
            if embedding_index is not None:
                item = table.get_item(Key={'Name': speaker_name}).get('Item')
                if item and 'EmbeddingVectors' in item:
                    del item['EmbeddingVectors'][embedding_index]
                    if item['EmbeddingVectors']:
                        table.put_item(Item=item)
                    else:
                        table.delete_item(Key={'Name': speaker_name})
                    self.logger.info(f"Deleted embedding index {embedding_index} for speaker {speaker_name} from table {self.speakers_table_name}")
            else:
                table.delete_item(Key={'Name': speaker_name})
                self.logger.info(f"Deleted item with Name {speaker_name} from table {self.speakers_table_name}")
        except ClientError as e:
            self.logger.error(f"Unable to delete item: {e.response['Error']['Message']}")


    def add_voice_sample(self, speaker_voice_file_path, speaker_name:str, speaker_role: SpeakerRole):
        """Process a voice sample and add to the specified table."""
        #remove white spaces from speaker_name and replace them witn _ (underscore)
        if not speaker_name:
            err = "Speaker name is required"
            self.logger.error(err)
            raise ValueError(err)

        local_voice_file = None
        remove_local_file = False
        try:
            local_voice_file, remove_local_file = self.b3session.s3_localize_file(speaker_voice_file_path)   
            if not local_voice_file:
                raise Exception("Failed to localize voice file") 
            
            _speaker_name = speaker_name.replace(" ", "_")
            self.vocoder.load_audio_file(local_voice_file)
            embeddings = self.vocoder.get_embedding()
            if embeddings is None:
                self.logger.error(f"Failed to extract embeddings from {speaker_voice_file_path}")
                return None, "error"        
            speaker, result = self.__create_or_update_speaker(embeddings, speaker_role, speaker_name=_speaker_name)
            self.vocoder.reset()
            # refresh the known speakers
            self.known_speakers = self.__fetch_all_speakers()
            
            self.logger.info(f"add_voice_sample: create_speaker attepted for speaker '{speaker_role.value}': '{_speaker_name}'. Result: '{result}' with speaker '{speaker['Name']}'")
            return speaker, result
        except Exception as e:
            self.logger.log_exception(f"add_voice_sample error", e)
            return None, "error"
        finally:
            if remove_local_file and local_voice_file and os.path.isfile(local_voice_file):
                os.remove(local_voice_file)

    def lookup_speaker(self, speaker_voice_file_path):
        """Lookup a speaker in the database."""
        #remove white spaces from speaker_name and replace them witn _ (underscore)

        local_voice_file = None
        remove_local_file = False
        try:
            local_voice_file, remove_local_file = self.b3session.s3_localize_file(speaker_voice_file_path)
            if not local_voice_file:
                raise Exception("Failed to localize voice file") 
            
            self.vocoder.load_audio_file(local_voice_file)
            embeddings = self.vocoder.get_embedding()
            if embeddings is None:
                self.logger.error(f"Failed to extract embeddings from {speaker_voice_file_path}")
                return None, "error"   
            
            speaker, result, similarity = self.find_best_match(embeddings)
            self.logger.debug(f"Match result: {result}. speaker '{speaker['Name']}'. similarity {similarity}")
            self.vocoder.reset()
            
            return speaker, result, similarity
        except Exception as e:
            self.logger.log_exception(f"add_voice_sample error", e)
            return None, "error", 0
        finally:
            if remove_local_file and local_voice_file and os.path.isfile(local_voice_file):
                os.remove(local_voice_file)
