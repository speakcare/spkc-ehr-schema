import logging
from logging import Logger
from dotenv import load_dotenv
import os, sys
import traceback

# Load environment variables
load_dotenv()

# Read the log level from the environment variable, defaulting to 'INFO'
logger_level = os.getenv('LOGGER_LEVEL', 'INFO').upper()
# Convert the string to a logging level
env_log_level = getattr(logging, logger_level, logging.INFO)


class SpeakcareLogger(logging.Logger):
    def __init__(self, name: str, level: int = None, propagate: bool = False):
        super().__init__(name)
        _level = level if level is not None else env_log_level
        module_log_level = os.getenv(f'LOGGER_LEVEL.{name}')
        # check if there is a specific log level for the module
        if module_log_level:
            _level = getattr(logging, module_log_level.upper(), _level)

        self.setLevel(_level)
        handler = logging.StreamHandler()
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (file: %(filename)s, line: %(lineno)d)')
        handler.setFormatter(formatter)
        self.addHandler(handler)
        self.propagate = propagate

    def log_exception(self, message: str, exception: Exception):
        self.error(f"{message}: {exception}")
        self.error(traceback.format_exc())  

