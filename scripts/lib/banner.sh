#!/usr/bin/env/bash

function show_banner {
  cat <<"EOF"
          __              __  
   ____  / /      _____  / /_ 
  / __ \/ / | /| / / _ \/ __ \
 / / / / /| |/ |/ /  __/ /_/ /
/_/ /_/_/ |__/|__/\___/_.___/ 
                              
EOF

  echo ""
}

function usage() {
  # me is defined in the entry point script that sources this file.

  _helpText="Usage: nlweb <command> <flags>
  commands:
    init  Configure the llm provider and retrieval endpoint
    check Verify connectivity for selected configuration and environment variables
    app   Run the web application
    run   End to End flow. Runs init, check and app.
    example:
      nlweb init
      nlweb run
  flags:
    -h, --help  Show this help message and exit
    -d, --debug Enable debug mode
  example:
    nlweb init -d    
"
  _info "$_helpText" 1>&2
  exit 0
}