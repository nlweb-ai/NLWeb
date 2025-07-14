import yaml
import os
import queue
import threading
import time
import atexit
from typing import Dict, Any, Optional
from .logger import LogLevel, LoggerUtility


class LoggingConfig:
    """Helper class to load and manage logging configuration from YAML file"""
    
    def __init__(self, config_path: str = "config/config_logging.yaml"):
        # Try to find the config file in multiple locations
        self.config_path = self._find_config_file(config_path)
        self.config = self._load_config()
        self._ensure_log_directory()
    
    def _find_config_file(self, config_path: str) -> str:
        """Find the config file by checking multiple possible locations"""
        # If the path is absolute and exists, use it
        if os.path.isabs(config_path) and os.path.exists(config_path):
            return config_path
        
        # Check for NLWEB_CONFIG_DIR environment variable
        config_dir = os.getenv('NLWEB_CONFIG_DIR')
        if config_dir:
            full_path = os.path.join(config_dir, os.path.basename(config_path))
            if os.path.exists(full_path):
                return full_path
        
        # Try relative to current working directory
        if os.path.exists(config_path):
            return config_path
            
        # Try relative to the logger module directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Go up to find the NLWeb root directory and then to config
        # logger -> misc -> python -> code -> NLWeb
        nlweb_root = current_dir
        for _ in range(4):  # Go up 4 levels
            nlweb_root = os.path.dirname(nlweb_root)
        
        config_dir = os.path.join(nlweb_root, 'config')
        full_path = os.path.join(config_dir, os.path.basename(config_path))
        if os.path.exists(full_path):
            return full_path
        
        # If nothing found, return the original path (will use defaults)
        return config_path
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Warning: Logging config file not found at {self.config_path}")
            print(f"Using default logging configuration (INFO level)")
            return self._get_default_config()
        except Exception as e:
            print(f"Error loading logging config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if file loading fails"""
        return {
            "logging": {
                "default_level": "INFO",
                "log_directory": "logs",  # Default to 'logs' folder
                "modules": {},
                "global": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "console_output": True,
                    "file_output": True
                }
            }
        }
    
    def _ensure_log_directory(self):
        """Resolve log directory path (but don't create it yet)"""
        log_dir = self.config["logging"].get("log_directory", "logs")
        
        # Check for NLWEB_OUTPUT_DIR environment variable
        output_dir = os.getenv('NLWEB_OUTPUT_DIR')
        if output_dir:
            # Create logs directory under the output directory
            log_dir = os.path.join(output_dir, os.path.basename(log_dir))
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                print(f"Created log directory: {log_dir}")
            
        # Store the resolved directory (but don't create it yet)
        self.log_directory = log_dir
    
    def get_module_config(self, module_name: str) -> Dict[str, Any]:
        """Get configuration for a specific module"""
        modules = self.config["logging"].get("modules", {})
        return modules.get(module_name, {})
    
    def get_logger(self, module_name: str) -> LoggerUtility:
        """Create and return a configured logger for the specified module"""
        module_config = self.get_module_config(module_name)
        global_config = self.config["logging"].get("global", {})
        
        # Get log level from environment variable if set
        env_var = module_config.get("env_var")
        env_level = os.getenv(env_var) if env_var else None
        
        # Get active profile from environment variable (only if set)
        active_profile_name = os.getenv("NLWEB_LOGGING_PROFILE")
        profile_level = None
        if active_profile_name:
            active_profile = self.get_profile(active_profile_name)
            profile_level = active_profile.get("default_level") if active_profile else None
    
        # Determine log level - priority order:
        # 1. Environment variable if set
        # 2. Profile-specific default level (only if profile is set)
        # 3. Module-specific default level if defined
        # 4. Global default level as fallback
        # 5. Ultimately fallback to INFO
        if env_level:
            level_str = env_level
        elif profile_level:
            level_str = profile_level
        else:
            # Fall back to module-specific level, then global default
            level_str = module_config.get("default_level", 
                       self.config["logging"].get("default_level", "INFO"))
        
        # Convert string level to LogLevel enum
        try:
            default_level = LogLevel[level_str.upper()]
        except KeyError:
            default_level = LogLevel.INFO
        
        # Get log file path - Use self.log_directory which respects NLWEB_OUTPUT_DIR
        log_file = None
        if global_config.get("file_output", True):
            log_filename = module_config.get("log_file", f"{module_name}.log")
            log_file = os.path.join(self.log_directory, log_filename)
        
        # Get format string
        format_string = global_config.get("file_format" if log_file else "format")
        
        # Create and return logger
        return LoggerUtility(
            name=module_name,
            level=default_level,
            format_string=format_string,
            log_file=log_file,
            console_output=global_config.get("console_output", True)
        )
    
    def get_profile(self, profile_name: str = "development") -> Dict[str, Any]:
        """Get settings for a specific profile"""
        profiles = self.config.get("profiles", {})
        return profiles.get(profile_name, profiles.get("development", {}))
    
    def apply_profile(self, profile_name: str = "development"):
        """Apply a specific profile's settings"""
        profile = self.get_profile(profile_name)
        
        # Update global settings with profile settings
        if "default_level" in profile:
            self.config["logging"]["default_level"] = profile["default_level"]
        
        if "console_output" in profile:
            self.config["logging"]["global"]["console_output"] = profile["console_output"]
        
        if "file_output" in profile:
            self.config["logging"]["global"]["file_output"] = profile["file_output"]
    
    def set_all_loggers_level(self, level: str):
        """Set all loggers to the same level"""
        level = level.upper()
        if level not in LogLevel.__members__:
            raise ValueError(f"Invalid log level: {level}. Must be one of {list(LogLevel.__members__.keys())}")
        
        # Update default level
        self.config["logging"]["default_level"] = level
        
        # Update all module levels
        for module_name in self.config["logging"].get("modules", {}):
            self.config["logging"]["modules"][module_name]["default_level"] = level
        
        print(f"Set all loggers to {level} level")
    
    def get_all_env_vars(self) -> Dict[str, str]:
        """Get all environment variables and their current values"""
        env_vars = {}
        for module_name, module_config in self.config["logging"].get("modules", {}).items():
            if "env_var" in module_config:
                env_var = module_config["env_var"]
                env_vars[env_var] = os.getenv(env_var, module_config.get("default_level", "INFO"))
        return env_vars


