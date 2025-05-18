#!/usr/bin/env bash
declare INSTALL_PATH=$(pwd)/scripts/cli
declare SCRIPTS_PATH=$(pwd)/scripts
source "$SCRIPTS_PATH/lib/shell_logger.sh"

if [[ "$0" = "$BASH_SOURCE" ]]; then
    _error "WARNING: setup.sh should not executed directly. Please source this script."
    _info "source setup.sh"
    exit 1
fi

export PATH=$PATH:$INSTALL_PATH
alias nlweb="nlweb.sh"

if [[ $? == 0 ]]; then
  _success "Added nlweb temporarily ($INSTALL_PATH) to PATH"
fi
