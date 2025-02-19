from dotenv import load_dotenv
from os_utils import ensure_directory_exists
import os
from speakcare_logging import SpeakcareLogger

__env = {}
envInitialized = False
logger =  SpeakcareLogger(__name__)

class SpeakcareEnv:
    env_loaded = False
    local_output_root_dir = "out"
    backwards_compatible = False

    # working dirs
    audio_dir = ""
    texts_dir = ""
    charts_dir = ""
    diarizations_dir = ""
    transcriptions_dir = ""
    
    @staticmethod
    def prepare_env(env_file: str = "./.env"):
        if SpeakcareEnv.env_loaded:
            return
        if not SpeakcareEnv.env_loaded:
            if not load_dotenv(env_file):
                print(f"No {env_file} file found")
                exit(1)
        SpeakcareEnv.backwards_compatible = (os.getenv("BC_MODE", "false").lower() == "true")
        SpeakcareEnv.__prepare_output_dirs()
        SpeakcareEnv.env_loaded = True
        
            
    @staticmethod
    def __prepare_output_dirs():
        if SpeakcareEnv.env_loaded:
            return
        
        if not SpeakcareEnv.backwards_compatible:
            SpeakcareEnv.audio_dir = "audio"
            SpeakcareEnv.texts_dir = "texts"
            SpeakcareEnv.charts_dir = "charts"
            SpeakcareEnv.diarizations_dir = "diarizations"
            SpeakcareEnv.transcriptions_dir = "transcriptions"
        
        else:
            SpeakcareEnv.audio_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.audio_dir}"
            ensure_directory_exists(SpeakcareEnv.audio_dir)
            SpeakcareEnv.texts_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.texts_dir}"
            ensure_directory_exists(SpeakcareEnv.texts_dir)
            SpeakcareEnv.charts_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.charts_dir}"
            ensure_directory_exists(SpeakcareEnv.charts_dir)
            SpeakcareEnv.diarizations_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.diarizations_dir}"
            ensure_directory_exists(SpeakcareEnv.diarizations_dir)
            SpeakcareEnv.transcriptions_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.transcriptions_dir}"
            ensure_directory_exists(SpeakcareEnv.transcriptions_dir)

    @staticmethod
    def get_working_dirs(): 
        return [SpeakcareEnv.audio_dir, SpeakcareEnv.texts_dir, SpeakcareEnv.charts_dir, SpeakcareEnv.diarizations_dir, SpeakcareEnv.transcriptions_dir]  
