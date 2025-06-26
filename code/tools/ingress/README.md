# Various data types => Vector Database

A modular, extensible data ingestion system for NLWeb using the Strategy Pattern + Factory Pattern. This system supports multiple data types for ingestion, each with its own processing logic, and outputs standardized documents for storage in a vector database.

## How to use

### Quick Start with Examples

Run the examples script to see the ingress system in action:

```bash
# From the code/tools/ingress directory
python -m tools.ingress.examples
```

### Loading Real Files with db_load.py

The `db_load.py` script provides a CLI interface compatible with the legacy loader but uses the new ingress system for supported file types (OpenAPI JSON, Java interfaces).

**Load OpenAPI JSON files:**
```bash
# Load a local OpenAPI specification
python -m tools.ingress.db_load ../demo/github.openapi.json github-api

# Delete existing data
python -m tools.ingress.db_load ../demo/github.openapi.json --delete-site github-api
```

**Load Java interface files:**
```bash
# Load a Java interface
python -m tools.ingress.db_load ../demo/Wikimedia.java wikimedia-api
```

**Use specific database endpoint:**
```bash
# Load to a specific vector database
python -m tools.ingress.db_load ../demo/github.openapi.json --database qdrant_local
```

## Architecture

The ingress system uses two key design patterns:

1. **Strategy Pattern**: Each data type (OpenAPI JSON, Java Interface, etc.) has its own strategy class that implements the `BaseIngressStrategy` interface
2. **Factory Pattern**: The `IngressFactory` automatically selects the appropriate strategy based on file extension or data content analysis

### Core Components

```
ingress/
├── __init__.py              # Module exports
├── base_strategy.py         # Abstract base strategy interface
├── factory.py              # Factory for strategy selection
├── openapi_strategy.py      # OpenAPI/Swagger JSON strategy
├── java_strategy.py         # Java interface strategy
└── README.md               # This documentation
```

## Design Principles

### 1. Standardized Document Format

All strategies convert their input data to a standardized document format for vector database storage:

```python
{
    "id": str,           # Unique identifier (hash of URL)
    "schema_json": str,  # JSON string of processed content
    "url": str,          # Source URL or synthetic identifier
    "name": str,         # Human-readable name
    "site": str          # Site identifier for categorization
}
```

### 2. Strategy Interface

Every ingress strategy implements the `BaseIngressStrategy` interface:

```python
class BaseIngressStrategy(ABC):
    @abstractmethod
    def validate_input(self, data: Any) -> bool:
        """Validate input data for this strategy"""
        
    @abstractmethod
    def process_data(self, data: Any, source_url: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Process data and return (documents, texts_for_embedding)"""
        
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions"""
        
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return human-readable strategy name"""
```

### 3. Factory-Based Selection

The factory automatically selects strategies based on:
- **File extension**: `.java` → Java strategy, `.json` → OpenAPI strategy
- **Content analysis**: Validates data structure to determine compatibility
- **Explicit specification**: Direct strategy name specification

## Supported Data Types

### OpenAPI/Swagger JSON (`openapi_strategy.py`)

**Supported formats:**
- OpenAPI 3.x specifications
- Swagger 2.x specifications
- JSON format from URLs or files

**Output format:** Schema.org APIReference objects representing API endpoints

**Extensions:** `.json`, `.yaml`, `.yml`

**Example usage:**
```python
from ingress.factory import auto_select_strategy

# Auto-detect strategy from file
strategy = auto_select_strategy(file_path="api-spec.json")

# Process OpenAPI data
with open("api-spec.json") as f:
    data = f.read()
    
documents, texts = strategy.process_data(data, "https://api.example.com", "example-api")
```

### Java Interfaces (`java_strategy.py`)

**Supported formats:**
- Java interface files (`.java`)
- Parses methods, parameters, return types, documentation

**Output format:** Schema.org APIReference objects representing Java methods

**Extensions:** `.java`

