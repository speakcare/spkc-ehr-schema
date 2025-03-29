import os
from speakcare_emr_utils import EmrUtils
from speakcare_logging import SpeakcareLogger
from speakcare_env import SpeakcareEnv

SpeakcareEnv.load_env()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = SpeakcareLogger(__name__)
logger.info(f"Creating database in directory: {DB_DIRECTORY}")
EmrUtils.init_db(db_directory=DB_DIRECTORY, create_db=True)



