"""
Factory for selecting the appropriate ingress strategy based on data type or file extension.

This module implements the Factory Pattern to automatically select and instantiate
the correct ingress strategy for different data types.
"""

from typing import Dict, List, Type, Optional, Any, Union
import os

from .base_strategy import BaseIngressStrategy
from .openapi_strategy import OpenAPIStrategy
from .java_strategy import JavaStrategy


class IngressFactory:
    """
    Factory class for creating appropriate ingress strategies.

    Automatically selects the right strategy based on:
    1. File extension
    2. Data content analysis
    3. Explicit strategy specification
    """

    def __init__(self):
        """Initialize the factory with all available strategies."""
        self._strategies: Dict[str, Type[BaseIngressStrategy]] = {
            'openapi': OpenAPIStrategy,
            'java': JavaStrategy
        }

        # Create strategy instances for validation
        self._strategy_instances: Dict[str, BaseIngressStrategy] = {
            name: strategy_class() for name, strategy_class in self._strategies.items()
        }

    def get_available_strategies(self) -> List[str]:
        """
        Get list of available strategy names.

        Returns:
            List of strategy names
        """
        return list(self._strategies.keys())

    def get_strategy_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all available strategies.

        Returns:
            Dictionary with strategy info including name, extensions, etc.
        """
        info = {}
        for name, instance in self._strategy_instances.items():
            info[name] = {
                'name': instance.get_strategy_name(),
                'extensions': instance.get_supported_extensions(),
                'class': type(instance).__name__
            }
        return info

    def create_strategy(self, strategy_name: str) -> BaseIngressStrategy:
        """
        Create a strategy instance by name.

        Args:
            strategy_name: Name of the strategy to create

        Returns:
            Strategy instance

        Raises:
            ValueError: If strategy name is not recognized
        """
        if strategy_name not in self._strategies:
            available = ', '.join(self._strategies.keys())
            raise ValueError(
                f"Unknown strategy '{strategy_name}'. Available strategies: {available}")

        return self._strategies[strategy_name]()

    def get_strategy_for_file(self, file_path: str) -> Optional[BaseIngressStrategy]:
        """
        Get the appropriate strategy for a file based on its extension.

        Args:
            file_path: Path to the file

        Returns:
            Strategy instance if one supports the file, None otherwise
        """
        # Check each strategy to see if it supports this file
        for instance in self._strategy_instances.values():
            if instance.supports_file(file_path):
                # Return a new instance of the appropriate strategy
                strategy_class = type(instance)
                return strategy_class()

        return None

    def get_strategy_for_data(self, data: Any) -> Optional[BaseIngressStrategy]:
        """
        Get the appropriate strategy for data based on content analysis.

        Args:
            data: Data to analyze

        Returns:
            Strategy instance if one can handle the data, None otherwise
        """
        # Check each strategy to see if it can handle this data
        for instance in self._strategy_instances.values():
            if instance.supports_data_type(data):
                # Return a new instance of the appropriate strategy
                strategy_class = type(instance)
                return strategy_class()

        return None

    def auto_select_strategy(self, data: Any = None, file_path: str = None,
                             strategy_name: str = None) -> Optional[BaseIngressStrategy]:
        """
        Automatically select the best strategy based on available information.

        Args:
            data: Optional data to analyze
            file_path: Optional file path to check
            strategy_name: Optional explicit strategy name

        Returns:
            Strategy instance, or None if no suitable strategy found
        """
        # If strategy is explicitly specified, use it
        if strategy_name:
            try:
                return self.create_strategy(strategy_name)
            except ValueError as e:
                print(f"Warning: {e}")
                # Fall through to automatic detection

        # Try file extension-based detection
        if file_path:
            strategy = self.get_strategy_for_file(file_path)
            if strategy:
                return strategy

        # Try data content-based detection
        if data is not None:
            strategy = self.get_strategy_for_data(data)
            if strategy:
                return strategy

        return None

    def get_supported_extensions(self) -> List[str]:
        """
        Get all file extensions supported by any strategy.

        Returns:
            List of supported file extensions
        """
        extensions = set()
        for instance in self._strategy_instances.values():
            extensions.update(instance.get_supported_extensions())
        return sorted(list(extensions))

    def print_strategy_info(self):
        """Print information about all available strategies."""
        print("\\n=== Available Ingress Strategies ===")
        for name, info in self.get_strategy_info().items():
            print(f"\\n{name}:")
            print(f"  Name: {info['name']}")
            print(f"  Extensions: {', '.join(info['extensions'])}")
            print(f"  Class: {info['class']}")

        print(
            f"\\nSupported extensions: {', '.join(self.get_supported_extensions())}")


# Global factory instance for convenience
factory = IngressFactory()


def create_strategy(strategy_name: str) -> BaseIngressStrategy:
    """
    Convenience function to create a strategy using the global factory.

    Args:
        strategy_name: Name of the strategy to create

    Returns:
        Strategy instance
    """
    return factory.create_strategy(strategy_name)


def auto_select_strategy(data: Any = None, file_path: str = None,
                         strategy_name: str = None) -> Optional[BaseIngressStrategy]:
    """
    Convenience function to auto-select a strategy using the global factory.

    Args:
        data: Optional data to analyze
        file_path: Optional file path to check
        strategy_name: Optional explicit strategy name

    Returns:
        Strategy instance, or None if no suitable strategy found
    """
    return factory.auto_select_strategy(data, file_path, strategy_name)


def get_available_strategies() -> List[str]:
    """
    Convenience function to get available strategies using the global factory.

    Returns:
        List of strategy names
    """
    return factory.get_available_strategies()


def print_strategy_info():
    """Convenience function to print strategy info using the global factory."""
    factory.print_strategy_info()
