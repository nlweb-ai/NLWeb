#!/usr/bin/env bash

#!/usr/bin/env bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
REPO_DIR=$SCRIPT_DIR/../../

# includes
source "$SCRIPT_DIR/../lib/banner.sh"
source "$SCRIPT_DIR/../lib/shell_logger.sh"
source "$SCRIPT_DIR/../lib/shell_inputs.sh"
source "$SCRIPT_DIR/../lib/llm_providers.sh"
source "$SCRIPT_DIR/../lib/retrieval_endpoints.sh"

declare DEBUG=false
declare me=$(basename "$0")

function init(){
  configure_llm_provider
  configure_retrieval_endpoint
  }

function dataload(){
  local rss_url
  _prompt_input "Please enter an RSS url" rss_url

  local site_name
  _prompt_input "Please enter a site name" site_name

  _debug "Loading data from $rss_url site name: $site_name"
  python -m data_loading.db_load "$rss_url" "$site_name"
}

function init_python(){
  python -m venv venv
  source venv/bin/activate

  pushd "$REPO_DIR/code" > /dev/null || exit 1
    pip install -r requirements.txt
  popd || exit 1

  _info "Run 'source venv/bin/activate' to activate the virtual environment"
}

function run(){
  init
  check
  dataload
  app
}

function check(){
    pushd "$REPO_DIR/code" > /dev/null || exit 1
        python azure_connectivity.py 
    popd || exit 1
}

function app(){
    pushd "$REPO_DIR/code" > /dev/null || exit 1
        python app-file.py
    popd || exit 1
}

# utility functions
function parse_args() {
  while (("$#")); do
    case "${1}" in
    data-load)
        shift 1
        export command="dataload"
        ;;       
    check)
        shift 1
        export command="check"
        ;;   
    run)
        shift 1
        export command="run"
        ;;           
    app)
        shift 1
        export command="app"
        ;;         
    init)
        shift 1
        export command="init"
        ;;
    init-python)
        shift 1
        export command="initpython"
        ;;        
    -h | --help)
        shift 1
        export command="help"
        usage
        ;;
    -d | --debug)
        shift 1
        DEBUG=true
        ;;
    *) # preserve positional arguments
        PARAMS+="${1} "
        shift
        ;;
    esac
  done

  args=($PARAMS)
  if [[ -z "$command" ]]; then
    usage
  fi  
}

process_command() {
  case "$command" in
  init)
    init
    ;;
  run)
    run
    ;;    
  check)
    check
    ;;
  dataload)
    dataload
    ;;
  initpython)
    init_python
    ;;
  view)
    view
    ;;
  app)
    app
    ;;
  esac
}

function main(){
    show_banner

    parse_args "$@"
    process_command
}

# invoke main last to ensure all functions and variables are defined
main "$@"

