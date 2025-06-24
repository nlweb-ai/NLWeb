#!/usr/bin/env python3
"""
Dependency checker for NLWeb
This script reads the configuration files and ensures all required modules are installed
based on the enabled LLM providers and retrieval backends.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path


class DependencyChecker:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_dir = self.base_dir / "code" / "config"
        self.missing_packages = []
        
        # Mapping of LLM types to their required packages
        self.llm_packages = {
            "openai": ["openai>=1.12.0"],
            "anthropic": ["anthropic>=0.18.1"],
            "gemini": ["google-cloud-aiplatform>=1.38.0"],
            "azure_openai": ["openai>=1.12.0"],
            "llama_azure": ["openai>=1.12.0"],
            "deepseek_azure": ["openai>=1.12.0"],
            "inception": ["aiohttp>=3.9.1"],
            "snowflake": ["httpx>=0.28.1"],
            "huggingface": ["huggingface_hub>=0.31.0"],
        }
        
        # Mapping of database types to their required packages
        self.db_packages = {
            "azure_ai_search": ["azure-core>=1.30.0", "azure-search-documents>=11.4.0"],
            "milvus": ["pymilvus>=1.1.0", "numpy"],
            "opensearch": ["httpx>=0.28.1"],
            "qdrant": ["qdrant-client>=1.14.0"],
            "snowflake_cortex_search": ["httpx>=0.28.1"],
        }

    def check_package_installed(self, package_name):
        """Check if a package is installed."""
        try:
            # Extract package name without version
            pkg_name = package_name.split(">=")[0].split("==")[0]
            
            # Handle special import names
            if pkg_name == "azure-core":
                __import__("azure.core")
            elif pkg_name == "azure-search-documents":
                __import__("azure.search.documents")
            elif pkg_name == "google-cloud-aiplatform":
                __import__("vertexai")
            elif pkg_name == "qdrant-client":
                __import__("qdrant_client")
            else:
                __import__(pkg_name)
            return True
        except ImportError:
            return False

    def read_yaml_config(self, filename):
        """Read a YAML configuration file."""
        config_path = self.config_dir / filename
        if not config_path.exists():
            print(f"Warning: {filename} not found at {config_path}")
            return {}
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def check_llm_dependencies(self):
        """Check dependencies for enabled LLM providers."""
        print("\n=== Checking LLM Provider Dependencies ===")
        
        config = self.read_yaml_config("config_llm.yaml")
        if not config:
            return
        
        endpoints = config.get("endpoints", {})
        enabled_providers = []
        
        for name, cfg in endpoints.items():
            # Check if provider has required API key set
            api_key_env = cfg.get("api_key_env")
            if api_key_env and os.getenv(api_key_env):
                llm_type = cfg.get("llm_type")
                if llm_type:
                    enabled_providers.append((name, llm_type))
        
        if not enabled_providers:
            print("No LLM providers have API keys configured.")
            return
        
        print(f"Found {len(enabled_providers)} configured LLM provider(s):")
        for name, llm_type in enabled_providers:
            print(f"  - {name} (type: {llm_type})")
            
            # Check required packages
            if llm_type in self.llm_packages:
                for package in self.llm_packages[llm_type]:
                    if not self.check_package_installed(package):
                        self.missing_packages.append(package)
                        print(f"    ❌ Missing: {package}")
                    else:
                        print(f"    ✅ Installed: {package}")

    def check_retrieval_dependencies(self):
        """Check dependencies for enabled retrieval backends."""
        print("\n=== Checking Retrieval Backend Dependencies ===")
        
        config = self.read_yaml_config("config_retrieval.yaml")
        if not config:
            return
        
        endpoints = config.get("endpoints", {})
        enabled_backends = []
        
        for name, cfg in endpoints.items():
            # Check if backend is enabled
            if cfg.get("enabled", False):
                db_type = cfg.get("db_type")
                if db_type:
                    # Check if it has required credentials
                    has_creds = False
                    if db_type in ["azure_ai_search", "snowflake_cortex_search"]:
                        api_key_env = cfg.get("api_key_env")
                        api_endpoint_env = cfg.get("api_endpoint_env")
                        if api_key_env and api_endpoint_env:
                            has_creds = bool(os.getenv(api_key_env) and os.getenv(api_endpoint_env))
                    elif db_type == "opensearch":
                        api_endpoint_env = cfg.get("api_endpoint_env")
                        api_key_env = cfg.get("api_key_env")
                        if api_endpoint_env and api_key_env:
                            has_creds = bool(os.getenv(api_endpoint_env) and os.getenv(api_key_env))
                    elif db_type == "qdrant":
                        if cfg.get("database_path"):
                            has_creds = True
                        else:
                            api_endpoint_env = cfg.get("api_endpoint_env")
                            if api_endpoint_env:
                                has_creds = bool(os.getenv(api_endpoint_env))
                    elif db_type == "milvus":
                        has_creds = bool(cfg.get("database_path"))
                    
                    if has_creds:
                        enabled_backends.append((name, db_type))
        
        if not enabled_backends:
            print("No retrieval backends are enabled with valid credentials.")
            return
        
        print(f"Found {len(enabled_backends)} enabled retrieval backend(s):")
        for name, db_type in enabled_backends:
            print(f"  - {name} (type: {db_type})")
            
            # Check required packages
            if db_type in self.db_packages:
                for package in self.db_packages[db_type]:
                    if not self.check_package_installed(package):
                        self.missing_packages.append(package)
                        print(f"    ❌ Missing: {package}")
                    else:
                        print(f"    ✅ Installed: {package}")

    def check_core_dependencies(self):
        """Check core dependencies from requirements.txt."""
        print("\n=== Checking Core Dependencies ===")
        
        requirements_path = self.base_dir / "code" / "requirements.txt"
        if not requirements_path.exists():
            print(f"Warning: requirements.txt not found at {requirements_path}")
            return
        
        core_packages = []
        with open(requirements_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith("#"):
                    # Only process lines before the optional dependencies section
                    if "Optional" in line:
                        break
                    core_packages.append(line)
        
        print(f"Checking {len(core_packages)} core dependencies...")
        missing_core = []
        for package in core_packages:
            if not self.check_package_installed(package):
                missing_core.append(package)
                print(f"  ❌ Missing: {package}")
        
        if missing_core:
            self.missing_packages.extend(missing_core)
        else:
            print("  ✅ All core dependencies are installed!")

    def install_missing_packages(self):
        """Install missing packages if user confirms."""
        if not self.missing_packages:
            print("\n✅ All required dependencies are already installed!")
            return
        
        # Remove duplicates
        unique_packages = list(set(self.missing_packages))
        
        print(f"\n❌ Found {len(unique_packages)} missing package(s):")
        for package in unique_packages:
            print(f"  - {package}")
        
        response = input("\nWould you like to install these packages now? (y/N): ")
        if response.lower() == 'y':
            print("\nInstalling missing packages...")
            for package in unique_packages:
                print(f"\nInstalling {package}...")
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", package
                    ])
                    print(f"✅ Successfully installed {package}")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to install {package}: {e}")
            print("\n✅ Installation complete!")
        else:
            print("\nSkipping installation. You can install these packages manually:")
            print(f"pip install {' '.join(unique_packages)}")

    def run(self):
        """Run all dependency checks."""
        print("=" * 60)
        print("NLWeb Dependency Checker")
        print("=" * 60)
        
        # Check core dependencies first
        self.check_core_dependencies()
        
        # Check LLM dependencies
        self.check_llm_dependencies()
        
        # Check retrieval dependencies
        self.check_retrieval_dependencies()
        
        # Offer to install missing packages
        self.install_missing_packages()
        
        print("\n" + "=" * 60)
        print("Dependency check complete!")
        print("=" * 60)


if __name__ == "__main__":
    checker = DependencyChecker()
    checker.run()