**Example usage:**
```python
from ingress.factory import auto_select_strategy

# Auto-detect strategy from file
strategy = auto_select_strategy(file_path="MyInterface.java")

# Process Java interface
with open("MyInterface.java") as f:
    java_code = f.read()
    
documents, texts = strategy.process_data(java_code, "java://com.example.MyInterface", "example-java")
```

## Usage Examples

### Basic Usage

```python
from ingress.factory import auto_select_strategy

# Automatic strategy selection
strategy = auto_select_strategy(file_path="data.json")

if strategy:
    print(f"Using strategy: {strategy.get_strategy_name()}")
    
    # Load and process data
    with open("data.json") as f:
        data = f.read()
    
    documents, texts = strategy.process_data(data, "https://example.com/data.json", "example-site")
    print(f"Generated {len(documents)} documents")
else:
    print("No suitable strategy found")
```

### Explicit Strategy Selection

```python
from ingress.factory import create_strategy

# Create specific strategy
openapi_strategy = create_strategy("openapi")

# Process data
documents, texts = openapi_strategy.process_data(json_data, source_url, site_name)
```

### Complete Processing Pipeline

```python
import asyncio
from ingress.factory import auto_select_strategy
from embedding.embedding import batch_get_embeddings
from retrieval.retriever import get_vector_db_client

async def process_file(file_path: str, site: str):
    """Complete pipeline: detect strategy, process data, embed, store"""
    
    # Auto-select strategy
    strategy = auto_select_strategy(file_path=file_path)
    if not strategy:
        print(f"No strategy found for {file_path}")
        return
    
    # Load and process data
    with open(file_path) as f:
        data = f.read()
    
    documents, texts = strategy.process_data(data, file_path, site)
    
    if not documents:
        print("No documents generated")
        return
    
    # Generate embeddings
    embeddings = await batch_get_embeddings(texts)
    
    # Add embeddings to documents
    for doc, embedding in zip(documents, embeddings):
        doc["embedding"] = embedding
    
    # Store in vector database
    client = get_vector_db_client()
    await client.upload_documents(documents)
    
    print(f"Processed {len(documents)} documents from {file_path}")

# Usage
asyncio.run(process_file("api-spec.json", "my-api"))
```

## Adding New Strategies

To add support for a new data type:

### 1. Create Strategy Class

Create a new file `your_strategy.py`:

```python
from typing import List, Dict, Any, Tuple
from .base_strategy import BaseIngressStrategy
from tools.db_load_utils import int64_hash

class YourStrategy(BaseIngressStrategy):
    def validate_input(self, data: Any) -> bool:
        # Implement validation logic
        return True
    
    def process_data(self, data: Any, source_url: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        # Process data and convert to standard format
        documents = []
        texts = []
        
        # Your processing logic here...
        
        return documents, texts
    
    def get_supported_extensions(self) -> List[str]:
        return ['.your_extension']
    
    def get_strategy_name(self) -> str:
        return "Your Data Type"
```

### 2. Register in Factory

Update `factory.py`:

```python
from .your_strategy import YourStrategy

class IngressFactory:
    def __init__(self):
        self._strategies: Dict[str, Type[BaseIngressStrategy]] = {
            'openapi': OpenAPIStrategy,
            'java': JavaStrategy,
            'your_type': YourStrategy,  # Add your strategy
        }
        # ... rest of init
```

### 3. Update Module Exports

Update `__init__.py`:

```python
from .your_strategy import YourStrategy

__all__ = [
    'BaseIngressStrategy',
    'IngressFactory', 
    'OpenAPIStrategy',
    'JavaStrategy',
    'YourStrategy'  # Add your strategy
]
```

## Dependencies

- **Core**: No additional dependencies for the base system
- **OpenAPI Strategy**: `aiohttp` for URL fetching
- **Java Strategy**: `javalang` for parsing Java code

Install optional dependencies:
```bash
pip install aiohttp javalang
```