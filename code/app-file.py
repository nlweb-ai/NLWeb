# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file is the entry point for the NLWeb Sample App.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import os
from webserver.WebServer import fulfill_request, start_server
from dotenv import load_dotenv


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Get port from Azure environment or use default
    port = int(os.environ.get('PORT', 8000))
    
    # Start the server
    asyncio.run(start_server(
        host='0.0.0.0',
        port=port,
        fulfill_request=fulfill_request
    ))

if __name__ == "__main__":
    main()