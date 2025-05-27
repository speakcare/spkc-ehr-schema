from speakcare_logging import SpeakcareLogger
from pydub import AudioSegment
from abc import ABC, abstractmethod
import torch
import numpy as np
import os
from speakcare_audio import audio_convert_to_wav, audio_is_wav
from speechbrain.inference import EncoderClassifier
from resemblyzer import VoiceEncoder, preprocess_wav
from os_utils import os_get_filename_without_ext
from backend.speakcare_env import SpeakcareEnv
 

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
    def __init__(self, model="speechbrain/spkrec-ecapa-voxceleb"):
        super().__init__()
        self.converted_to_wav = False
        try:
            self.classifier = EncoderClassifier.from_hparams(
                source=model,
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


SpeakcareEnv.load_env()
VOCODER_MODEL = os.getenv("VOCODER_MODEL", "speechbrain/spkrec-ecapa-voxceleb")
class VocoderFactory:
    VOCODERS = ["speechbrain/spkrec-ecapa-voxceleb", "resemblyzer"]
    @staticmethod
    def create_vocoder(vocoder_model=None):
        vocoder_model = vocoder_model or VOCODER_MODEL
        if not vocoder_model in VocoderFactory.VOCODERS:
            raise ValueError(f"Invalid vocoder model '{vocoder_model}'")
        
        match vocoder_model.lower():
            case model if model.startswith("speechbrain"):
                return SpeechBrainVocoder(vocoder_model)
            case "resemblyzer":
                return ResemblyzerVocoder()
            case _:
                raise ValueError("Invalid vocoder model")
        
    @staticmethod
    def get_vocoder_model():
        return VOCODER_MODEL