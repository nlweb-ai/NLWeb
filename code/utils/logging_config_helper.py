import yaml
import os
from typing import Dict, Any, Optional
from utils.logger import LogLevel, LoggerUtility


class LoggingConfig:
    """Helper class to load and manage logging configuration from YAML file"""
    
    def __init__(self, config_path: str = "config/config_logging.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._ensure_log_directory()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Warning: Logging config file not found at {self.config_path}")
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
        """Create log directory if it doesn't exist"""
        log_dir = self.config["logging"].get("log_directory", "logs")
        
        # Check for NLWEB_OUTPUT_DIR environment variable
        output_dir = os.getenv('NLWEB_OUTPUT_DIR')
        if output_dir:
            # Create logs directory under the output directory
            log_dir = os.path.join(output_dir, os.path.basename(log_dir))
            
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            print(f"Created log directory: {log_dir}")
            
        # Store the resolved directory
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


# Singleton instance
_logging_config = None

def get_logging_config(config_path: str = "config/config_logging.yaml") -> LoggingConfig:
    """Get or create the singleton logging configuration"""
    global _logging_config
    if _logging_config is None:
        _logging_config = LoggingConfig(config_path)
    return _logging_config


# Convenience function for getting a logger
def get_configured_logger(module_name: str) -> LoggerUtility:
    """Get a logger configured according to the YAML configuration"""
    config = get_logging_config()  # Fixed to call get_logging_config instead of itself
    return config.get_logger(module_name)


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