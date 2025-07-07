"""
Base strategy interface for data ingestion in NLWeb.

This module defines the abstract base class that all ingress strategies must implement.
Each strategy handles a specific data type (e.g., OpenAPI JSON, Java interfaces)
and converts it to the standardized document format for vector database storage.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional


class BaseIngressStrategy(ABC):
    """
    Abstract base class for all data ingestion strategies.

    Each strategy implementation must:
    1. Validate input data
    2. Process the data according to its type
    3. Convert to standardized document format
    4. Return documents ready for embedding and storage
    """

    @abstractmethod
    def validate_input(self, data: Any) -> bool:
        """
        Validate that the input data is appropriate for this strategy.

        Args:
            data: Raw input data to validate

        Returns:
            True if data is valid for this strategy, False otherwise
        """
        pass

    @abstractmethod
    def process_data(self, data: Any, source_url: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process the input data and convert to standardized document format.

        Args:
            data: Raw input data (file content, JSON object, etc.)
            source_url: URL or identifier for the data source
            site: Site identifier for categorization

        Returns:
            Tuple of (documents, texts_for_embedding) where:
            - documents: List of dicts with keys: id, schema_json, url, name, site
            - texts_for_embedding: List of text strings to generate embeddings from
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Get list of file extensions supported by this strategy.

        Returns:
            List of file extensions (e.g., ['.json', '.yaml'])
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Get a human-readable name for this strategy.

        Returns:
            Strategy name (e.g., "OpenAPI JSON", "Java Interface")
        """
        pass

    def supports_file(self, file_path: str) -> bool:
        """
        Check if this strategy supports the given file based on extension.

        Args:
            file_path: Path to the file to check

        Returns:
            True if this strategy can handle the file, False otherwise
        """
        extensions = self.get_supported_extensions()
        return any(file_path.lower().endswith(ext.lower()) for ext in extensions)

    def supports_data_type(self, data: Any) -> bool:
        """
        Check if this strategy can handle the given data type.
        This is a convenience method that combines validation and type checking.

        Args:
            data: Data to check

        Returns:
            True if this strategy can handle the data, False otherwise
        """
        try:
            return self.validate_input(data)
        except Exception:
            return False