# Global cache for lazy loggers and background thread management
_lazy_loggers = {}
_logging_config = None
_async_log_processor = None

# Removed redundant imports; moved to the top of the file.

def get_logging_config(config_path: str = "config/config_logging.yaml") -> LoggingConfig:
    """Get or create the singleton logging configuration"""
    global _logging_config
    if _logging_config is None:
        _logging_config = LoggingConfig(config_path)
    return _logging_config


class AsyncLogProcessor:
    """Background processor for handling log writes asynchronously"""
    
    def __init__(self, flush_interval=1.0, max_queue_size=1000):
        self.log_queue = queue.Queue(maxsize=max_queue_size)
        self.flush_interval = flush_interval
        self.shutdown_event = threading.Event()
        self.worker_thread = None
        self.real_loggers = {}  # Cache of actual LoggerUtility instances
        
    def start(self):
        """Start the background worker thread"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            # Register cleanup on exit
            atexit.register(self.shutdown)
    
    def _worker(self):
        """Background worker that processes queued log messages"""
        last_flush = time.time()
        
        while not self.shutdown_event.is_set():
            try:
                # Try to get a log record with timeout
                try:
                    log_record = self.log_queue.get(timeout=0.1)
                except queue.Empty:
                    # Check if we need to flush
                    if time.time() - last_flush > self.flush_interval:
                        self._flush_all_loggers()
                        last_flush = time.time()
                    continue
                
                # Process the log record
                module_name, level, message, args, kwargs = log_record
                
                # Get or create the real logger
                real_logger = self._get_real_logger(module_name)
                
                # Write the log message
                self._dispatch_log(real_logger, level, message, args, kwargs)
                self.log_queue.task_done()
                
            except Exception as e:
                # Don't let exceptions in logging crash the worker thread
                print(f"Error in async log processor: {e}")
                continue
        
        # Process remaining items in queue during shutdown
        self._drain_queue()
    
    def _get_real_logger(self, module_name: str):
        """Get or create the real LoggerUtility instance"""
        if module_name not in self.real_loggers:
            config = get_logging_config()
            self.real_loggers[module_name] = config.get_logger(module_name)
        return self.real_loggers[module_name]
    
    def _dispatch_log(self, logger, level, message, args, kwargs):
        """Dispatch log message to the appropriate logger method based on level"""
        try:
            if level == 'debug':
                logger.debug(message, *args, **kwargs)
            elif level == 'info':
                logger.info(message, *args, **kwargs)
            elif level == 'warning':
                logger.warning(message, *args, **kwargs)
            elif level == 'error':
                logger.error(message, *args, **kwargs)
            elif level == 'critical':
                logger.critical(message, *args, **kwargs)
            elif level == 'exception':
                logger.exception(message, **kwargs)
            elif level == 'log_with_context':
                logger.log_with_context(args[0], message, args[1])
        except Exception as e:
            print(f"Error dispatching log: {e}")
    
    def _flush_all_loggers(self):
        """Force flush all real loggers"""
        for logger in self.real_loggers.values():
            try:
                logger._force_flush()
            except:
                pass
    
    def _drain_queue(self):
        """Process all remaining items in the queue"""
        while True:
            try:
                log_record = self.log_queue.get_nowait()
                module_name, level, message, args, kwargs = log_record
                real_logger = self._get_real_logger(module_name)
                
                # Write the log message
                if level == 'debug':
                    real_logger.debug(message, *args, **kwargs)
                elif level == 'info':
                    real_logger.info(message, *args, **kwargs)
                elif level == 'warning':
                    real_logger.warning(message, *args, **kwargs)
                elif level == 'error':
                    real_logger.error(message, *args, **kwargs)
                elif level == 'critical':
                    real_logger.critical(message, *args, **kwargs)
                elif level == 'exception':
                    real_logger.exception(message, **kwargs)
                elif level == 'log_with_context':
                    real_logger.log_with_context(args[0], message, args[1])
                
                self.log_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error draining log queue: {e}")
                break
        
        # Final flush
        self._flush_all_loggers()
    
    def enqueue_log(self, module_name: str, level: str, message: str, *args, **kwargs):
        """Add a log message to the queue for async processing"""
        if not self.shutdown_event.is_set():
            log_record = (module_name, level, message, args, kwargs)
            self.log_queue.put(log_record)
    
    def shutdown(self, timeout=5.0):
        """Shutdown the async processor gracefully"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.shutdown_event.set()
            self.worker_thread.join(timeout=timeout)


