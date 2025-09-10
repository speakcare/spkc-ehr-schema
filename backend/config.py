# put config objects here
import logging
from speakcare_common import SpeakcareLogger


# Logger setup
api_logger = SpeakcareLogger('speackcare.emr.api')

# Configuration dictionary for initializing the EMR API
APP_BASE_ID = 'appRFbM7KJ2QwCDb6'
SpeakCareEmrApiconfig = {
    'baseId': APP_BASE_ID,
    'logger': api_logger
}
