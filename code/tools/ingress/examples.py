#!/usr/bin/env python3
"""
Example usage of the NLWeb ingress system.

This script demonstrates how to use the Strategy + Factory Pattern-based
ingress system for processing different types of data.
"""

from tools.ingress.factory import auto_select_strategy, create_strategy, print_strategy_info
import asyncio
import json
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


def example_basic_usage():
    """Demonstrate basic strategy selection and usage."""
    print("=== Basic Usage Example ===\\n")

    # Show available strategies
    print("Available strategies:")
    print_strategy_info()
    print()

    # Example 1: Auto-detect strategy from file extension
    print("1. Auto-detecting strategy from file extension:")

    # Simulate different file types
    test_files = [
        "api-spec.json",
        "swagger.yaml",
        "MyInterface.java",
        "unknown.txt"
    ]

    for file_path in test_files:
        strategy = auto_select_strategy(file_path=file_path)
        if strategy:
            print(f"  {file_path} -> {strategy.get_strategy_name()}")
        else:
            print(f"  {file_path} -> No suitable strategy found")

    print()


def example_openapi_processing():
    """Demonstrate OpenAPI data processing."""
    print("=== OpenAPI Processing Example ===\\n")

    # Create sample OpenAPI data
    sample_openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": "Sample API",
            "version": "1.0.0",
            "description": "A sample API for demonstration"
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get all users",
                    "description": "Retrieve a list of all users",
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get user by ID",
                    "description": "Retrieve a specific user",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User object"
                        }
                    }
                }
            }
        }
    }

    # Convert to JSON string
    json_data = json.dumps(sample_openapi)

    # Auto-detect strategy from data content
    strategy = auto_select_strategy(data=json_data)

    if strategy:
        print(f"Detected strategy: {strategy.get_strategy_name()}")

        # Process the data
        documents, texts = strategy.process_data(
            json_data,
            "https://api.example.com/openapi.json",
            "example-api"
        )

        print(f"Generated {len(documents)} documents:")
        for i, doc in enumerate(documents):
            print(f"  {i+1}. {doc['name']} (ID: {doc['id']})")

        # Show a sample document structure
        if documents:
            print(f"\\nSample document structure:")
            sample_doc = documents[0]
            for key in ['id', 'url', 'name', 'site']:
                print(f"  {key}: {sample_doc[key]}")
            print(f"  schema_json: {sample_doc['schema_json'][:100]}...")
    else:
        print("No suitable strategy found for OpenAPI data")

    print()


def example_java_processing():
    """Demonstrate Java interface processing."""
    print("=== Java Interface Processing Example ===\\n")

    # Sample Java interface code
    sample_java = '''
package com.example.api;

/**
 * User management interface
 */
public interface UserService {
    
    /**
     * Get user by ID
     * @param userId the user ID
     * @return User object
     */
    User getUserById(Long userId);
    
    /**
     * Create a new user
     * @param userData user information
     * @return created User object
     */
    User createUser(UserData userData);
    
    /**
     * Delete user
     * @param userId the user ID to delete
     */
    void deleteUser(Long userId);
}
'''

    # Auto-detect strategy from data content
    strategy = auto_select_strategy(data=sample_java)

    if strategy:
        print(f"Detected strategy: {strategy.get_strategy_name()}")

        # Process the data
        documents, texts = strategy.process_data(
            sample_java,
            "java://com.example.api.UserService",
            "example-java"
        )

        print(f"Generated {len(documents)} documents:")
        for i, doc in enumerate(documents):
            print(f"  {i+1}. {doc['name']} (ID: {doc['id']})")

        # Show a sample document structure
        if documents:
            print(f"\\nSample document structure:")
            sample_doc = documents[0]
            for key in ['id', 'url', 'name', 'site']:
                print(f"  {key}: {sample_doc[key]}")
            print(f"  schema_json: {sample_doc['schema_json'][:150]}...")
    else:
        print("No suitable strategy found for Java interface data")
        print("Note: Java processing requires 'javalang' package to be installed")

    print()


def example_explicit_strategy():
    """Demonstrate explicit strategy creation."""
    print("=== Explicit Strategy Selection Example ===\\n")

    # Create strategies explicitly
    try:
        openapi_strategy = create_strategy("openapi")
        print(
            f"Created OpenAPI strategy: {openapi_strategy.get_strategy_name()}")
        print(
            f"  Supported extensions: {openapi_strategy.get_supported_extensions()}")
    except Exception as e:
        print(f"Error creating OpenAPI strategy: {e}")

    try:
        java_strategy = create_strategy("java")
        print(f"Created Java strategy: {java_strategy.get_strategy_name()}")
        print(
            f"  Supported extensions: {java_strategy.get_supported_extensions()}")
    except Exception as e:
        print(f"Error creating Java strategy: {e}")

    # Try creating invalid strategy
    try:
        invalid_strategy = create_strategy("nonexistent")
        print(f"Created strategy: {invalid_strategy}")
    except ValueError as e:
        print(f"Expected error for invalid strategy: {e}")

    print()


async def example_complete_pipeline():
    """Demonstrate a complete processing pipeline (without actual database storage)."""
    print("=== Complete Pipeline Example (Simulation) ===\\n")

    # Sample data
    sample_data = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "summary": "Test endpoint",
                    "responses": {"200": {"description": "Success"}}
                }
            }
        }
    }

    json_data = json.dumps(sample_data)

    # Step 1: Auto-select strategy
    strategy = auto_select_strategy(data=json_data)

    if not strategy:
        print("No suitable strategy found")
        return

    print(f"Step 1: Selected strategy: {strategy.get_strategy_name()}")

    # Step 2: Process data
    documents, texts = strategy.process_data(
        json_data, "test://example", "test-site")
    print(f"Step 2: Generated {len(documents)} documents")

    # Step 3: Simulate embedding generation (normally would use batch_get_embeddings)
    print("Step 3: Generating embeddings (simulated)...")
    embeddings = [[0.1, 0.2, 0.3] for _ in texts]  # Fake embeddings

    # Step 4: Add embeddings to documents
    for doc, embedding in zip(documents, embeddings):
        doc["embedding"] = embedding

    print("Step 4: Added embeddings to documents")

    # Step 5: Simulate database storage (normally would use client.upload_documents)
    print("Step 5: Uploading to database (simulated)...")

    print(f"✓ Pipeline complete: {len(documents)} documents processed")

    # Show final document structure
    if documents:
        doc = documents[0]
        print(f"\\nFinal document keys: {list(doc.keys())}")
        print(f"Document has embedding: {'embedding' in doc}")

    print()


def main():
    """Run all examples."""
    print("NLWeb Ingress System Examples")
    print("=" * 40)
    print()

    # Run synchronous examples
    example_basic_usage()
    example_openapi_processing()
    example_java_processing()
    example_explicit_strategy()

    # Run async example
    asyncio.run(example_complete_pipeline())

    print("Examples completed!")
    print()
    print("To use the ingress system in your code:")
    print("  from ingress.factory import auto_select_strategy")
    print("  strategy = auto_select_strategy(file_path='your_file.json')")
    print("  documents, texts = strategy.process_data(data, source_url, site)")


if __name__ == "__main__":
    main()