def _get_async_processor():
    """Get or create the global async log processor"""
    global _async_log_processor
    if _async_log_processor is None:
        _async_log_processor = AsyncLogProcessor()
        _async_log_processor.start()
    return _async_log_processor


class LazyLogger:
    """Lazy logger that defers actual logger creation until first use and writes asynchronously"""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self._real_logger = None
        self._initialized = False
        self.async_processor = _get_async_processor()
    
    def _ensure_logger_for_sync_ops(self):
        """Create the actual logger for operations that need immediate response"""
        if not self._initialized:
            config = get_logging_config()
            self._real_logger = config.get_logger(self.module_name)
            self._initialized = True
        return self._real_logger
    
    def debug(self, message: str, *args, **kwargs):
        """Log a debug message asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'debug', message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log an info message asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'info', message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log a warning message asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'warning', message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log an error message asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'error', message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log a critical message asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'critical', message, *args, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log an exception with traceback asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'exception', message, **kwargs)
    
    def log_with_context(self, level, message: str, context):
        """Log a message with additional context information asynchronously."""
        self.async_processor.enqueue_log(self.module_name, 'log_with_context', message, level, context)
    
    def set_level(self, level):
        """Set the logging verbosity level - requires sync access to real logger."""
        self._ensure_logger_for_sync_ops().set_level(level)
    
    def get_level(self):
        """Get the current logging level - requires sync access to real logger."""
        return self._ensure_logger_for_sync_ops().get_level()


# Convenience function for getting a lazy logger
def get_configured_logger(module_name: str) -> LazyLogger:
    """Get a lazy logger that will be configured on first use and writes asynchronously"""
    global _lazy_loggers
    if module_name not in _lazy_loggers:
        _lazy_loggers[module_name] = LazyLogger(module_name)
    return _lazy_loggers[module_name]


# Command-line interface for setting all loggers to a specific level
def set_all_loggers_to_level(level: str):
    """
    Set all loggers to a specific level.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    config = get_logging_config()
    config.set_all_loggers_level(level)
    
    # Print export commands for environment variables
    print("\nTo make this change effective, set these environment variables:")
    for env_var, _ in config.get_all_env_vars().items():
        print(f"export {env_var}={level}")
    
    # Or create a single export command
    print("\nOr use this single command:")
    all_exports = " && ".join([f"export {env_var}={level}" for env_var in config.get_all_env_vars().keys()])
    print(all_exports)


# Example usage
if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "set-level" and len(sys.argv) > 2:
            set_all_loggers_to_level(sys.argv[2])
        else:
            print("Usage: python logging_config_helper.py set-level <LEVEL>")
            print("Where <LEVEL> is one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    else:
        # Get configuration
        config = get_logging_config()
        
        # Get profile from environment variable or default to development
        profile = os.getenv("NLWEB_LOGGING_PROFILE", "development")
        config.apply_profile(profile)
        print(f"Applied logging profile: {profile}")
        
        # Get loggers for different modules
        llm_logger = get_configured_logger("llm_wrapper")
        ranking_logger = get_configured_logger("ranking_engine")
        
        # Use the loggers
        llm_logger.info("This is an info message from LLM wrapper")
        ranking_logger.debug("This is a debug message from ranking engine")