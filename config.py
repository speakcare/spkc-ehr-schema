# put config objects here
import logging

# Logger setup
logger = logging.getLogger('speackcare.emr.api')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (file: %(filename)s, line: %(lineno)d)')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = True

# TODO: provide logger config function

# Configuration dictionary for initializing the EMR API
APP_BASE_ID = 'appRFbM7KJ2QwCDb6'
SpeakCareEmrApiconfig = {
    'baseId': APP_BASE_ID,
    'logger': logger
}
