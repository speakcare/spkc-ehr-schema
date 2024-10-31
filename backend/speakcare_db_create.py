from dotenv import load_dotenv
import os
from speakcare_emr_utils import EmrUtils
from speakcare_logging import create_logger
load_dotenv()
DB_DIRECTORY = os.getenv("DB_DIRECTORY", "db")

logger = create_logger(__name__)
logger.info(f"Creating database in directory: {DB_DIRECTORY}")
EmrUtils.init_db(db_directory=DB_DIRECTORY, create_db=True)



