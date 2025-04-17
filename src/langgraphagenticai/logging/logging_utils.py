import logging
import functools
import time
import os

# Ensure the logs directory exists
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOG_DIR, 'app.log')

logging.basicConfig(
    level=logging.INFO,
    format="\n{'='*20}\n}%(asctime)s - %(name)s - %(levelname)s - %(message)s\n{'='*20}\n",
    handlers=[
        logging.StreamHandler(), # Logs to console
        logging.FileHandler(LOG_FILE_PATH) # Logs to a file in the logs directory
    ]
)

logger = logging.getLogger(__name__)

def log_entry_exit(func):
    """
    A decorator that logs the entry and exit of a function.
    It also logs the execution time.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"\n{'='*20}\n:Entering: {func_name}\n{'='*20}\n")
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.info(f"\n{'='*20}\n:Exiting: {func_name} (Execution Time: {execution_time:.4f} seconds)\n{'='*20}\n")
            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.error(f"{'='*20}:Error Exception in {func_name}: {e} (Execution Time: {execution_time:.4f} seconds)", exc_info=True)
            raise
    return wrapper
