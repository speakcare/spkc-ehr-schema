import os
from speakcare_logging import SpeakcareLogger
import time
from datetime import datetime, timezone


logger = SpeakcareLogger(__name__)

def __get_directory_path(dir_name):

    # check if absolute path or local path
    if os.path.isabs(dir_name) or dir_name.startswith("/"):
        # Full path (starts with / or the system's root directory)
        return dir_name
    else:
        # Local path (does not start with / or ./)
        return f"./{dir_name}"

def os_ensure_directory_exists(dir_name):
    # Extract the directory path from the file path
    _dir_path = __get_directory_path(dir_name)
    
    logger.debug(f"Verify directory {_dir_path} exists")
    # Create the directory if it does not exist
    if _dir_path and not os.path.exists(_dir_path):
        logger.debug(f"Creating directory {_dir_path}")
        os.makedirs(_dir_path, exist_ok=True)
    return _dir_path


def os_ensure_file_directory_exists(filename):
    # Extract the directory path from the file
    dir_name = os.path.dirname(filename)
    return os_ensure_directory_exists(dir_name)

def os_get_file_extension(filename):
    """Get the file extension from a given filename or path."""
    _, ext = os.path.splitext(filename)
    return ext

def os_get_filename_without_ext(filename):
    """Get the file name from a given filename or path."""
    name, _ = os.path.splitext(os.path.basename(filename))
    return name

def os_sanitize_name(filename:str):
    """Sanitize a name to make it safe for filenames and other identifiere. invalid character with '-'."""
    return "".join(c if (c.isalnum() or c in "._- ") else "-" for c in filename)


def os_concat_current_time(prefix:str):
    utc_now = datetime.now(timezone.utc)
    # Format the datetime as a string with milliseconds without timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H-%M-%S-%f')[:-3] # remove last 3 digits
    return f'{prefix}-{utc_string}'

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


