import os
from speakcare_logging import SpeakcareLogger
import time


logger = SpeakcareLogger(__name__)

def __get_directory_path(dir_name):

    # check if absolute path or local path
    if os.path.isabs(dir_name) or dir_name.startswith("/"):
        # Full path (starts with / or the system's root directory)
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


def ensure_file_directory_exists(filename):
    # Extract the directory path from the file
    dir_name = os.path.dirname(filename)
    return ensure_directory_exists(dir_name)

def get_file_extension(filename):
    """Get the file extension from a given filename or path."""
    _, ext = os.path.splitext(filename)
    return ext

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


