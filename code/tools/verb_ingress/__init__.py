"""
Ingress module for NLWeb - Extensible data ingestion using Strategy Pattern.

This module provides a modular, extensible system for ingesting various data types
into the NLWeb vector database. It uses the Strategy Pattern for different data types
and a Factory Pattern for strategy selection.
"""

from .base_strategy import BaseIngressStrategy
from .factory import IngressFactory
from .openapi_strategy import OpenAPIStrategy
from .java_strategy import JavaStrategy

__all__ = [
    'BaseIngressStrategy',
    'IngressFactory',
    'OpenAPIStrategy',
    'JavaStrategy'
]
