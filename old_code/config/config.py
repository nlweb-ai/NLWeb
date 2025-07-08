# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Basic config services, including loading config from config_llm.yaml, config_embedding.yaml, config_retrieval.yaml, 
config_webserver.yaml, config_nlweb.yaml
WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import yaml
from dataclasses import dataclass, field
from dotenv import load_dotenv
from typing import Dict, Optional, Any, List

@dataclass
class ModelConfig:
    high: str
    low: str

@dataclass
class LLMProviderConfig:
    llm_type: str
    api_key: Optional[str] = None
    models: Optional[ModelConfig] = None
    endpoint: Optional[str] = None
    api_version: Optional[str] = None

@dataclass
class EmbeddingProviderConfig:
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    api_version: Optional[str] = None
    model: Optional[str] = None

@dataclass
class RetrievalProviderConfig:
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    database_path: Optional[str] = None
    index_name: Optional[str] = None
    db_type: Optional[str] = None
    use_knn: Optional[bool] = None
    enabled: bool = False
    vector_type: Optional[Dict[str,Any]] = None

@dataclass
class SSLConfig:
    enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None

@dataclass
class LoggingConfig:
    level: str = "info"
    file: str = "./logs/webserver.log"

@dataclass
class StaticConfig:
    enable_cache: bool = True
    cache_max_age: int = 3600
    gzip_enabled: bool = True

@dataclass
class ServerConfig:
    host: str = "localhost"
    enable_cors: bool = True
    max_connections: int = 100
    timeout: int = 30
    ssl: Optional[SSLConfig] = None
    logging: Optional[LoggingConfig] = None
    static: Optional[StaticConfig] = None

@dataclass
class NLWebConfig:
    sites: List[str]  # List of allowed sites
    json_data_folder: str = "./data/json"  # Default folder for JSON data
    json_with_embeddings_folder: str = "./data/json_with_embeddings"  # Default folder for JSON with embeddings
    chatbot_instructions: Dict[str, str] = field(default_factory=dict)  # Dictionary of chatbot instructions
    headers: Dict[str, str] = field(default_factory=dict)  # Dictionary of headers to include in responses
    tool_selection_enabled: bool = True  # Enable or disable tool selection
    memory_enabled: bool = False  # Enable or disable memory functionality
    analyze_query_enabled: bool = False  # Enable or disable query analysis
    decontextualize_enabled: bool = True  # Enable or disable decontextualization
    required_info_enabled: bool = True  # Enable or disable required info checking

    headers: Dict[str, str] = field(default_factory=dict)  # HTTP headers to send

