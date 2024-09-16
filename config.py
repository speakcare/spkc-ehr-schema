# put config objects here
import logging
from speakcare_logging import create_logger


# Logger setup
api_logger = create_logger('speackcare.emr.api')

# Configuration dictionary for initializing the EMR API
APP_BASE_ID = 'appRFbM7KJ2QwCDb6'
SpeakCareEmrApiconfig = {
    'baseId': APP_BASE_ID,
    'logger': api_logger
}
