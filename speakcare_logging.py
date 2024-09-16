import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Read the log level from the environment variable, defaulting to 'INFO'
logger_level = os.getenv('LOGGER_LEVEL', 'INFO').upper()
# Convert the string to a logging level
env_log_level = getattr(logging, logger_level, logging.INFO)

print(f'Logger level set to {logger_level} {env_log_level}')

# Generic logger creation function to be used by all modules
def create_logger(name: str, level: int = None, propagate: bool = False) -> logging.Logger:
    _level = level if level is not None else env_log_level
    logger = logging.getLogger(name)
    logger.setLevel(_level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (file: %(filename)s, line: %(lineno)d)')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = propagate
    return logger