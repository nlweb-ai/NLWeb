#!/usr/bin/env bash


function configure_llm_provider(){
  load_llm_provider_data
  # Select LLM provider if more than one is available
  if [ ${#LLM_PROVIDERS[@]} -gt 1 ]; then
      declare llm_selection
      _select_list llm_selection "Select LLM provider:" "${LLM_PROVIDERS[@]}"
      export SELECTED_LLM_PROVIDER="$llm_selection"
      update_preferred_provider "$SELECTED_LLM_PROVIDER"
  else
      # Use the only available provider or the preferred one
      export SELECTED_LLM_PROVIDER="${LLM_PREFERRED_PROVIDER:-${LLM_PROVIDERS[0]}}"
  fi
    
  # Now check the environment variables required for the selected LLM provider
  check_provider_env_vars "$SELECTED_LLM_PROVIDER"
}

function load_llm_provider_data(){
    local config_file="$REPO_DIR/code/config/config_llm.yaml"
    
    # Check if config file exists
    if [ ! -f "$config_file" ]; then
        _error "Config file not found: $config_file"
        return 1
    fi
    
    # Extract preferred provider
    preferred_provider=$(grep "^preferred_provider:" "$config_file" | cut -d ':' -f2 | tr -d ' ')
    
    # Extract all provider names
    declare -a PROVIDERS
    PROVIDERS=($(grep -A 50 "^providers:" "$config_file" | grep -E "^  [a-zA-Z_]+:" | sed 's/:.*$//' | tr -d ' '))
    
    # Export providers as an array for use in other functions
    export LLM_PROVIDERS=("${PROVIDERS[@]}")
    export LLM_PREFERRED_PROVIDER="$preferred_provider"
}


function check_provider_env_vars() {
  local provider="$1"
  local config_file="$REPO_DIR/code/config/config_llm.yaml"
  local start_line
  local end_line
  
  # Find the start line of the provider in the yaml file
  start_line=$(grep -n "^  $provider:" "$config_file" | cut -d: -f1)
  
  if [ -z "$start_line" ]; then
    _error "Provider $provider not found in config file"
    return 1
  fi
  
  # Find the end line of the provider section (next provider or end of file)
  end_line=$(tail -n +$((start_line + 1)) "$config_file" | grep -n "^  [a-zA-Z_]\+:" | head -1 | cut -d: -f1)
  if [ -z "$end_line" ]; then
    # If no next provider, use end of file
    end_line=$(wc -l < "$config_file")
  else
    # Adjust end_line to be relative to the file, not to tail's output
    end_line=$((start_line + end_line))
  fi
  
  # Extract the environment variable keys, excluding 'models' section
  local env_vars
  env_vars=$(sed -n "${start_line},${end_line}p" "$config_file" | grep -E "    [a-zA-Z_]+_env:" | 
              grep -v "models" | grep -v "api_version_env" | sed 's/.*: //' | tr -d '"' | tr -d "'")
  
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
      cp "${REPO_DIR}code/.env.template" "${REPO_DIR}code/.env"
    fi
    
    for var in "${missing_vars[@]}"; do
      local input
      _prompt_input "Please enter value for $var" input
      export "$var=$input"
      
      # Update the .env file
      if grep -q "^$var=" "$env_file"; then
        # If variable exists in .env, update it
        sed -i "s|^$var=.*|$var=\"$input\"|" "$env_file"
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
    _info "All required environment variables for $provider are set"
  fi
}

function update_preferred_provider() {
  local new_provider="$1"
  local config_file="$REPO_DIR/code/config/config_llm.yaml"
  
  if [ -z "$new_provider" ]; then
    _error "No provider specified to update as preferred"
    return 1
  fi
  
  # Check if the provider exists in the config file
  if ! grep -q "^  $new_provider:" "$config_file"; then
    _error "Provider $new_provider not found in config file"
    return 1
  fi
  
  # Use sed to update the preferred_provider line
  # Create a backup of the original file
  cp "$config_file" "${config_file}.bak"
  
  # Update the preferred_provider line
  sed -i "s/^preferred_provider:.*$/preferred_provider: $new_provider/" "$config_file"
  
  if [ $? -eq 0 ]; then
    _info "Updated preferred provider to $new_provider"
    rm "${config_file}.bak"
    return 0
  else
    _error "Failed to update preferred provider"
    # Restore from backup
    cp "${config_file}.bak" "$config_file"
    return 1
  fi
}