class AppConfig:
    config_paths = ["config.yaml", "config_llm.yaml", "config_embedding.yaml", "config_retrieval.yaml", 
                   "config_webserver.yaml", "config_nlweb.yaml"]

    def __init__(self):
        load_dotenv()
        self.base_output_directory = self._get_base_output_directory()
        self.load_llm_config()
        self.load_embedding_config()
        self.load_retrieval_config()
        self.load_webserver_config()
        self.load_nlweb_config()

    def _get_base_output_directory(self) -> Optional[str]:
        """
        Get the base directory for all output files from the environment variable.
        Returns None if the environment variable is not set.
        """
        base_dir = os.getenv('NLWEB_OUTPUT_DIR')
        if base_dir and not os.path.exists(base_dir):
            try:
                os.makedirs(base_dir, exist_ok=True)
                print(f"Created output directory: {base_dir}")
            except Exception as e:
                print(f"Warning: Failed to create output directory {base_dir}: {e}")
                return None
        return base_dir

    def _resolve_path(self, path: str) -> str:
        """
        Resolves a path, considering the base output directory if set.
        If path is absolute, returns it unchanged.
        If path is relative and base_output_directory is set, resolves against base_output_directory.
        Otherwise, resolves against the config directory.
        """
        if os.path.isabs(path):
            return path
            
        config_dir = os.path.dirname(os.path.abspath(__file__))
        
        if self.base_output_directory:
            # If base output directory is set, use it for all relative paths
            return os.path.abspath(os.path.join(self.base_output_directory, path))
        else:
            # Otherwise use the config directory
            return os.path.abspath(os.path.join(config_dir, path))

    def _get_config_value(self, value: Any, default: Any = None) -> Any:
        """
        Get configuration value. If value is a string, return it directly.
        Otherwise, treat it as an environment variable name and fetch from environment.
        Returns default if environment variable is not set or value is None.
        """
        if value is None:
            return default
            
        if isinstance(value, str):
            # If it's clearly an environment variable name (e.g., "OPENAI_API_KEY_ENV")
            if value.endswith('_ENV') or value.isupper():
                return os.getenv(value, default)
            # Otherwise, treat it as a literal string value
            else:
                return value
        
        # For non-string values, return as-is
        return value

    def load_llm_config(self, path: str = "config_llm.yaml"):
        # Get the directory where this config.py file is located
        config_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the config file
        full_path = os.path.join(config_dir, path)
        
        with open(full_path, "r") as f:
            data = yaml.safe_load(f)

            self.preferred_llm_endpoint: str = data["preferred_endpoint"]
            self.llm_endpoints: Dict[str, LLMProviderConfig] = {}

            for name, cfg in data.get("endpoints", {}).items():
                m = cfg.get("models", {})
                models = ModelConfig(
                    high=self._get_config_value(m.get("high")),
                    low=self._get_config_value(m.get("low"))
                ) if m else None
                
                # Extract configuration values from the YAML with the new method
                api_key = self._get_config_value(cfg.get("api_key_env"))
                api_endpoint = self._get_config_value(cfg.get("api_endpoint_env"))
                api_version = self._get_config_value(cfg.get("api_version_env"))
                llm_type = self._get_config_value(cfg.get("llm_type"))
                # Create the LLM provider config - no longer include embedding model
                self.llm_endpoints[name] = LLMProviderConfig(
                    llm_type=llm_type,
                    api_key=api_key,
                    models=models,
                    endpoint=api_endpoint,
                    api_version=api_version
                )

    def load_embedding_config(self, path: str = "config_embedding.yaml"):
        """Load embedding model configuration."""
        # Get the directory where this config.py file is located
        config_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the config file
        full_path = os.path.join(config_dir, path)
        
        try:
            with open(full_path, "r") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            # If config file doesn't exist, use defaults
            print(f"Warning: {path} not found. Using default embedding configuration.")
            data = {
                "preferred_provider": "openai",
                "providers": {}
            }
        
        self.preferred_embedding_provider: str = data["preferred_provider"]
        self.embedding_providers: Dict[str, EmbeddingProviderConfig] = {}

        for name, cfg in data.get("providers", {}).items():
            # Extract configuration values from the YAML
            api_key = self._get_config_value(cfg.get("api_key_env"))
            api_endpoint = self._get_config_value(cfg.get("api_endpoint_env"))
            api_version = self._get_config_value(cfg.get("api_version_env"))
            model = self._get_config_value(cfg.get("model"))

            # Create the embedding provider config
            self.embedding_providers[name] = EmbeddingProviderConfig(
                api_key=api_key,
                endpoint=api_endpoint,
                api_version=api_version,
                model=model
            )

    def load_retrieval_config(self, path: str = "config_retrieval.yaml"):
        # Get the directory where this config.py file is located
        config_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the config file
        full_path = os.path.join(config_dir, path)
        
        try:
            with open(full_path, "r") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            # If config file doesn't exist, use defaults
            print(f"Warning: {path} not found. Using default retrieval configuration.")
            data = {
                "preferred_endpoint": "default",
                "endpoints": {}
            }

        # No longer using preferred_endpoint - now using enabled field on each endpoint
        self.retrieval_endpoints: Dict[str, RetrievalProviderConfig] = {}
        
        # Get the write endpoint for database modifications
        self.write_endpoint: str = data.get("write_endpoint", None)

        # Changed from providers to endpoints
        for name, cfg in data.get("endpoints", {}).items():
            # Use the new method for all configuration values
            self.retrieval_endpoints[name] = RetrievalProviderConfig(
                api_key=self._get_config_value(cfg.get("api_key_env")),
                api_endpoint=self._get_config_value(cfg.get("api_endpoint_env")),
                database_path=self._get_config_value(cfg.get("database_path")),
                index_name=self._get_config_value(cfg.get("index_name")),
                db_type=self._get_config_value(cfg.get("db_type")),  # Add db_type
                enabled=cfg.get("enabled", False),  # Add enabled field
                vector_type=self._get_config_value(cfg.get("vector_type"))
            )
    
    def load_webserver_config(self, path: str = "config_webserver.yaml"):
        # Get the directory where this config.py file is located
        config_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the config file
        full_path = os.path.join(config_dir, path)
        
        try:
            with open(full_path, "r") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            # If config file doesn't exist, use defaults
            print(f"Warning: {path} not found. Using default webserver configuration.")
            data = {
                "port": 8080,
                "static_directory": "./static",
                "server": {}
            }
        
        # Load basic configurations with the new method
        self.port: int = self._get_config_value(data.get("port"), 8080)
        self.static_directory: str = self._get_config_value(data.get("static_directory"), "./static")
        self.mode: str = self._get_config_value(data.get("mode"), "production")
        
        # Keep static directory relative to config directory, not base output directory
        if not os.path.isabs(self.static_directory):
            self.static_directory = os.path.abspath(os.path.join(config_dir, self.static_directory))
        
        # Load server configurations
        server_data = data.get("server", {})
        
        # SSL configuration
        ssl_data = server_data.get("ssl", {})
        ssl_config = SSLConfig(
            enabled=self._get_config_value(ssl_data.get("enabled"), False),
            cert_file=self._get_config_value(ssl_data.get("cert_file_env")),
            key_file=self._get_config_value(ssl_data.get("key_file_env"))
        )
        
        # Logging configuration
        logging_data = server_data.get("logging", {})
        logging_file = self._get_config_value(logging_data.get("file"), "./logs/webserver.log")
        # Use the _resolve_path method for logging file (but not for static directory)
        logging_file = self._resolve_path(logging_file)
        
        logging_config = LoggingConfig(
            level=self._get_config_value(logging_data.get("level"), "info"),
            file=logging_file
        )
        
        # Static file configuration
        static_data = server_data.get("static", {})
        static_config = StaticConfig(
            enable_cache=self._get_config_value(static_data.get("enable_cache"), True),
            cache_max_age=self._get_config_value(static_data.get("cache_max_age"), 3600),
            gzip_enabled=self._get_config_value(static_data.get("gzip_enabled"), True)
        )
        
        # Create the server config
        self.server = ServerConfig(
            host=self._get_config_value(server_data.get("host"), "localhost"),
            enable_cors=self._get_config_value(server_data.get("enable_cors"), True),
            max_connections=self._get_config_value(server_data.get("max_connections"), 100),
            timeout=self._get_config_value(server_data.get("timeout"), 30),
            ssl=ssl_config,
            logging=logging_config,
            static=static_config
        )

    def load_nlweb_config(self, path: str = "config_nlweb.yaml"):
        """Load Natural Language Web configuration."""
        # Get the directory where this config.py file is located
        config_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the full path to the config file
        full_path = os.path.join(config_dir, path)
        
        try:
            with open(full_path, "r") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            # If config file doesn't exist, use defaults
            print(f"Warning: {path} not found. Using default NLWeb configuration.")
            data = {
                "sites": "",
                "data_folders": {
                    "json_data": "./data/json",
                    "json_with_embeddings": "./data/json_with_embeddings"
                },
                "chatbot_instructions": {
                    "search_results": "IMPORTANT: When presenting these results to the user, always include the original URL as a clickable link for each item."
                }
            }
        
        # Parse the comma-separated sites string into a list
        sites_str = self._get_config_value(data.get("sites"), "")
        sites_list = [site.strip() for site in sites_str.split(",") if site.strip()]

        # Get data folder paths from config
        json_data_folder = "./data/json"
        json_with_embeddings_folder = "./data/json_with_embeddings"
        
        if "data_folders" in data:
            json_data_folder = self._get_config_value(
                data["data_folders"].get("json_data"), 
                json_data_folder
            )
            json_with_embeddings_folder = self._get_config_value(
                data["data_folders"].get("json_with_embeddings"), 
                json_with_embeddings_folder
            )

        # Load chatbot instructions from config
        chatbot_instructions = data.get("chatbot_instructions", {})
        
        # Load headers from config
        headers = data.get("headers", {})

        # Load tool selection enabled flag
        tool_selection_enabled = self._get_config_value(data.get("tool_selection_enabled"), True)
        
        # Load memory enabled flag
        memory_enabled = self._get_config_value(data.get("memory_enabled"), False)
        
        # Load analyze query enabled flag
        analyze_query_enabled = self._get_config_value(data.get("analyze_query_enabled"), False)
        
        # Load decontextualize enabled flag
        decontextualize_enabled = self._get_config_value(data.get("decontextualize_enabled"), True)
        
        # Load required info enabled flag
        required_info_enabled = self._get_config_value(data.get("required_info_enabled"), True)
        
        # Load headers from config
        headers = data.get("headers", {})
        
        # Convert relative paths to use NLWEB_OUTPUT_DIR if available
        base_output_dir = self.base_output_directory
        if base_output_dir:
            if not os.path.isabs(json_data_folder):
                json_data_folder = os.path.join(base_output_dir, "data", "json")
            if not os.path.isabs(json_with_embeddings_folder):
                json_with_embeddings_folder = os.path.join(base_output_dir, "data", "json_with_embeddings")
    
        # Ensure directories exist
        os.makedirs(json_data_folder, exist_ok=True)
        os.makedirs(json_with_embeddings_folder, exist_ok=True)
        
        self.nlweb = NLWebConfig(
            sites=sites_list,
            json_data_folder=json_data_folder,
            json_with_embeddings_folder=json_with_embeddings_folder,
            chatbot_instructions=chatbot_instructions,
            tool_selection_enabled=tool_selection_enabled,
            memory_enabled=memory_enabled,
            analyze_query_enabled=analyze_query_enabled,
            decontextualize_enabled=decontextualize_enabled,
            required_info_enabled=required_info_enabled,
            headers=headers
        )
    
    def get_chatbot_instructions(self, instruction_type: str = "search_results") -> str:
        """Get the chatbot instructions for a specific type."""
        if (hasattr(self, 'nlweb') and 
            self.nlweb.chatbot_instructions and 
            instruction_type in self.nlweb.chatbot_instructions):
            return self.nlweb.chatbot_instructions[instruction_type]
        
        # Default instructions if not found in config
        default_instructions = {
            "search_results": (
                "IMPORTANT: When presenting these results to the user, always include "
                "the original URL as a clickable link for each item. Format each item's name "
                "as a hyperlink using its URL."
            )
        }
    
    def get_headers(self) -> Dict[str, str]:
        """Get the configured headers to include in responses."""
        if hasattr(self, 'nlweb') and self.nlweb.headers:
            return self.nlweb.headers
        return {}
        
    def get_chatbot_instruction_fallback(self, instruction_type: str = "search_results") -> str:
        """Get fallback chatbot instructions."""
        default_instructions = {
            "search_results": (
                "IMPORTANT: When presenting these results to the user, always include "
                "the original URL as a clickable link for each item. Format each item's name "
                "as a hyperlink using its URL."
            )
        }
        return default_instructions.get(instruction_type, "")
    
    def get_ssl_cert_path(self) -> Optional[str]:
        """Get the SSL certificate file path."""
        if self.server.ssl:
            return self.server.ssl.cert_file
        return None
    
    def get_ssl_key_path(self) -> Optional[str]:
        """Get the SSL key file path."""
        if self.server.ssl:
            return self.server.ssl.key_file
        return None
    
    def is_ssl_enabled(self) -> bool:
        """Check if SSL is enabled and properly configured."""
        return (self.server.ssl and 
                self.server.ssl.enabled and 
                self.server.ssl.cert_file is not None and 
                self.server.ssl.key_file is not None)
    
    def is_production_mode(self) -> bool:
        """Returns True if the system is running in production mode."""
        return getattr(self, 'mode', 'production').lower() == 'production'
    
    def is_development_mode(self) -> bool:
        """Returns True if the system is running in development mode."""
        return getattr(self, 'mode', 'production').lower() == 'development'
    
    def is_testing_mode(self) -> bool:
        """Returns True if the system is running in testing mode."""
        return getattr(self, 'mode', 'production').lower() == 'testing'
    
    def should_raise_exceptions(self) -> bool:
        """Returns True if exceptions should be raised instead of caught (for testing and development)."""
        return self.is_testing_mode() or self.is_development_mode()
    
    def set_mode(self, mode: str):
        """Set the application mode (development, production, or testing)."""
        if mode.lower() not in ['development', 'production', 'testing']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'development', 'production', or 'testing'")
        self.mode = mode.lower()
    
    def get_allowed_sites(self) -> List[str]:
        """Get the list of allowed sites from NLWeb configuration."""
        return self.nlweb.sites if hasattr(self, 'nlweb') else []
    
    def is_site_allowed(self, site: str) -> bool:
        """Check if a site is in the allowed sites list."""
        allowed_sites = self.get_allowed_sites()
        # If no sites are configured, allow all sites
        if not allowed_sites or allowed_sites == ['all']:
            return True
        return site in allowed_sites
    
    def is_tool_selection_enabled(self) -> bool:
        """Check if tool selection is enabled."""
        return self.nlweb.tool_selection_enabled if hasattr(self, 'nlweb') else True
    
    def is_memory_enabled(self) -> bool:
        """Check if memory functionality is enabled."""
        return self.nlweb.memory_enabled if hasattr(self, 'nlweb') else False
    
    def is_analyze_query_enabled(self) -> bool:
        """Check if query analysis is enabled."""
        return self.nlweb.analyze_query_enabled if hasattr(self, 'nlweb') else False
    
    def is_decontextualize_enabled(self) -> bool:
        """Check if decontextualization is enabled."""
        return self.nlweb.decontextualize_enabled if hasattr(self, 'nlweb') else True
    
    def is_required_info_enabled(self) -> bool:
        """Check if required info checking is enabled."""
        return self.nlweb.required_info_enabled if hasattr(self, 'nlweb') else True
    
    def get_embedding_provider(self, provider_name: Optional[str] = None) -> Optional[EmbeddingProviderConfig]:
        """Get the specified embedding provider config or the preferred one if not specified."""
        if not hasattr(self, 'embedding_providers'):
            return None
            
        if provider_name and provider_name in self.embedding_providers:
            return self.embedding_providers[provider_name]
            
        if hasattr(self, 'preferred_embedding_provider') and self.preferred_embedding_provider in self.embedding_providers:
            return self.embedding_providers[self.preferred_embedding_provider]
            
        return None
            
    def get_llm_provider(self, provider_name: Optional[str] = None) -> Optional[LLMProviderConfig]:
        """Get the specified LLM provider config or the preferred one if not specified."""
        if not hasattr(self, 'llm_endpoints'):
            return None
            
        if provider_name and provider_name in self.llm_endpoints:
            return self.llm_endpoints[provider_name]
            
        if hasattr(self, 'preferred_llm_endpoint') and self.preferred_llm_endpoint in self.llm_endpoints:
            return self.llm_endpoints[self.preferred_llm_endpoint]
            
        return None

# Global singleton
CONFIG = AppConfig()