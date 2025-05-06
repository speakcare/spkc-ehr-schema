import logging
import os, sys
import traceback
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.speakcare_env import SpeakcareEnv

# Load environment variables
SpeakcareEnv.load_env()

# Read the log level from the environment variable, defaulting to 'INFO'
logger_level = os.getenv('LOGGER_LEVEL', 'INFO').upper()
# Convert the string to a logging level
env_log_level = getattr(logging, logger_level, logging.INFO)


class CustomFormatter(logging.Formatter):
    LEVELNAME_MAP = {
        'WARNING': 'WARN',
        'INFO': 'INFO',
        'DEBUG': 'DEBUG',
        'ERROR': 'ERROR',
        'CRITICAL': 'CRIT',
    }

    def format(self, record):
        if record.levelname in self.LEVELNAME_MAP:
            record.levelname = self.LEVELNAME_MAP[record.levelname]
        return super().format(record)


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
        formatter = CustomFormatter('%(asctime)s - %(levelname)-5s: %(name)s - %(message)s (file: %(filename)s, line: %(lineno)d)')
        handler.setFormatter(formatter)
        self.addHandler(handler)
        self.propagate = propagate

    def log_exception(self, message: str, exception: Exception):
        self.error(f"{message}: {exception}")
        self.error(traceback.format_exc())  

