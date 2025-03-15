from abc import ABC, abstractmethod
import os
import argparse
import numpy as np
import torch
import json
import shutil
from pydub import AudioSegment
from speechbrain.inference import EncoderClassifier
from resemblyzer import VoiceEncoder, preprocess_wav
from boto3_session import Boto3Session
from collections import defaultdict
from decimal import Decimal
from speakcare_logging import SpeakcareLogger
from os_utils import os_ensure_directory_exists, os_get_filename_without_ext, os_get_file_extension
from enum import Enum as PyEnum
from datetime import datetime
from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError
from typing import List
from speakcare_env import SpeakcareEnv
from speakcare_audio import audio_convert_to_wav, audio_is_wav

class SpeakerType(PyEnum):
    PATIENT = 'Patient'
    NURSE = 'Nurse'
    UNKNOWN = 'Unknown'


MIN_SEGMENT_DURATION = 500 # milliseconds

'''
class SpeakcareVocoder(ABC):
Abstract class for extracting embeddings from audio files and comparing them.
'''
class SpeakcareVocoder(ABC):
    def __init__(self):
        self._logger = SpeakcareLogger(SpeakcareVocoder.__name__)
        self._audio_path = ""
        self._audio: AudioSegment = None
        self._audio_length = 0
        
    def load_audio_file(self, audio_path):
        self.reset()
        try:
            self._audio_path = audio_path
            self._audio = AudioSegment.from_file(self._audio_path)
            self._audio_length = len(self._audio)
        except Exception as e:
            self._logger.log_exception(f"Audio load error", e)
            raise e
        
    def reset(self):
        self._audio_path = ""
        self._audio = None
        self._audio_length = 0
        
    def get_audio(self):
        return self._audio
    
    def get_audio_length(self):
        return self._audio_length
    
    def get_audio_file_name(self):
        return os.path.basename(self._audio_path)
    
    def get_segment_file_path(self, index: int, start_ms: int, end_ms: int, output_dir:str):
        audio_file_name = os_get_filename_without_ext(self._audio_path)
        segment_filename = f"{audio_file_name}_{index}-{start_ms}-{end_ms}.wav"
        segment_path = os.path.join(output_dir, segment_filename) 
        return segment_path
        
    @abstractmethod
    def get_embedding(self):
        ''' 
        Get the embedding of the audio file 
        '''
        raise NotImplementedError()
        
    @abstractmethod
    def get_segment_embedding(self, index:int,  start_ms:int, end_ms:int, segment_output_dir:str, keep_segments=False):
        '''
        Get the embedding for the segment of the audio file between start_ms and end_ms
        If keep_segments is True, keep the segments for debugging

        start_ms: start time in milliseconds
        end_ms: end time in milliseconds
        segment_output_path: path to put the segment audio file
        keep_segments: keep the segment audio file (for debugging)
        '''
        raise NotImplementedError()

    def convert_from_decimal_list(self, decimal_list):
        return np.array([float(x) for x in decimal_list], dtype=np.float32)
        
   
    def __cosine_similarity(self, vec1, vec2):
        vec1norm = np.linalg.norm(vec1)
        vec2norm = np.linalg.norm(vec2)
        if vec1norm == 0 or vec2norm == 0:
            return 0
        return np.dot(vec1, vec2) / (vec1norm * vec2norm)
    
    def similarity(self, vec1, vec2):
        return self.__cosine_similarity(vec1, vec2)
    
    def isidenticial(self, vec1, vec2):
        return np.array_equal(vec1, vec2)


