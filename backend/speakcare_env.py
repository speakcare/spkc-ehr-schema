'''
 This module should not import any other Speakcare modules to avoid circular imports !!!
 It should only be used to load environment variables and set the working directories.
'''
from dotenv import load_dotenv
import os

__env = {}
envInitialized = False

class SpeakcareEnv:
    __env_loaded = False
    __local_output_root_dir = "/tmp/speakcare"
    backwards_compatible = False

    # working dirs
    __audio_dir = "audio"
    __texts_dir = "texts"
    __charts_dir = "charts"
    __diarizations_dir = "diarizations"
    __transcriptions_dir = "transcriptions"
    __persons_dir = "persons"
    __test_dir = "test"
    __voice_samples_dir = os.path.join(__audio_dir,"samples") 
    __care_sessions_dir = os.path.join(__audio_dir,"sessions")
    __local_downloads_dir = os.path.join(__local_output_root_dir, "downloads")

    @staticmethod
    def get_audio_dir():
        return SpeakcareEnv.__audio_dir
    @staticmethod
    def get_audio_local_dir():
        return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__audio_dir}'
    
    @staticmethod
    def get_texts_dir():
        return SpeakcareEnv.__texts_dir
    @staticmethod
    def get_texts_local_dir():
        return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__texts_dir}'
    
    @staticmethod
    def get_charts_dir():
        return SpeakcareEnv.__charts_dir
    @staticmethod
    def get_charts_local_dir():
        return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__charts_dir}'
    
    @staticmethod
    def get_diarizations_dir():
        return SpeakcareEnv.__diarizations_dir
    @staticmethod
    def get_diarizations_local_dir():
        return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__diarizations_dir}'
    
    @staticmethod
    def get_transcriptions_dir():
        return SpeakcareEnv.__transcriptions_dir
    @staticmethod
    def get_transcriptions_local_dir():
        return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__transcriptions_dir}'
    
    @staticmethod
    def get_persons_dir():
        return SpeakcareEnv.__persons_dir
    @staticmethod
    def get_persons_local_dir():
        return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__persons_dir}'
    
    @staticmethod
    def get_test_dir():
        return SpeakcareEnv.__test_dir
        
    @staticmethod
    def get_voice_samples_dir():
        return SpeakcareEnv.__voice_samples_dir
    # @staticmethod
    # def get_voice_samples_local_dir():
    #     return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__voice_samples_dir}'
    
    @staticmethod
    def get_care_sessions_dir():
        return SpeakcareEnv.__care_sessions_dir
    # @staticmethod
    # def get_care_sessions_local_dir():
    #     return f'{SpeakcareEnv.__local_output_root_dir}/{SpeakcareEnv.__care_sessions_dir}'

    @staticmethod
    def get_local_downloads_dir():
        return SpeakcareEnv.__local_downloads_dir

    
    @staticmethod
    def load_env(env_file: str = None):
        if SpeakcareEnv.__env_loaded:
            return
        if not SpeakcareEnv.__env_loaded:
            if not env_file:
                env_file = os.getenv("ENV_FILE", "./.env")
            if not os.path.isfile(env_file):
                print(f"No {env_file} file found")
                exit(1)
            print(f"Loading environment variables from {env_file}")
            if not load_dotenv(env_file):
                print(f"No {env_file} file found")
                exit(1)
        SpeakcareEnv.backwards_compatible = (os.getenv("BC_MODE", "false").lower() == "true")
        SpeakcareEnv.__prepare_output_dirs()
        SpeakcareEnv.__env_loaded = True
        
            
    @staticmethod
    def __prepare_output_dirs():
        if SpeakcareEnv.__env_loaded:
            return      
        os.makedirs(SpeakcareEnv.get_audio_local_dir(), exist_ok=True)
        os.makedirs(SpeakcareEnv.get_texts_local_dir(), exist_ok=True)
        os.makedirs(SpeakcareEnv.get_charts_local_dir(), exist_ok=True)
        os.makedirs(SpeakcareEnv.get_diarizations_local_dir(), exist_ok=True)
        os.makedirs(SpeakcareEnv.get_transcriptions_local_dir(), exist_ok=True)
        os.makedirs(SpeakcareEnv.get_persons_local_dir(), exist_ok=True)
        os.makedirs(SpeakcareEnv.get_local_downloads_dir(), exist_ok=True)

        if SpeakcareEnv.backwards_compatible:
            # set the working directories to local directories
            SpeakcareEnv.__audio_dir = SpeakcareEnv.get_audio_local_dir()
            SpeakcareEnv.__texts_dir = SpeakcareEnv.get_texts_local_dir()
            SpeakcareEnv.__charts_dir = SpeakcareEnv.get_charts_local_dir()
            SpeakcareEnv.__diarizations_dir = SpeakcareEnv.get_diarizations_local_dir()
            SpeakcareEnv.__transcriptions_dir = SpeakcareEnv.get_transcriptions_local_dir()
            SpeakcareEnv.__persons_dir = SpeakcareEnv.get_persons_local_dir()
        
    @staticmethod
    def get_local_root_dir():
        return SpeakcareEnv.__local_output_root_dir

    @staticmethod
    def get_working_dirs(): 
        return [
                 SpeakcareEnv.__audio_dir, 
                 SpeakcareEnv.__texts_dir, 
                 SpeakcareEnv.__charts_dir, 
                 SpeakcareEnv.__diarizations_dir, 
                 SpeakcareEnv.__transcriptions_dir,
                 SpeakcareEnv.__persons_dir,
                 SpeakcareEnv.__test_dir,
                 SpeakcareEnv.__voice_samples_dir,
                 SpeakcareEnv.__care_sessions_dir
               ]  
