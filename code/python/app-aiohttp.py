# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Entry point for the NLWeb Sample App with aiohttp server.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv


async def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Suppress verbose HTTP client logging from OpenAI SDK
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    # Suppress Azure SDK HTTP logging
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    
    # Suppress webserver middleware INFO logs
    logging.getLogger("webserver.middleware.logging_middleware").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    
    # Initialize router
    import core.router as router
    router.init()
    
    # Initialize LLM providers
    import core.llm as llm
    llm.init()
    
    # Initialize retrieval clients
    import core.retriever as retriever
    retriever.init()
    
    # Determine which server to use
    use_aiohttp = os.environ.get('USE_AIOHTTP', 'true').lower() == 'true'
    
    if use_aiohttp:
        print("Starting aiohttp server...")
        from webserver.aiohttp_server import AioHTTPServer
        server = AioHTTPServer()
        await server.start()
    else:
        print("Starting legacy server...")
        from webserver.WebServer import fulfill_request, start_server
        
        # Get port from Azure environment or use default
        port = int(os.environ.get('PORT', 8000))
        
        # Start the server
        await start_server(
            host='0.0.0.0',
            port=port,
            fulfill_request=fulfill_request
        )


if __name__ == "__main__":
    asyncio.run(main())