'''
class SpeechBrainVocoder(SpeakcareVocoder)
Vocoder implementation using SpeechBrain's speaker recognition model.
'''
class SpeechBrainVocoder(SpeakcareVocoder):
    def __init__(self):
        super().__init__()
        self.converted_to_wav = False
        try:
            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb"
            )
        except Exception as e:
            self._logger.log_exception(f"Classifier load error", e)
            raise e

    def load_audio_file(self, audio_path):
        self.reset()
        if not audio_is_wav(audio_path):
            audio_path = audio_convert_to_wav(audio_path)
            self.converted_to_wav = True
        super().load_audio_file(audio_path)

    def reset(self):
        if self.converted_to_wav and self._audio_path and os.path.isfile(self._audio_path):
            self._logger.debug(f'Removing converted wav file {self._audio_path}')
            os.remove(self._audio_path)
            self.converted_to_wav = False
        super().reset()
        
    def __get_embedding(self, audio_path):
        self._logger.debug(f'Getting embedding for {audio_path}')
        try:
            with torch.no_grad():
                signal = self.classifier.load_audio(audio_path)
                embedding: torch.Tensor = self.classifier.encode_batch(signal)
                embedding_np = embedding.squeeze().cpu().numpy()
            return embedding_np
        except Exception as e:
            self._logger.log_exception(f"Embedding error file '{audio_path}'", e)
            return None

    def get_embedding(self):
        if not self._audio_path:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")
        
        return self.__get_embedding(self._audio_path)

                
    def get_segment_embedding(self, index:int,  start_ms:int, end_ms:int, segment_output_dir:str, keep_segments=False):
        if not self._audio:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")        
        
        self._logger.debug(f'Getting segment embedding {start_ms}-{end_ms}')
        try:
            segment_path = self.get_segment_file_path(index, start_ms, end_ms, segment_output_dir)
            segment = self._audio[start_ms:end_ms]
            segment.export(segment_path, format="wav")
            embeddings = self.__get_embedding(segment_path)
            if not keep_segments and os.path.isfile(segment_path):
                os.remove(segment_path)
            return embeddings
        except Exception as e:
            self._logger.log_exception(f"Segment embedding error", e)
            return None
        
'''
class ResemblyzerVocoder(SpeakcareVocoder)
Vocoder implementation using Resemblyzer's speaker recognition model.
'''
class ResemblyzerVocoder(SpeakcareVocoder):
    WAV_NORMALIZATION_FACTOR = 32768.0

    def __init__(self):
        super().__init__()
        try:
            self.encoder = VoiceEncoder(verbose=False)
        except Exception as e:
            self._logger.log_exception(f"Encoder load error", e)
            raise e
        
        
    def __get_normalized_audio_data(self, audio):
        return np.array(audio.get_array_of_samples(), dtype=np.float32) /self.WAV_NORMALIZATION_FACTOR

    def get_embedding(self):
        if not self._audio:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")
        self._logger.debug(f'Getting embedding.')
        try:
            normalized_audio_data = self.__get_normalized_audio_data(self._audio) # np.array(_audio.get_array_of_samples(), dtype=np.float32) / 32768.0
            wav = preprocess_wav(normalized_audio_data)
            embedding = self.encoder.embed_utterance(wav)
            return embedding
        except Exception as e:
            self._logger.log_exception(f"Embedding error", e)
            return None


    def get_segment_embedding(self, index:int, start_ms:int, end_ms:int, segment_output_dir:str, keep_segments=False):
        if not self._audio:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")
        self._logger.debug(f'Getting segment embedding {start_ms}-{end_ms}')
        try:
            audio_segment = self._audio[start_ms:end_ms]
            # get as numpy array and normalize to 16 bits
            normalized_audio_data = self.__get_normalized_audio_data(audio_segment)# np.array(audio_segment.get_array_of_samples(), dtype=np.float32) / 32768.0
            wav = preprocess_wav(normalized_audio_data)
            embedding = self.encoder.embed_utterance(wav)
            if keep_segments:
                segment_path = self.get_segment_file_path(index, start_ms, end_ms, segment_output_dir)
                audio_segment.export(segment_path, format="wav")
            return embedding
        except Exception as e:
            self._logger.log_exception(f"Segment embedding error", e)
            return None



