#!/usr/bin/env bash


declare RETRIEVAL_CONFIG_FILE="$REPO_DIR/code/config/config_retrieval.yaml"

function configure_retrieval_endpoint(){
    load_retreival_endpoint_data
    # Select Retreival Endpoint if more than one is available
    if [ ${#RETRIEVAL_ENDPOINTS[@]} -gt 1 ]; then
        declare endpoint_selection
        _select_list endpoint_selection "Select Retrieval endpoint:" "${RETRIEVAL_ENDPOINTS[@]}"
        export SELECTED_RETRIEVAL_ENDPOINT="$endpoint_selection"
        update_preferred_endpoint "$SELECTED_RETRIEVAL_ENDPOINT"
    else
      # Use the only available provider or the preferred one
      export SELECTED_RETRIEVAL_ENDPOINT="${RETRIEVAL_PREFERRED_PROVIDER:-${RETRIEVAL_ENDPOINTS[0]}}"
    fi    

    check_endpoint_env_vars "$SELECTED_RETRIEVAL_ENDPOINT"
}

function load_retreival_endpoint_data(){
    local config_file="$RETRIEVAL_CONFIG_FILE"
    
    # Check if config file exists
    if [ ! -f "$config_file" ]; then
        _error "Config file not found: $config_file"
        return 1
    fi
    
    # Extract preferred provider
    preferred_endpoint=$(grep "^preferred_endpoint:" "$config_file" | cut -d ':' -f2 | tr -d ' ')
    
    # Extract all endpoint names - improved to capture all entries regardless of file size
    # Find start line of endpoints section
    local start_line=$(grep -n "^endpoints:" "$config_file" | cut -d: -f1)
    
    # If endpoints section is not found, return error
    if [ -z "$start_line" ]; then
        _error "Endpoints section not found in config file"
        return 1
    fi
    
    # Extract all endpoint names from the section
    declare -a ENDPOINTS
    ENDPOINTS=($(tail -n +$((start_line + 1)) "$config_file" | grep -E "^  [a-zA-Z_0-9]+:" | sed 's/:.*$//' | tr -d ' '))
    
    # Print endpoints for debugging
    if [ "$DEBUG" = true ]; then
        _debug "Preferred endpoint: $preferred_endpoint"
        _debug "Available endpoints: ${ENDPOINTS[*]}"
    fi
    
    # Export endpoints as an array for use in other functions
    export RETRIEVAL_ENDPOINTS=("${ENDPOINTS[@]}")
    export RETRIEVAL_PREFERRED_PROVIDER="$preferred_endpoint"
}

function check_endpoint_env_vars() {
  local endpoint="$1"
  local config_file="$RETRIEVAL_CONFIG_FILE"
  
  # Debug output - print the selected endpoint
  if [ "$DEBUG" = true ]; then
    _debug "Checking environment variables for endpoint: $endpoint"
  fi

  # Use awk to extract environment variables for the specific endpoint
  # This is a more reliable method than using line numbers and sed
  local env_vars
  env_vars=$(awk -v endpoint="  $endpoint:" '
    # Set a flag when we find our endpoint
    $0 ~ endpoint {in_section=1; next}
    # Reset the flag when we find the next endpoint
    /^  [a-zA-Z0-9_]+:/ {if(in_section) in_section=0}
    # Print lines with environment variables while we are in our section
    in_section && /_env:/ && !/models/ && !/api_version_env/ {
      gsub(/.*: *|["'\'']/, "");  # Remove key part and quotes
      print;
    }
  ' "$config_file")
  
  if [ "$DEBUG" = true ]; then
    _debug "Required environment variables for $endpoint: $env_vars"
  fi
  
  # Check if each environment variable is set
  local missing_vars=()
  for env_var in $env_vars; do
    if [ -z "${!env_var}" ]; then
      missing_vars+=("$env_var")
    fi
  done
  
  # If there are missing variables, prompt the user to set them
  if [ ${#missing_vars[@]} -gt 0 ]; then
    local env_file="$REPO_DIR/code/.env"
    
    if [ ! -f "$env_file" ]; then
      if [ -f "${REPO_DIR}/code/.env.template" ]; then
        cp "${REPO_DIR}/code/.env.template" "${REPO_DIR}/code/.env"
      else
        touch "$env_file"
      fi
    fi
    
    _info "The following environment variables are required for $endpoint:"
    for var in "${missing_vars[@]}"; do
      local input
      _prompt_input "Please enter value for $var" input
      export "$var=$input"
      
      # Update the .env file
      if grep -q "^$var=" "$env_file"; then
        # If variable exists in .env, update it
        sed -i "s|^$var=.*|$var=\"$input\"|" "$env_file"
        if [ "$DEBUG" = true ]; then
          _debug "Updated $var in $env_file"
        fi
      else
        # If variable doesn't exist in .env, append it
        echo "$var=\"$input\"" >> "$env_file"
        if [ "$DEBUG" = true ]; then
          _debug "Added $var to $env_file"
        fi
      fi
    done
    _info "Environment variables updated in $env_file"
  else
    _info "All required environment variables for $endpoint are set"
  fi
}

function update_preferred_endpoint(){
  local new_endpoint="$1"
  local config_file="$RETRIEVAL_CONFIG_FILE"

  if [ -z "$new_endpoint" ]; then
    _error "No endpoint specified to update as preferred"
    return 1
  fi
  
  # Check if the provider exists in the config file
  if ! grep -q "^  $new_endpoint:" "$config_file"; then
    _error "Endpoint $new_endpoint not found in config file"
    return 1
  fi
  
  # Use sed to update the preferred_provider line
  # Create a backup of the original file
  cp "$config_file" "${config_file}.bak"
  
  # Update the preferred_provider line
  sed -i "s/^preferred_endpoint:.*$/preferred_endpoint: $new_endpoint/" "$config_file"
  
  if [ $? -eq 0 ]; then
    _info "Updated preferred endpoint to $new_endpoint"
    rm "${config_file}.bak"
    return 0
  else
    _error "Failed to update preferred provider"
    # Restore from backup
    cp "${config_file}.bak" "$config_file"
    return 1
  fi

}