import os
from backend.spkc_logging import SpeakcareLogger
import time


logger = SpeakcareLogger(__name__)

def __get_directory_path(dir_name):
    if os.path.isabs(dir_name):
        # Full path (starts with / or the system's root directory)
        return dir_name
    elif dir_name.startswith("./"):
        # Relative path (starts with ./)
        return dir_name
    else:
        # Local path (does not start with / or ./)
        return f"./{dir_name}"

def ensure_directory_exists(dir_name):
    # Extract the directory path from the file path
    _dir_path = __get_directory_path(dir_name)
    #directory = os.path.dirname(file_path)
    
    logger.debug(f"Verify directory {_dir_path} exists")
    # Create the directory if it does not exist
    if _dir_path and not os.path.exists(_dir_path):
        logger.debug(f"Creating directory {_dir_path}")
        os.makedirs(_dir_path, exist_ok=True)
    return _dir_path

class Timer:
    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.perf_counter()

    def stop(self):
        self.end_time = time.perf_counter()

    def elapsed_time(self):
        return self.end_time - self.start_time