class SpeakcareEmbeddings:
    def __init__(self, 
                 vocoder: SpeakcareVocoder, 
                 matching_similarity_threshold=0.75, 
                 addition_similarity_threshold=0.95
                 ):
        try:
            self.logger = SpeakcareLogger(type(self).__name__)
            self.b3session = Boto3Session.get_single_instance()
            self.speakers_table_name = self.b3session.dynamo_get_table_name("speakers")
            self.vocoder = vocoder
            self.matching_similarity_threshold = matching_similarity_threshold
            self.addition_similarity_threshold = addition_similarity_threshold
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
    
    def __create_or_update_speaker(self, speaker_embedding, speaker_type: SpeakerType, speaker_name):
        """Match or create a new speaker in the speakers table."""
        # Check for identical embeddings
        try:
            for known_speaker_name, speaker in self.known_speakers.items():
                embeddings = speaker.get('EmbeddingVectors', [])
                type = speaker.get('Type', '')
                for idx, known_embedding in enumerate(embeddings):
                    embedding_vector = self.vocoder.convert_from_decimal_list(known_embedding) 
                    similarity = self.vocoder.similarity(speaker_embedding, embedding_vector)
                    if self.vocoder.isidenticial(speaker_embedding, embedding_vector):
                        self.logger.warning(f"Identical embedding found for speaker '{type}': '{known_speaker_name}' and new speaker '{speaker_type.value}': '{speaker_name}'. No changes made.")
                        return speaker, "identical"
                    elif similarity >= self.addition_similarity_threshold and known_speaker_name != speaker_name:
                        self.logger.warning(f"High similarity found between new speaker {speaker_name} and existing speaker {known_speaker_name} with similarity {similarity}")

            # Add the new embedding to the speaker
            if speaker_name in self.known_speakers:
                speaker = self.__add_embedding_to_speaker(speaker_name, speaker_embedding)
                self.logger.info(f"Added new embedding to existing speaker: {speaker_name}")
                return speaker, "added"
            else:
                speaker = self.__add_new_speaker(speaker_name, speaker_embedding, speaker_type)
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
                type = speaker.get('Type', '')
                self.logger.debug(f"Checking speaker {known_speaker_name} with {len(embeddings)} embeddings")
                for known_embedding in embeddings:
                    embedding_vector = self.vocoder.convert_from_decimal_list(known_embedding)
                    similarity = self.vocoder.similarity(speaker_embedding, embedding_vector)
                    self.logger.debug(f"cosine similarity: {similarity} with '{known_speaker_name}' of type: '{type}'")
                    if similarity >= self.matching_similarity_threshold:
                        self.logger.debug(f"Found high similarity: {similarity} with '{known_speaker_name}' of type: '{type}'")
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
        
 

    def __add_new_speaker(self, speaker_name, embedding, speaker_type: SpeakerType):
        """Save speaker embedding to DynamoDB."""
        embedding_decimal = [Decimal(str(value)) for value in embedding]
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        item = {
            "EmbeddingVectors": [embedding_decimal],
            "Name": speaker_name,
            "Type": speaker_type.value,
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


    def add_voice_sample(self, speaker_voice_file_path, speaker_name:str, speaker_type: SpeakerType):
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
            speaker, result = self.__create_or_update_speaker(embeddings, speaker_type, speaker_name=_speaker_name)
            self.vocoder.reset()
            # refresh the known speakers
            self.known_speakers = self.__fetch_all_speakers()
            
            self.logger.info(f"add_voice_sample: create_speaker attepted for speaker '{speaker_type.value}': '{_speaker_name}'. Result: '{result}' with speaker '{speaker['Name']}'")
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


# Pydantic objects for the transcript JSON format validation
class TranscriptAudioSegment(BaseModel):
    id: int
    transcript: str
    start_time: str
    end_time: str
    speaker_label: str

class TranscriptResults(BaseModel):
    audio_segments: List[TranscriptAudioSegment]

class Transcript(BaseModel):
    results: TranscriptResults


class TranscriptRecognizer:

    
    def __init__(self, vocoder: SpeakcareVocoder, matching_similarity_threshold = None, work_dir="output_segments"):
        self.work_dir = work_dir
        os_ensure_directory_exists(self.work_dir)

        self.b3session = Boto3Session.get_single_instance()
        self.logger = SpeakcareLogger(TranscriptRecognizer.__name__)
        self.classifier: EncoderClassifier  = None
        self.speaker_segments = defaultdict(list)
        #self.speaker_embeddings = defaultdict(list)
        self.speaker_matches = defaultdict(list)
        self.speaker_stats = {}
        self.processed_segments = 0
        self.skipped_segments = 0
        self.mapped_segments = 0
        self.transcript_file = None
        self.transcript = None
        self.vocoder = vocoder
        self.embeddings_store = SpeakcareEmbeddings(vocoder=self.vocoder, matching_similarity_threshold=matching_similarity_threshold)

        # state indicators
        self.mapped = False
        self.stats_calculated = False
        self.speakers_updated = False            


    def __load_audio_and_transcript(self, audio_file, transcript_file):
        ''' Load the audio file and transcript json file '''
        try:
            ''' Load the audio file and get its length '''
            self.vocoder.load_audio_file(audio_file)
            audio_length = self.vocoder.get_audio_length()
        except Exception as e:
            self.logger.log_exception(f"Audio load error", e)
            raise e
        
        self.transcript = None

       # try to open the transcript file and read it as json
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                 self.transcript = json.load(f) 
                 self.transcript_file = transcript_file
        except Exception as e:
            self.logger.log_exception(f"Transcript read error from file '{transcript_file}'", e)
            raise e
        
        # try to validate the transcript json format
        try:
            validated = Transcript(** self.transcript)
        except ValidationError as e:
            self.logger.log_exception(f"Transcript validation error", e)
            raise e


    def __map_segments_to_speakers(self, keep_segment_files=False):
        ''' 
            Iterate the audio segments and extract embeddings for each speaker 
            Map each segment to the speaker with the highest similarity
            If keep_segment_files is True, save the audio segments to the output directory for debugging
        '''

        if not self.transcript or not self.vocoder.get_audio():
            raise Exception("Audio or transcript not loaded")

        audio_length = self.vocoder.get_audio_length()
        segment_speaker_counter = {}
        errors = []
        self.processed_segments = 0
        self.skipped_segments = 0
        self.mapped_segments = 0

        segments_output_dir = os.path.join(self.work_dir, os_get_filename_without_ext(self.vocoder.get_audio_file_name()), "segments")
        os_ensure_directory_exists(segments_output_dir)
        audio_segments =  self.transcript.get("results", {}).get("audio_segments", [])

        for segment_counter, audio_segment in enumerate(audio_segments):
            start_time = float(audio_segment.get("start_time", 0)) 
            end_time = float(audio_segment.get("end_time", 0))
            if start_time >= end_time:
                    self.skipped_segments += 1
                    continue
                
            speaker_label = audio_segment.get("speaker_label", "Unknown")
            content = audio_segment.get("transcript", "")
            start_ms = int(start_time * 1000)
            end_ms = min(int(end_time * 1000), audio_length)
            
            if start_ms >= audio_length or end_ms - start_ms < MIN_SEGMENT_DURATION:
                self.skipped_segments += 1
                continue

            segment_speaker_counter[speaker_label] = segment_speaker_counter.get(speaker_label, 0) + 1

            try:
                segment_embedding = self.vocoder.get_segment_embedding(index=segment_counter, start_ms= start_ms, end_ms=end_ms, 
                                                                       segment_output_dir= segments_output_dir, 
                                                                       keep_segments=keep_segment_files)
                if segment_embedding is None:
                    self.skipped_segments += 1
                    continue

                segment_path = self.vocoder.get_segment_file_path(segment_counter, start_ms, end_ms, segments_output_dir)
                segment_info = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": end_time - start_time,
                        "content": content,
                        **({"file_path": segment_path} if keep_segment_files is not None else {}), #only include file path if it was saved
                }
                self.speaker_segments[speaker_label].append(segment_info)
                self.logger.debug(f'Calling find_best_match for speaker {speaker_label} segment {segment_counter}')    
                best_match_speaker, result, similarity = self.embeddings_store.find_best_match(speaker_embedding=segment_embedding)
                
                if best_match_speaker:
                    self.logger.debug(f"Match result for segment {segment_counter}: '{speaker_label}' result: {result}. speaker '{best_match_speaker['Name']}'. similarity {similarity}")
                    self.speaker_matches[speaker_label].append(best_match_speaker)
                    self.mapped_segments += 1
                else:
                    self.logger.debug(f"No match found for segment {segment_counter}: speaker {speaker_label}. result: {result}")
                self.processed_segments += 1

            except Exception as e:
                err = f"Get segment {segment_counter} embeddings error: {start_ms}-{end_ms}"
                errors.append(err)
                self.skipped_segments += 1
                self.logger.log_exception(err, e)
            

        if not keep_segment_files and os.path.isdir(segments_output_dir):
            self.logger.debug(f"Removing segments directory {segments_output_dir}")
            shutil.rmtree(segments_output_dir)
        
        self.logger.info(f"Mapping done: found {segment_counter}, skipped {self.skipped_segments}, processed {self.processed_segments}, mapped {self.mapped_segments}")
        self.mapped = True            
        return errors

    
    def __calc_speaker_stats(self):
        ''' Calculate speaker stats based on the segments and embeddings '''

        if not self.transcript or not self.vocoder.get_audio():
            raise Exception("Audio or transcript not loaded")
        if not self.mapped:
            raise Exception("Segments not mapped to speakers. Call __map_segments_to_speakers() first")
        
        for speaker, segments in self.speaker_segments.items():
            total_duration = sum(seg["duration"] for seg in segments)
            avg_duration = total_duration / len(segments) if segments else 0
            word_count = sum(len(seg["content"].split()) for seg in segments)
            
            # if speaker in self.speaker_embeddings and self.speaker_embeddings[speaker]:
            if speaker in self.speaker_matches and self.speaker_matches[speaker]:
                all_matches = [match['Name'] for match in self.speaker_matches[speaker] if match]
                if all_matches:
                    match_counts = {}
                    # count how many matches the speaker has with each known speaker
                    for match in all_matches:
                        match_counts[match] = match_counts.get(match, 0) + 1
                    
                    sorted_matches = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)
                    most_likely_person = sorted_matches[0][0] if sorted_matches else "Unknown"
                    match_confidence = sorted_matches[0][1] / len(all_matches) if sorted_matches and all_matches else 0
                else:
                    self.logger.warning(f"No matches found for speaker {speaker}")
                    most_likely_person = "Unknown"
                    match_confidence = 0
            else:
                self.logger.warning(f"No embeddings found for speaker {speaker}")
                most_likely_person = "Unknown"
                match_confidence = 0
            
            self.speaker_stats[speaker] = {
                "segment_count": len(segments),
                "total_duration": total_duration,
                "avg_duration": avg_duration,
                "word_count": word_count,
                "words_per_second": word_count / total_duration if total_duration > 0 else 0,
                "most_likely_person": most_likely_person,
                "match_confidence": match_confidence
            }
        
        self.stats_calculated = True
        return self.get_results()

        
    def __update_recognized_speakers(self):
        ''' Update the speaker labels in the transcript with the most likely speaker names '''
        
        if not self.transcript:
            raise Exception("Transcript not loaded")
        if not self.stats_calculated:
            raise Exception("Speaker stats not calculated. Call __calc_speaker_stats() first")
        
        try:        
            audio_segments = self.transcript.get("results", {}).get("audio_segments", [])

            for audio_segment in audio_segments:
                speaker = audio_segment.get("speaker_label", "")
                if speaker:
                    most_likely_name = self.speaker_stats.get(speaker, {}).get('most_likely_person', f'{speaker} ("Unknown")')
                    audio_segment["speaker_label"] = most_likely_name
        
        except Exception as e:
            self.logger.log_exception(f"Transcript generation error", e)
            return {}
        
        self.speakers_updated = True
        return audio_segments
    
    def get_results(self):
        return {
            "processed_segments": self.processed_segments,
            "skipped_segments": self.skipped_segments,
            "mapped_segments": self.mapped_segments,
            "speaker_stats": self.speaker_stats
        }
    
    def get_audio_segments(self):
         if not self.transcript:
             return None
         else:
            return self.transcript.get("results", {}).get("audio_segments", [])


    def generate_recognized_text_transcript(self):
        ''' Generate a text transcript with the most likely speaker names '''

        if not self.transcript:
            raise Exception("Transcript not loaded")
        
        lines = []
        try:
            audio_segments = self.transcript.get("results", {}).get("audio_segments", [])
            for audio_segment in audio_segments:
                start_time = float(audio_segment.get("start_time", 0))
                end_time = float(audio_segment.get("end_time", 0))
                speaker_label = audio_segment.get("speaker_label", "Unknown")
                transcript = audio_segment.get("transcript", "")
                speaker_item = self.embeddings_store.get_speaker(speaker_label)
                speaker_type = speaker_item.get("Type", "Unknown") if speaker_item else "Unknown"

                line = f"{start_time} - {end_time}: '{speaker_label}' ({speaker_type}): {transcript}"
                lines.append(line)
            return "\n".join(lines)
        except Exception as e:
            self.logger.log_exception(f"Transcript generation error", e)
            return ""
    
    def recognize(self, audio_file, transcript_file, keep_segment_files=False):
        ''' 
            Takes a diarized transcript and original audio file, splits the audio into segments,
            extracts embeddings, and compares them to known speaker embeddings to identify speakers.
            Returns a dictionary containing the number of processed and skipped segments, and speaker stats.
        '''
        transcript_local_file = None
        remove_transcript_file = False
        audio_local_file = None
        remove_audio_file = False
        try:
            transcript_local_file, remove_transcript_file = self.b3session.s3_localize_file(transcript_file)
            audio_local_file, remove_audio_file = self.b3session.s3_localize_file(audio_file)
            if not transcript_local_file or not audio_local_file:
                raise Exception("Failed to localize files")
            
            self.vocoder.reset()
            self.__load_audio_and_transcript(audio_file= audio_local_file, transcript_file= transcript_local_file)
            self.__map_segments_to_speakers(keep_segment_files=keep_segment_files)
            self.__calc_speaker_stats()
            self.__update_recognized_speakers()
        except Exception as e:
            self.logger.log_exception(f"Recognition error", e)
            raise e
        finally:
            if remove_transcript_file and transcript_local_file and os.path.isfile(transcript_local_file): 
                os.remove(transcript_local_file)
            if remove_audio_file and audio_local_file and os.path.isfile(audio_local_file):
                os.remove(audio_local_file)
    




