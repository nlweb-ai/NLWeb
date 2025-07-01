import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load env variables
load_dotenv()

def test_direct_logging():
    # Get output directory
    output_dir = os.getenv('NLWEB_OUTPUT_DIR')
    if not output_dir:
        print("NLWEB_OUTPUT_DIR not set!")
        return
        
    # Set up log directory
    log_dir = os.path.join(output_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure test logger
    test_logger = logging.getLogger("test_logger")
    test_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    test_logger.handlers = []
    
    # Add console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    test_logger.addHandler(console)
    
    # Add file handler with explicit flush
    log_file = os.path.join(log_dir, "test_logger.log")
    file_handler = RotatingFileHandler(log_file, mode='a', maxBytes=1024*1024, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    test_logger.addHandler(file_handler)
    
    # Write test messages
    test_logger.debug("This is a DEBUG test message")
    test_logger.info("This is an INFO test message")
    test_logger.warning("This is a WARNING test message")
    test_logger.error("This is an ERROR test message")
    
    # Force flush
    for handler in test_logger.handlers:
        handler.flush()
        
    print(f"Test complete - check log file at: {log_file}")
    
    # Read the file back to verify content
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        print(f"Log file content:\n{content}")
    except Exception as e:
        print(f"Error reading log file: {e}")

if __name__ == "__main__":
    test_direct_logging()