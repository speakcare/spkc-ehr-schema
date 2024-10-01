import os
from speakcare_logging import create_logger

logger = create_logger(__name__)

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