def main():
    SpeakcareEnv.load_env()
    parser = argparse.ArgumentParser(description="Process audio, split by speaker, and analyze voice similarity.")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    recognize_parser = subparsers.add_parser('recognize', help='Recognize speakers in the audio file and update transcript')
    recognize_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file.")
    recognize_parser.add_argument("--transcript", type=str, required=True, help="Path to the transcript file.")
    recognize_parser.add_argument("--outdir", type=str, default=SpeakcareEnv.get_transcriptions_local_dir(), help="Output directory for transcription.")
    recognize_parser.add_argument("--workdir", type=str, default=SpeakcareEnv.get_audio_local_dir(), help="Work directory for recognizer vocoder.")
    recognize_parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold (0-1) for speaker matching.")
    recognize_parser.add_argument("--keep-segments", action="store_true", help="Keeps the segment files for debug")
    recognize_parser.add_argument("--generate-transcript", action="store_true", help="Generate final transcript with probable names")
    
    speaker_parser = subparsers.add_parser('speaker', help='Manage speaker embeddings in the database')
    speaker_subparsers = speaker_parser.add_subparsers(dest='subcommand', help='Sub command to execute')

    speaker_add_parser = speaker_subparsers.add_parser('add', help='Add a new speaker embedding')
    speaker_add_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file containing the speaker's voice.")
    speaker_add_parser.add_argument("--name", type=str, required=True, help="Name of the speaker.")
    speaker_add_parser.add_argument("--type", type=str, required=True, choices=[SpeakerType.PATIENT.value, SpeakerType.NURSE.value], help="Type of speaker.")
    speaker_add_parser.add_argument("--workdir", type=str, default=SpeakcareEnv.get_audio_local_dir(), help="Work directory for recognizer vocoder.")

    speaker_lookup_parser = speaker_subparsers.add_parser('lookup', help='Lookup a speaker in the database')
    speaker_lookup_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file containing the speaker's voice.")    
    speaker_lookup_parser.add_argument("--workdir", type=str, default=SpeakcareEnv.get_audio_local_dir(), help="Work directory for recognizer vocoder.")


    args = parser.parse_args()

    work_dir = args.workdir
    vocoder = SpeechBrainVocoder()
    # vocoder = ResemblyzerVocoder()
    embedding_store = SpeakcareEmbeddings(vocoder=vocoder, matching_similarity_threshold= args.threshold)

    if args.command == 'recognize':
        recognizer = TranscriptRecognizer(vocoder=vocoder, work_dir=work_dir, matching_similarity_threshold= args.threshold)
        recognizer.recognize(audio_file= args.audio, transcript_file= args.transcript, keep_segment_files=True)
        results = recognizer.get_results()
        
        print("\n=== Final Summary ===")
        if results:
            print(f"Successfully processed {results['processed_segments']} segments. Mapped {results['mapped_segments']} segments to speakers.")
            print(f"Speaker identities:")
            for speaker, stats in results['speaker_stats'].items():
                print(f"  Speaker {speaker} → {stats['most_likely_person']} ({stats['match_confidence']*100:.1f}% confidence)")
            
            if args.generate_transcript:
                generated_transcript = recognizer.generate_recognized_text_transcript()
                output_transcript_path = os.path.join(args.outdir, "transcript.txt")
                
                with open(output_transcript_path, 'w', encoding='utf-8') as f:
                    f.write(generated_transcript)
                
                print(f"\nGenerated transcript: {output_transcript_path}")
        else:
            print("Processing failed. Check the logs for details.")
    
    elif args.command == 'speaker':
        if args.subcommand == 'lookup':
            speaker, result, similarity = embedding_store.lookup_speaker(args.audio)
            if speaker:
                print(f"Speaker found: '{speaker['Name']}' of type {speaker['Type']} with similarity {similarity}")
            else:
                print(f"Speaker not found. Check the logs for details.")
        elif args.subcommand == 'add':
            type = SpeakerType(args.type)
            speaker, result = embedding_store.add_voice_sample(speaker_voice_file_path= args.audio, 
                                                            speaker_name= args.name, speaker_type= type)
            if speaker and result in ["added", "created"]:
                print(f"Successfully added embedding for speaker '{args.name}' type '{type}' result: {result}'")
            else:
                print(f"Failed to add embedding. result: {result} . Check the logs for details.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()