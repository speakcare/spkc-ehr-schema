from abc import ABC, abstractmethod
import os
import argparse
import numpy as np
import torch
import json
import random
from pydub import AudioSegment
from speechbrain.inference import EncoderClassifier
from resemblyzer import VoiceEncoder, preprocess_wav
from boto3_session import Boto3Session
#from speakcare_env import SpeakcareEnv
from collections import defaultdict
from decimal import Decimal
from speakcare_logging import SpeakcareLogger
from os_utils import os_ensure_directory_exists, os_get_filename_without_ext
from enum import Enum as PyEnum
from datetime import datetime
from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError
from typing import List
from speakcare_env import SpeakcareEnv

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
    def __init__(self, output_dir="output_segments"):
        self._logger = SpeakcareLogger(type(self).__name__)
        self._audio_path = ""
        self._audio: AudioSegment = None
        self._audio_length = 0
        self._output_dir = output_dir
        os_ensure_directory_exists(self._output_dir)
        
    def load_audio_file(self, audio_path):
        try:
            self._audio_path = audio_path
            self._audio = AudioSegment.from_file(self._audio_path)
            self._audio_length = len(self._audio)
        except Exception as e:
            self._logger.log_exception(f"Audio load error: {e}")
            raise e
        
    def reset(self):
        self._audio_path = ""
        self._audio = None
        self._audio_length = 0
        
    def get_audio(self):
        return self._audio
    
    def get_audio_length(self):
        return self._audio_length
    
        
    @abstractmethod
    def get_embedding(self):
        ''' 
        Get the embedding of the audio file 
        '''
        raise NotImplementedError()
        
    @abstractmethod
    def get_segment_embedding(self, start_ms, end_ms, segment_output_path = None):
        '''
        Get the embedding for the segment of the audio file between start_ms and end_ms
        If segment_output_path is provided, save the segment to that path for debugging
        start_ms: start time in milliseconds
        end_ms: end time in milliseconds
        segment_output_path: path to save the segment to - use it for debugging
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
    def __init__(self, output_dir):
        super().__init__(output_dir=output_dir)
        try:
            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb"
            )
        except Exception as e:
            self._logger.log_exception(f"Classifier load error: {e}")
            raise e

    def __get_embedding(self, audio_path):
        try:
            with torch.no_grad():
                signal = self.classifier.load_audio(audio_path)
                embedding: torch.Tensor = self.classifier.encode_batch(signal)
                embedding_np = embedding.squeeze().cpu().numpy()
            return embedding_np
        except Exception as e:
            self._logger.log_exception(f"Embedding error file '{audio_path}': {e}")
            return None

    def get_embedding(self):
        if not self._audio_path:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")
        
        return self.__get_embedding(self._audio_path)

                
    def get_segment_embedding(self, start_ms, end_ms, segment_output_path = None):
        if not self._audio:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")        
        try:
            rnd = random.randint(1000, 9999) # make it random to avoid conflicts
            segment = self._audio[start_ms:end_ms]
            audio_file_name = os_get_filename_without_ext(self._audio_path)
            segment_filename = f"{audio_file_name}-{start_ms}-{end_ms}.{rnd}.wav"
            segment_path = os.path.join(self._output_dir, segment_filename)
            segment.export(segment_path, format="wav")
            embeddings = self.__get_embedding(segment_path)
            if not segment_output_path:
                os.remove(segment_path)
            else:
                os.rename(segment_path, segment_output_path)
            return embeddings
        except Exception as e:
            self._logger.log_exception(f"Segment embedding error: {e}")
            return None
        
'''
class ResemblyzerVocoder(SpeakcareVocoder)
Vocoder implementation using Resemblyzer's speaker recognition model.
'''
class ResemblyzerVocoder(SpeakcareVocoder):
    WAV_NORMALIZATION_FACTOR = 32768.0

    def __init__(self,output_dir):
        super().__init__(output_dir=output_dir)
        try:
            self.encoder = VoiceEncoder(verbose=False)
        except Exception as e:
            self._logger.log_exception(f"Encoder load error: {e}")
            raise e
        
        
    def __get_normalized_audio_data(self, audio):
        return np.array(audio.get_array_of_samples(), dtype=np.float32) /self.WAV_NORMALIZATION_FACTOR

    def get_embedding(self):
        if not self._audio:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")
        try:
            # _audio = AudioSegment.from_file(audio_path) if audio_path else self.__audio
            normalized_audio_data = self.__get_normalized_audio_data(self._audio) # np.array(_audio.get_array_of_samples(), dtype=np.float32) / 32768.0
            wav = preprocess_wav(normalized_audio_data)
            embedding = self.encoder.embed_utterance(wav)
            return embedding
        except Exception as e:
            self._logger.log_exception(f"Embedding error: {e}")
            return None


    def get_segment_embedding(self, start_ms, end_ms, segment_output_path = None):
        if not self._audio:
            self._logger.error("Unable to get embedding. Audio file not loaded. Call load_audio_file() first.")
            raise Exception("Audio file not loaded")
        try:
            audio_segment = self._audio[start_ms:end_ms]
            # get as numpy array and normalize to 16 bits
            normalized_audio_data = self.__get_normalized_audio_data(audio_segment)# np.array(audio_segment.get_array_of_samples(), dtype=np.float32) / 32768.0
            wav = preprocess_wav(normalized_audio_data)
            embedding = self.encoder.embed_utterance(wav)
            if segment_output_path:
                audio_segment.export(segment_output_path, format="wav")
            return embedding
        except Exception as e:
            self._logger.log_exception(f"Segment embedding error: {e}")
            return None



class SpeakcareEmbeddings:
    def __init__(self, 
                 vocoder: SpeakcareVocoder, 
                 matching_similarity_threshold=0.75, 
                 addition_similarity_threshold=0.95
                 ):
        try:
            self.b3session = Boto3Session.get_single_instance()
            self.logger = SpeakcareLogger(type(self).__name__)
            self.speakers_table_name = self.b3session.dynamo_get_table_name("speakers")
            self.vocoder = vocoder
            self.matching_similarity_threshold = matching_similarity_threshold
            self.addition_similarity_threshold = addition_similarity_threshold
            self.known_speakers = self.fetch_all_speakers()
        except Exception as e:
            self.logger.log_exception(f"Initialization error: {e}")
            raise e

    def fetch_all_speakers(self):
        """Fetch all embeddings from a DynamoDB table."""
        table = self.b3session.dynamo_get_table(self.speakers_table_name)
        response = table.scan()
        return {item['Name']: item for item in response['Items']}
       

    def get_speaker(self, speaker_name):
        """Get speaker from a specific table."""
        return self.known_speakers.get(speaker_name, None)  
    
    def create_or_update_speaker(self, speaker_embedding, speaker_type: SpeakerType, speaker_name):
        """Match or create a new speaker in a specific table."""
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
                speaker = self.add_embedding_to_speaker(speaker_name, speaker_embedding)
                self.logger.info(f"Added new embedding to existing speaker: {speaker_name}")
                return speaker, "added"
            else:
                speaker = self.add_new_speaker(speaker_name, speaker_embedding, speaker_type)
                self.logger.info(f"New speaker created: {speaker_name}")
                return speaker, "created"
        except Exception as e:
            self.logger.log_exception(f"Create or update speaker error: {e}")
            return None, "error"

    
    def find_best_match(self, speaker_name, speaker_embedding):
        """Match or create a new speaker in a specific table."""
        try:
            self.logger.debug(f"Matching speaker embedding for '{speaker_name}' against {len(self.known_speakers)} known speakers")
            best_match = None
            highest_similarity = -1
            for known_speaker_name, speaker in self.known_speakers.items():
                embeddings = speaker.get('EmbeddingVectors', [])
                type = speaker.get('Type', '')
                self.logger.debug(f"Checking speaker {known_speaker_name} embeddings {len(embeddings)}")
                for known_embedding in embeddings:
                    self.logger.debug(f"Checking specific embedding {len(known_embedding)}")
                    embedding_vector = self.vocoder.convert_from_decimal_list(known_embedding)
                    similarity = self.vocoder.similarity(speaker_embedding, embedding_vector)
                    self.logger.debug(f"cosine similarity: {similarity} for '{speaker_name}' with '{known_speaker_name}' of type: '{type}'")
                    if similarity >= self.matching_similarity_threshold:
                        self.logger.debug(f"Found high similarity: {similarity} for '{speaker_name}' with '{known_speaker_name}' of type: '{type}'")
                        if similarity > highest_similarity:
                            best_match = speaker
                            highest_similarity = similarity

            if best_match:
                self.logger.debug(f"Match found: '{speaker_name}' is '{best_match['Name']}' with similarity {highest_similarity}")
                return best_match, "matched"
            else:
                self.logger.debug(f"No match found: '{speaker_name}'")
                return None, "unmatched"
        except Exception as e:
            self.logger.log_exception(f"Find best match error: {e}")
            return None, "error"
  

    def add_embedding_to_speaker(self, speaker_name, embedding):
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
        
 

    def add_new_speaker(self, speaker_name, embedding, speaker_type: SpeakerType):
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
            
        _speaker_name = speaker_name.replace(" ", "_")
        self.vocoder.load_audio_file(speaker_voice_file_path)
        embeddings = self.vocoder.get_embedding()
        if embeddings is None:
            self.logger.error(f"Failed to extract embeddings from {speaker_voice_file_path}")
            return None, "error"        
        speaker, result = self.create_or_update_speaker(embeddings, speaker_type, speaker_name=_speaker_name)
        self.vocoder.reset()
        # refresh the known speakers
        self.known_speakers = self.fetch_all_speakers()
        
        self.logger.info(f"add_voice_sample: create_speaker attepted for speaker '{speaker_type.value}': '{_speaker_name}'. Result: '{result}' with speaker '{speaker['Name']}'")
        return speaker, result


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

    
    def __init__(self, vocoder: SpeakcareVocoder, output_dir="output_segments"):
        self.output_dir = output_dir
        os_ensure_directory_exists(self.output_dir)

        self.b3session = Boto3Session.get_single_instance()
        self.logger = SpeakcareLogger(TranscriptRecognizer.__name__)
        self.classifier: EncoderClassifier  = None
        self.speaker_segments = defaultdict(list)
        #self.speaker_embeddings = defaultdict(list)
        self.speaker_matches = defaultdict(list)
        self.speaker_stats = {}
        self.processed = 0
        self.skipped = 0
        self.transcript_file = None
        self.transcript = None
        self.vocoder = vocoder
        self.embeddings_store = SpeakcareEmbeddings(vocoder=self.vocoder)


    def load_audio_and_transcript(self, audio_file, transcript_file):
        ''' Load the audio file and transcript json file '''
        try:
            ''' Load the audio file and get its length '''
            self.vocoder.load_audio_file(audio_file)
            audio_length = self.vocoder.get_audio_length()
        except Exception as e:
            self.logger.log_exception(f"Audio load error: {e}")
            raise e
        
        self.transcript = None

       # try to open the transcript file and read it as json
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                 self.transcript = json.load(f) 
                 self.transcript_file = transcript_file
        except Exception as e:
            self.logger.log_exception(f"Transcript read error from file '{transcript_file}': {e}")
            raise e
        
        # try to validate the transcript json format
        try:
            validated = Transcript(** self.transcript)
        except ValidationError as e:
            self.logger.log_exception(f"Transcript validation error: {e}")
            raise e


    def map_segments_to_speakers(self, keep_segment_files=False):
        ''' 
            Iterate the audio segments and extract embeddings for each speaker 
            Map each segment to the speaker with the highest similarity
            If keep_segment_files is True, save the audio segments to the output directory for debugging
        '''

        if not self.transcript or not self.vocoder.get_audio():
            raise Exception("Audio or transcript not loaded")

        audio_length = self.vocoder.get_audio_length()
        segment_speaker_counter = {}
        segment_counter = 0
        errors = []

        
        audio_segments =  self.transcript.get("results", {}).get("audio_segments", [])

        for audio_segment in audio_segments:
            start_time = audio_segment.get("start_time", 0)
            end_time = audio_segment.get("end_time", 0)
            if start_time >= end_time:
                    self.skipped += 1
                    continue
                
            speaker_label = audio_segment.get("speaker_label", "Unknown")
            content = audio_segment.get("transcript", "")
            start_ms = int(start_time * 1000)
            end_ms = min(int(end_time * 1000), audio_length)
            
            if start_ms >= audio_length or end_ms - start_ms < MIN_SEGMENT_DURATION:
                self.skipped += 1
                continue

            # segment = audio[start_ms:end_ms]

            segment_speaker_counter[speaker_label] = segment_speaker_counter.get(speaker_label, 0) + 1
            segment_counter += 1

            segment_path = None
            if keep_segment_files:
                segment_filename = f"segment-{segment_counter:03d}_spk{speaker_label}_{segment_speaker_counter[speaker_label]:03d}.wav"
                segment_path = os.path.join(self.output_dir, segment_filename)

            try:
                #segment.export(segment_path, format="wav")
                segment_embedding = self.vocoder.get_segment_embedding(start_ms, end_ms, segment_path)
                if segment_embedding is None:
                    self.skipped += 1
                    continue
            except Exception as e:
                err = f"Get segment embeddings error: {segment_filename}"
                errors.append(err)
                self.skipped += 1
                self.logger.log_exception(err)
            
            segment_info = {
                    # "file_path": segment_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "content": content,
                    **({"file_path": segment_path} if segment_path is not None else {}), #only include file path if it was saved
            }
            self.speaker_segments[speaker_label].append(segment_info)
            self.processed += 1
                
            best_match_speaker = self.embeddings_store.find_best_match(speaker_embedding=segment_embedding)# __find_closest_speakers(embedding, known_speakers)
            if best_match_speaker:
                self.speaker_matches[speaker_label].append(best_match_speaker)
                    
        self.vocoder.reset()
        return errors

    def get_results(self):
        return {
            "processed_segments": self.processed,
            "skipped_segments": self.skipped,
            "speaker_stats": self.speaker_stats
        }
    
    def get_audio_segments(self):
         if not self.transcript:
             return None
         else:
            return self.transcript.get("results", {}).get("audio_segments", [])
    
    def calc_speaker_stats(self):
        ''' Calculate speaker stats based on the segments and embeddings '''

        if not self.transcript or not self.vocoder.get_audio():
            raise Exception("Audio or transcript not loaded")
        
        for speaker, segments in self.speaker_segments.items():
            total_duration = sum(seg["duration"] for seg in segments)
            avg_duration = total_duration / len(segments) if segments else 0
            word_count = sum(len(seg["content"].split()) for seg in segments)
            
            # if speaker in self.speaker_embeddings and self.speaker_embeddings[speaker]:
            if speaker in self.speaker_matches and self.speaker_matches[speaker]:
                all_matches = [match[0] for match in self.speaker_matches[speaker] if match]
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
        
        return self.get_results()

        
    def update_recognized_speakers(self):
        ''' Update the speaker labels in the transcript with the most likely speaker names '''
        
        if not self.transcript:
            raise Exception("Transcript not loaded")
        try:        
            audio_segments = self.transcript.get("results", {}).get("audio_segments", [])

            for audio_segment in audio_segments:
                speaker = audio_segment.get("speaker_label", "")
                if speaker:
                    most_likely_name = self.speaker_stats.get(speaker, {}).get('most_likely_person', f'{speaker} ("Unknown")')
                    audio_segment["speaker_label"] = most_likely_name
        
        except Exception as e:
            self.logger.log_exception(f"Transcript generation error: {e}")
            return {}
        
        return audio_segments
    
    def generate_recognized_text_transcript(self):
        ''' Generate a text transcript with the most likely speaker names '''

        if not self.transcript:
            raise Exception("Transcript not loaded")
        
        lines = []
        try:
            audio_segments = self.transcript.get("results", {}).get("audio_segments", [])
            for audio_segment in audio_segments:
                start_time = audio_segment.get("start_time", 0)
                end_time = audio_segment.get("end_time", 0)
                speaker_label = audio_segment.get("speaker_label", "Unknown")
                transcript = audio_segment.get("transcript", "")
                speaker_item = self.embeddings_store.get_speaker(speaker_label)
                speaker_type = speaker_item.get("Type", "Unknown") if speaker_item else "Unknown"

                line = f"{start_time} - {end_time}: '{speaker_label}' ({speaker_type}): {transcript}"
                lines.append(line)
            return "\n".join(lines)
        except Exception as e:
            self.logger.log_exception(f"Transcript generation error: {e}")
            return ""
    
    def recognize(self, audio_file, transcript_file):
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
            self.load_audio_and_transcript(audio_file= audio_local_file, transcript_file= transcript_local_file)
            self.map_segments_to_speakers()
            self.calc_speaker_stats()
            self.update_recognized_speakers()
        except Exception as e:
            self.logger.log_exception(f"Recognition error: {e}")
            raise e
        finally:
            if remove_transcript_file and transcript_local_file and os.path.isfile(transcript_local_file): 
                os.remove(transcript_local_file)
            if remove_audio_file and audio_local_file and os.path.isfile(audio_local_file):
                os.remove(audio_local_file)
    




def main():
    parser = argparse.ArgumentParser(description="Process audio, split by speaker, and analyze voice similarity.")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    split_parser = subparsers.add_parser('recognize', help='Recognize speakers in the audio file and update transcript')
    split_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file.")
    split_parser.add_argument("--transcript", type=str, required=True, help="Path to the transcript file.")
    split_parser.add_argument("--output", type=str, default="output_segments", help="Output directory for segments.")
    split_parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold (0-1) for speaker matching.")
    split_parser.add_argument("--generate-transcript", action="store_true", help="Generate modified transcript with probable names")
    
    add_parser = subparsers.add_parser('speaker', help='Manage speaker embeddings in the database')
    add_parser.add_argument("--name", type=str, required=True, help="Name of the speaker.")
    add_parser.add_argument("--type", type=str, required=True, choices=[SpeakerType.PATIENT.value, SpeakerType.NURSE.value], help="Type of speaker.")
    add_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file containing the speaker's voice.")
    
    args = parser.parse_args()

    output_dir = SpeakcareEnv.get_audio_local_dir()
    vocoder = SpeechBrainVocoder(output_dir="output_segments")
    recognizer = TranscriptRecognizer(vocoder, output_dir)
    embedding_store = SpeakcareEmbeddings(vocoder)

    if args.command == 'recognize':
        recognizer.recognize(args.audio, args.transcript, args.output, args.threshold)
        results = recognizer.get_results()
        
        print("\n=== Final Summary ===")
        if results:
            print(f"Successfully processed {results['processed_segments']} segments")
            print(f"Speaker identities:")
            for speaker, stats in results['speaker_stats'].items():
                print(f"  Speaker {speaker} → {stats['most_likely_person']} ({stats['match_confidence']*100:.1f}% confidence)")
            
            if args.generate_transcript:
                generated_transcript = recognizer.generate_recognized_text_transcript()
                output_transcript_path = os.path.join(args.output, "modified_transcript.txt")
                
                with open(output_transcript_path, 'w', encoding='utf-8') as f:
                    f.write(generated_transcript)
                
                print(f"\nGenerated modified transcript: {output_transcript_path}")
        else:
            print("Processing failed. Check the logs for details.")
    
    elif args.command == 'add':
        type = SpeakerType(args.type)
        speaker, result = embedding_store.add_voice_sample(speaker_voice_file_path= args.audio, 
                                                           speaker_name= args.name, speaker_type= type)
        if speaker:
            print(f"Successfully added embedding for speaker '{args.name} type '{type}' result: {result}'")
        else:
            print(f"Failed to add embedding. Check the logs for details.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()