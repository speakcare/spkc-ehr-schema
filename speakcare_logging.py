import logging


# Generic logger creation function to be used by all modules
def create_logger(name: str, level: int = logging.INFO, propagate: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (file: %(filename)s, line: %(lineno)d)')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = propagate
    return logger