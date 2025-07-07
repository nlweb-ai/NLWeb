"""
Java interface ingress strategy for NLWeb.

This strategy handles Java interface files, parsing them and converting 
to Schema.org APIReference format for vector database storage.
"""

import json
from typing import List, Dict, Any, Tuple, Optional
import javalang

from .base_strategy import BaseIngressStrategy
from tools.db_load_utils import int64_hash


class JavaStrategy(BaseIngressStrategy):
    """
    Strategy for ingesting Java interface files.

    Supports:
    - Java interface files (.java)
    - Parses methods, parameters, return types
    - Converts to Schema.org APIReference format
    """

    def validate_input(self, data: Any) -> bool:
        """
        Validate that the input data is a valid Java interface.

        Args:
            data: Data to validate (should be Java source code string)

        Returns:
            True if data appears to be valid Java interface code
        """
        try:
            # Must be a string
            if not isinstance(data, str):
                return False

            # Try to parse the Java code
            tree = javalang.parse.parse(data)

            # Check if it contains interface declarations
            has_interface = False
            for path, node in tree:
                if isinstance(node, javalang.tree.InterfaceDeclaration):
                    has_interface = True
                    break

            return has_interface

        except Exception:
            return False

    def process_data(self, data: Any, source_url: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process Java interface and convert to standardized documents.

        Args:
            data: Java source code string
            source_url: File path or identifier for the source
            site: Site identifier

        Returns:
            Tuple of (documents, texts_for_embedding)
        """
        try:
            # Parse the Java code
            parsed_data = self._parse_java_interface(data, source_url)

            # Convert to Schema.org APIReference documents
            api_references = self._java_interface_to_schema_org(
                parsed_data, source_url)

            # Convert to standardized document format
            documents = []
            texts_for_embedding = []

            for api_ref in api_references:
                # Convert to JSON string for embedding
                json_data = json.dumps(
                    api_ref, ensure_ascii=False).replace("\\n", " ")

                # Extract URL and name
                url = api_ref.get(
                    "url", f"synthetic:{site}:{api_ref.get('identifier', 'unknown')}")
                name = api_ref.get("name", "Untitled Java Method")

                # Create standardized document
                doc = {
                    "id": str(int64_hash(url)),
                    "schema_json": json_data,
                    "url": url,
                    "name": name,
                    "site": site
                }

                documents.append(doc)
                texts_for_embedding.append(json_data)

            return documents, texts_for_embedding

        except Exception as e:
            print(f"Error processing Java interface: {str(e)}")
            return [], []

    def get_supported_extensions(self) -> List[str]:
        """Get file extensions supported by this strategy."""
        return ['.java']

    def get_strategy_name(self) -> str:
        """Get human-readable name for this strategy."""
        return "Java Interface"

    @staticmethod
    def load_from_file(file_path: str) -> str:
        """
        Load Java source code from file.

        Args:
            file_path: Path to the Java file

        Returns:
            Java source code as string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading Java file {file_path}: {str(e)}")
            raise

    def _parse_java_interface(self, java_code: str, file_path: str) -> Dict[str, Any]:
        """
        Parse Java interface source code.

        Args:
            java_code: Java source code
            file_path: Original file path for reference

        Returns:
            Parsed Java interface data
        """
        print(f"Parsing Java interface from: {file_path}")

        try:
            # Parse the Java code
            tree = javalang.parse.parse(java_code)

            if not tree:
                raise ValueError(
                    f"Failed to parse Java code from: {file_path}")

            return {
                'tree': tree,
                'source': java_code,
                'file_path': file_path
            }
        except Exception as e:
            print(f"Error parsing Java code: {str(e)}")
            raise

    def _extract_java_type_name(self, java_type) -> str:
        """
        Extract type name from javalang type object.

        Args:
            java_type: javalang type object

        Returns:
            String representation of the type
        """
        if java_type is None:
            return "void"

        if hasattr(java_type, 'name'):
            # Basic type like String, int, etc.
            type_name = java_type.name

            # Handle generic types
            if hasattr(java_type, 'arguments') and java_type.arguments:
                generic_args = []
                for arg in java_type.arguments:
                    if hasattr(arg, 'type'):
                        generic_args.append(
                            self._extract_java_type_name(arg.type))
                    else:
                        generic_args.append(str(arg))
                type_name += f"<{', '.join(generic_args)}>"

            # Handle array types
            if hasattr(java_type, 'dimensions') and java_type.dimensions:
                type_name += "[]" * len(java_type.dimensions)

            return type_name

        return str(java_type)

    def _java_interface_to_schema_org(self, parsed_data: Dict[str, Any], source_url: str = None) -> List[Dict[str, Any]]:
        """
        Convert parsed Java interface to Schema.org APIReference objects.

        Args:
            parsed_data: Parsed Java interface data
            source_url: Source URL/path for reference

        Returns:
            List of Schema.org APIReference documents
        """
        documents = []
        tree = parsed_data['tree']
        file_path = parsed_data['file_path']

        # Extract package information
        package_name = tree.package.name if tree.package else "default"

        # Find interface declarations
        interface_declarations = []
        for path, node in tree:
            if isinstance(node, javalang.tree.InterfaceDeclaration):
                interface_declarations.append(node)

        if not interface_declarations:
            print("No interface declarations found in the Java file")
            return documents

        for interface in interface_declarations:
            interface_name = interface.name
            interface_docs = ""

            # Extract interface-level documentation
            if interface.documentation:
                interface_docs = interface.documentation.strip()

            # Generate base URL for this interface
            base_url = source_url or f"java://{package_name}.{interface_name}"

            # Process each method in the interface
            for method in interface.body:
                if isinstance(method, javalang.tree.MethodDeclaration):
                    method_name = method.name
                    method_docs = ""

                    # Extract method documentation
                    if method.documentation:
                        method_docs = method.documentation.strip()

                    # Extract return type
                    return_type = self._extract_java_type_name(
                        method.return_type)

                    # Extract parameters
                    parameters = []
                    for param in method.parameters:
                        param_type = self._extract_java_type_name(param.type)
                        param_name = param.name

                        parameters.append({
                            "@type": "PropertyValue",
                            "name": param_name,
                            "description": f"Parameter of type {param_type}",
                            "valueRequired": True,
                            "dataType": param_type
                        })

                    # Extract exceptions
                    exceptions = []
                    if method.throws:
                        for exception_type in method.throws:
                            exception_name = self._extract_java_type_name(
                                exception_type)
                            exceptions.append(exception_name)

                    # Generate method signature
                    param_types = [self._extract_java_type_name(
                        p.type) for p in method.parameters]
                    method_signature = f"{method_name}({', '.join(param_types)})"

                    # Build method URL
                    method_url = f"{base_url}#{method_signature}"

                    # Create Schema.org APIReference document for the method
                    api_reference = {
                        "@type": "APIReference",
                        "name": f"{interface_name}.{method_name}",
                        "description": method_docs or f"{method_name} method from {interface_name} interface",
                        "url": method_url,
                        "identifier": f"{package_name}.{interface_name}.{method_name}",
                        "programmingLanguage": "Java",
                        "applicationCategory": "JavaInterface",
                        "operatingSystem": "Any",
                        "isPartOf": {
                            "@type": "SoftwareApplication",
                            "name": interface_name,
                            "description": interface_docs or f"Java interface {interface_name}",
                            "applicationCategory": "JavaInterface",
                            "operatingSystem": "Any",
                            "programmingLanguage": "Java"
                        },
                        "potentialAction": {
                            "@type": "Action",
                            "name": method_signature,
                            "description": method_docs or f"Call {method_name} method",
                            "target": {
                                "@type": "EntryPoint",
                                "urlTemplate": method_url,
                                "httpMethod": "CALL",
                                "contentType": "application/java"
                            },
                            "object": parameters,
                            "result": {
                                "@type": "DataDownload",
                                "name": f"Method Return Value",
                                "description": f"Returns {return_type}",
                                "encodingFormat": return_type
                            }
                        },
                        "keywords": [interface_name, "Java", "Interface", "Method", package_name],
                        "category": "java-interface",
                        "version": "1.0",
                        "codeRepository": source_url,
                        "returnType": return_type,
                        "parameters": param_types,
                        "exceptions": exceptions
                    }

                    documents.append(api_reference)

        print(
            f"Converted Java interface to {len(documents)} APIReference documents")
        return documents
