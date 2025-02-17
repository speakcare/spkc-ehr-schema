from dotenv import load_dotenv
from os_utils import ensure_directory_exists
import os

__env = {}
envInitialized = False

class SpeakcareEnv:
    env_loaded = False
    audio_dir = ""
    texts_dir = ""
    charts_dir = ""
    local_output_root_dir = "out"
    

    @staticmethod
    def prepare_env(env_file: str = "./.env"):
        if not SpeakcareEnv.env_loaded:
            if not load_dotenv(env_file):
                print(f"No {env_file} file found")
                exit(1)
            SpeakcareEnv.env_loaded = True
        SpeakcareEnv.__prepare_output_dirs()
        
            
    @staticmethod
    def __prepare_output_dirs():
        outputs = os.getenv("OUTPUTS", "local")
        if outputs == "s3":
            SpeakcareEnv.audio_dir = "audio"
            SpeakcareEnv.texts_dir = "texts"
            SpeakcareEnv.charts_dir = "charts"
        elif outputs == "local":
            SpeakcareEnv.audio_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.audio_dir}"
            ensure_directory_exists(SpeakcareEnv.audio_dir)
            SpeakcareEnv.texts_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.texts_dir}"
            ensure_directory_exists(SpeakcareEnv.texts_dir)
            SpeakcareEnv.charts_dir = f"{SpeakcareEnv.local_output_root_dir}/{SpeakcareEnv.charts_dir}"
            ensure_directory_exists(SpeakcareEnv.charts_dir)
