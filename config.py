# put config objects here
import logging

# Logger setup
logger = logging.getLogger('speackcare.emr.api')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.propagate = True

# Configuration dictionary for initializing the EMR API
APP_BASE_ID = 'appRFbM7KJ2QwCDb6'
SpeakCareEmrApiconfig = {
    'baseId': APP_BASE_ID,
    'logger': logger
}
