import os
import logging
import argparse
import numpy as np
import torch
import json
from pydub import AudioSegment
from speechbrain.inference import EncoderClassifier
from boto3_session import Boto3Session
from speakcare_env import SpeakcareEnv
from collections import defaultdict
from decimal import Decimal
from speakcare_logging import SpeakcareLogger
from os_utils import os_ensure_directory_exists

MIN_SEGMENT_DURATION = 500 # milliseconds


class SpeakcareRecognizer:
    def __init__(self, output_dir="output_segments"):
        self.output_dir = output_dir
        os_ensure_directory_exists(self.output_dir)

        self.b3session = Boto3Session.get_single_instance()
        self.logger = SpeakcareLogger(SpeakcareRecognizer.__name__)
        self.classifier: EncoderClassifier  = None
        try:
            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb"
            )
        except Exception as e:
            self.logger.error(f"Model load error: {e}")
            return {}
        self.speaker_segments = defaultdict(list)
        self.speaker_embeddings = defaultdict(list)
        self.speaker_matches = defaultdict(list)
        self.speaker_stats = {}
        self.processed = 0
        self.skipped = 0

    
    
    @staticmethod
    def cosine_similarity(vec1, vec2):
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def get_embeddings(self, audio_path, classifier: EncoderClassifier):
        try:
            with torch.no_grad():
                signal = classifier.load_audio(audio_path)
                embedding: torch.Tensor = classifier.encode_batch(signal)
                embedding_np = embedding.squeeze().cpu().numpy()
            return embedding_np
        except Exception as e:
            logging.error(f"Embedding error: {e}")
            return None

    def fetch_all_speakers(self):
        table_name = self.b3session.dynamo_get_table_name("speakers")
        table = self.b3session.dynamo_get_table(table_name)
        response = table.scan()
        return {item['Name']: item for item in response['Items']}

    @staticmethod
    def convert_to_decimal_list(numpy_array):
        return [Decimal(str(float(x))) for x in numpy_array]

    @staticmethod
    def convert_from_decimal_list(decimal_list):
        return np.array([float(x) for x in decimal_list], dtype=np.float32)

    def find_closest_speakers(self, embedding, known_speakers):
        similarities = []
        highest_unknown = None
        highest_unknown_similarity = -1
        
        for known_speaker_name, speaker in known_speakers.items():
            embeddings = speaker.get('EmbeddingVectors', [])
            for known_embedding in embeddings:
                embedding_vector = self.convert_from_decimal_list(known_embedding)
                similarity = self.cosine_similarity(embedding, embedding_vector)
                if known_speaker_name.startswith("Unknown-"):
                    if similarity > highest_unknown_similarity:
                        highest_unknown = (known_speaker_name, similarity)
                        highest_unknown_similarity = similarity
                else:
                    similarities.append((known_speaker_name, similarity))
        
        if highest_unknown:
            similarities.append(highest_unknown)
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities

    def map_segments_to_speakers(self, audio_file, transcript_file):
        try:
            audio = AudioSegment.from_file(audio_file)
            audio_length = len(audio)
        except Exception as e:
            self.logger.error(f"Audio load error: {e}")
            return {}
        transcript = None

        known_speakers = self.fetch_all_speakers()
        
        segment_speaker_counter = {}
        segment_counter = 0
        errors = []

       
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript = json.load(f) 
        except Exception as e:
            self.logger.error(f"Transcript read error from file '{transcript_file}': {e}")
            return {}
        
        audio_segments = transcript.get("results", {}).get("audio_segments", [])

        #for i in range(0, len(lines) - 1, 2):
        for audio_segment in audio_segments:
            start_time = audio_segment.get("start_time", 0)
            end_time = audio_segment.get("end_time", 0)
            if start_time >= end_time:
                    self.skipped += 1
                    continue
                
            speaker = audio_segment.get("speaker_label", "")
            content = audio_segment.get("transcript", "")
            start_ms = int(start_time * 1000)
            end_ms = min(int(end_time * 1000), audio_length)
            
            if start_ms >= audio_length or end_ms - start_ms < MIN_SEGMENT_DURATION:
                self.skipped += 1
                continue

            segment = audio[start_ms:end_ms]

            segment_speaker_counter[speaker] = segment_speaker_counter.get(speaker, 0) + 1
            segment_counter += 1

            segment_filename = f"segment-{segment_counter:03d}_spk{speaker}_{segment_speaker_counter[speaker]:03d}.wav"
            segment_path = os.path.join(self.output_dir, segment_filename)

            try:
                segment.export(segment_path, format="wav")
                
                segment_info = {
                    "file_path": segment_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "content": content
                }
                self.speaker_segments[speaker].append(segment_info)
                self.processed += 1
                
                embedding = self.get_embeddings(segment_path, self.classifier)
                if embedding is not None:
                    self.speaker_embeddings[speaker].append(embedding)
                    
                    closest_speakers = self.find_closest_speakers(embedding, known_speakers)
                    top_match = closest_speakers[0] if closest_speakers else None
                    self.speaker_matches[speaker].append(top_match)
                    
            except Exception as e:
                errors.append(f"Export error: {segment_filename}")
                self.skipped += 1

    def collect_speaker_stats(self):
        
        for speaker, segments in self.speaker_segments.items():
            total_duration = sum(seg["duration"] for seg in segments)
            avg_duration = total_duration / len(segments) if segments else 0
            word_count = sum(len(seg["content"].split()) for seg in segments)
            
            if speaker in self.speaker_embeddings and self.speaker_embeddings[speaker]:
                all_matches = [match[0][0] for match in self.speaker_matches[speaker] if match]
                match_counts = {}
                for match in all_matches:
                    match_counts[match] = match_counts.get(match, 0) + 1
                
                sorted_matches = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)
                most_likely_person = sorted_matches[0][0] if sorted_matches else "Unknown"
                match_confidence = sorted_matches[0][1] / len(all_matches) if sorted_matches and all_matches else 0
            else:
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
        
        return {
            "processed_segments": self.processed,
            "skipped_segments": self.skipped,
            "speaker_stats": self.speaker_stats
        }


    def recognize_speakers(self, audio_file, transcript_file):
        ''' 
            Takes a diarized transcript and original audio file, splits the audio into segments,
            extracts embeddings, and compares them to known speaker embeddings to identify speakers.
            Returns a dictionary containing the number of processed and skipped segments, and speaker stats.
        '''
        try:
            transcript_local_file, remove_transcript_file = self.b3session.s3_localize_file(transcript_file)
            audio_local_file, remove_audio_file = self.b3session.s3_localize_file(audio_file)
            self.map_segments_to_speakers(audio_file= audio_local_file, transcript_file= transcript_local_file)
            self.collect_speaker_stats()
        except Exception as e:
            self.logger.error(f"Recognition error: {e}")
            return {}
        finally:
            if remove_transcript_file:
                os.remove(transcript_local_file)
            if remove_audio_file:
                os.remove(audio_local_file)


        
        

    def generate_recognized_transcript(self, transcript_file, speaker_stats):
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            modified_lines = []
            for i in range(0, len(lines) - 1, 2):
                speaker_line = lines[i + 1]
                
                if ":" not in speaker_line:
                    continue
                
                speaker = speaker_line.split(":", 1)[0].strip()
                content = speaker_line.split(":", 1)[1].strip()
                
                most_likely_name = speaker_stats.get(speaker, {}).get('most_likely_person', speaker)
                
                modified_line = f"{most_likely_name.replace('spk_', 'name')}: {content}"
                modified_lines.append(modified_line)
            
            return "\n".join(modified_lines)
        
        except Exception as e:
            logging.error(f"Transcript generation error: {e}")
            return ""

    def add_speaker_embedding(self, speaker_name, audio_file):
        logger = logging.getLogger(__name__)
        
        try:
            classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb"
            )
            
            embedding = self.get_embeddings(audio_file, classifier)
            if embedding is None:
                logger.error(f"Failed to extract embedding from {audio_file}")
                return False
            
            embedding_decimal = self.convert_to_decimal_list(embedding)
            
            b3session = Boto3Session(SpeakcareEnv.get_working_dirs())
            table_name = b3session.dynamo_get_table_name("speakers")
            table = b3session.dynamo_get_table(table_name)
            
            speakers = self.fetch_all_speakers()
            if speaker_name in speakers:
                speaker: dict = speakers[speaker_name]
                embeddings: list = speaker.get('EmbeddingVectors', [])
                embeddings.append(embedding_decimal)
                
                table.update_item(
                    Key={'Name': speaker_name},
                    UpdateExpression="SET EmbeddingVectors = :e",
                    ExpressionAttributeValues={':e': embeddings}
                )
            else:
                table.put_item(
                    Item={
                        'Name': speaker_name,
                        'EmbeddingVectors': [embedding_decimal]
                    }
                )
            
            return True
        except Exception as e:
            logger.error(f"Embedding addition error: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Process audio, split by speaker, and analyze voice similarity.")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    split_parser = subparsers.add_parser('split', help='Split audio by segments and analyze speakers')
    split_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file.")
    split_parser.add_argument("--transcript", type=str, required=True, help="Path to the transcript file.")
    split_parser.add_argument("--output", type=str, default="output_segments", help="Output directory for segments.")
    split_parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold (0-1) for speaker matching.")
    split_parser.add_argument("--generate-transcript", action="store_true", help="Generate modified transcript with probable names")
    
    add_parser = subparsers.add_parser('add', help='Add a new speaker embedding to the database')
    add_parser.add_argument("--name", type=str, required=True, help="Name of the speaker.")
    add_parser.add_argument("--audio", type=str, required=True, help="Path to the audio file containing the speaker's voice.")
    
    args = parser.parse_args()

    recognizer = SpeakcareRecognizer()

    if args.command == 'split':
        results = recognizer.recognize_speakers(args.audio, args.transcript, args.output, args.threshold)
        
        print("\n=== Final Summary ===")
        if results:
            print(f"Successfully processed {results['processed_segments']} segments")
            print(f"Speaker identities:")
            for speaker, stats in results['speaker_stats'].items():
                print(f"  Speaker {speaker} → {stats['most_likely_person']} ({stats['match_confidence']*100:.1f}% confidence)")
            
            if args.generate_transcript:
                modified_transcript = recognizer.generate_recognized_transcript(args.transcript, results['speaker_stats'])
                output_transcript_path = os.path.join(args.output, "modified_transcript.txt")
                
                with open(output_transcript_path, 'w', encoding='utf-8') as f:
                    f.write(modified_transcript)
                
                print(f"\nGenerated modified transcript: {output_transcript_path}")
        else:
            print("Processing failed. Check the logs for details.")
    
    elif args.command == 'add':
        success = recognizer.add_speaker_embedding(args.name, args.audio)
        if success:
            print(f"Successfully added embedding for speaker '{args.name}'")
        else:
            print(f"Failed to add embedding. Check the logs for details.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()