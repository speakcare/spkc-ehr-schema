import os
import argparse
import json
import shutil
from boto3_session import Boto3Session
from collections import defaultdict
from speakcare_logging import SpeakcareLogger
from os_utils import os_ensure_directory_exists, os_get_filename_without_ext
from pydantic import BaseModel, ValidationError
from typing import List
from speakcare_env import SpeakcareEnv
from speakcare_vocoder import SpeakcareVocoder, VocoderFactory
from speakcare_embeddings import SpeakcareEmbeddings, SpeakerRole

SpeakcareEnv.load_env()
AUDIO_MIN_SEGMENT_DURATION = int(os.getenv("AUDIO_MIN_SEGMENT_DURATION", 500)) # milliseconds


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

    
    def __init__(self, vocoder: SpeakcareVocoder, embedding_store: SpeakcareEmbeddings, work_dir="output_segments"):
        self.work_dir = work_dir
        os_ensure_directory_exists(self.work_dir)

        self.b3session = Boto3Session.get_single_instance()
        self.logger = SpeakcareLogger(TranscriptRecognizer.__name__)
        self.speaker_segments = defaultdict(list)
        #self.speaker_embeddings = defaultdict(list)
        self.speaker_matches = defaultdict(list)
        self.speaker_stats = {}
        self.processed_segments = 0
        self.skipped_segments = 0
        self.mapped_segments = 0
        self.transcript_file = None
        self.transcript = None
        self.vocoder: SpeakcareVocoder  = vocoder
        self.embeddings_store: SpeakcareEmbeddings = embedding_store

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
                
            speaker_label = audio_segment.get("speaker_label",SpeakcareEmbeddings.UNKNOWN_SPEAKER)
            content = audio_segment.get("transcript", "")
            start_ms = int(start_time * 1000)
            end_ms = min(int(end_time * 1000), audio_length)
            
            if start_ms >= audio_length or end_ms - start_ms < AUDIO_MIN_SEGMENT_DURATION:
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
                    most_likely_person = sorted_matches[0][0] if sorted_matches else SpeakcareEmbeddings.UNKNOWN_SPEAKER
                    match_confidence = sorted_matches[0][1] / len(all_matches) if sorted_matches and all_matches else 0
                else:
                    self.logger.warning(f"No matches found for speaker {speaker}")
                    most_likely_person = SpeakcareEmbeddings.UNKNOWN_SPEAKER
                    match_confidence = 0
            else:
                self.logger.warning(f"No embeddings found for speaker {speaker}")
                most_likely_person = SpeakcareEmbeddings.UNKNOWN_SPEAKER
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
                    most_likely_name = self.speaker_stats.get(speaker, {}).get('most_likely_person', f"{speaker} ('{SpeakcareEmbeddings.UNKNOWN_SPEAKER}')")
                    audio_segment["speaker_label"] = most_likely_name
                    audio_segment["speaker_role"] = self.embeddings_store.get_speaker_role(most_likely_name).value
        
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

    def get_transcript(self):
        return self.transcript
    
    def generate_recognized_text_transcript(self):
        ''' Generate a text transcript with the most likely speaker names '''

        if not self.transcript:
            raise Exception("Transcript not loaded")
        
        lines = []
        try:
            audio_segments = self.transcript.get("results", {}).get("audio_segments", [])
            for audio_segment in audio_segments:
                speaker_label = audio_segment.get("speaker_label", SpeakcareEmbeddings.UNKNOWN_SPEAKER)
                speaker_role = audio_segment.get("speaker_role", SpeakerRole.UNKNOWN)
                transcript = audio_segment.get("transcript", "")

                line = f"speaker:{speaker_label} role:{speaker_role}: {transcript}"
                lines.append(line)
            return "\n".join(lines)
        except Exception as e:
            self.logger.log_exception(f"Transcript generation error", e)
            return ""
    
    def recognize(self, audio_file, transcript_file, keep_segment_files=False) -> dict:
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
            return self.transcript
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
    speaker_add_parser.add_argument("--role", type=str, required=True, choices=[SpeakerRole.PATIENT.value, SpeakerRole.NURSE.value], help="Role of speaker.")
    speaker_add_parser.add_argument("--workdir", type=str, default=SpeakcareEnv.get_audio_local_dir(), help="Work directory for recognizer vocoder.")

    speaker_lookup_parser = speaker_subparsers.add_parser('lookup', help='Lookup a speaker in the database')
    speaker_lookup_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file containing the speaker's voice.")    
    speaker_lookup_parser.add_argument("--workdir", type=str, default=SpeakcareEnv.get_audio_local_dir(), help="Work directory for recognizer vocoder.")


    args = parser.parse_args()

    work_dir = args.workdir
    vocoder = VocoderFactory.create_vocoder()
    

    if args.command == 'recognize':
        embedding_store = SpeakcareEmbeddings(vocoder=vocoder,matching_similarity_threshold= args.threshold)
        recognizer = TranscriptRecognizer(vocoder=vocoder, work_dir=work_dir, embedding_store= embedding_store)
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
        embedding_store = SpeakcareEmbeddings(vocoder=vocoder)
        if args.subcommand == 'lookup':
            speaker, result, similarity = embedding_store.lookup_speaker(args.audio)
            if speaker:
                print(f"Speaker found: '{speaker['Name']}' role {speaker['Role']} with similarity {similarity}")
            else:
                print(f"Speaker not found. Check the logs for details.")
        elif args.subcommand == 'add':
            role = SpeakerRole(args.role)
            speaker, result = embedding_store.add_voice_sample(speaker_voice_file_path= args.audio, 
                                                            speaker_name= args.name, speaker_role= role)
            if speaker and result in ["added", "created"]:
                print(f"Successfully added embedding for speaker '{args.name}' role '{role}' result: {result}'")
            else:
                print(f"Failed to add embedding. result: {result} . Check the logs for details.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()