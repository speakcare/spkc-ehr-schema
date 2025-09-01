# put config objects here
import logging
from speakcare_logging import SpeakcareLogger


# Logger setup
api_logger = SpeakcareLogger('speackcare.emr.api')

# Configuration dictionary for initializing the EMR API
APP_BASE_ID = 'appRFbM7KJ2QwCDb6'

# Production configuration
SpeakCareEmrApiconfig = {
    'baseId': APP_BASE_ID,
    'logger': api_logger,
    'emr_api': None
}

def register_emr_api(api):
    SpeakCareEmrApiconfig['emr_api'] = api
