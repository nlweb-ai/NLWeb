#!/usr/bin/env bash

# shell helpers to read and validate input

function _select_list_no_display() {
  variable="$1"
  message="${2:-Please make a selection}"
  list=($3)
  label=$4
  input=""
  found=1
  while [ $found -ne 0 ]; do
    printf "\e[35m> %s : \e[0m" "$message"
    read -r input
    if [[ " list " =~ " ${input} " ]]; then
      PS3="$(printf '\e[0m')?> "
      printf "\n\e[35m"
      select input in "${list[@]}"; do
        re='^[0-9]+$'
        if [[ $REPLY =~ $re ]]; then
          eval "$variable=$input"
          found=0
          break
        else
          if ! [[ " ${list[*]} " =~ " ${REPLY} " ]]; then
            echo "$REPLY is not a valid selection."
          else
            eval "$variable=$REPLY"
            found=0
            break
          fi
        fi
      done
      printf "\e[0m"
    elif ! [[ " ${list[*]} " =~ " ${input} " ]]; then
      _error "$input is not a valid $label."
    else
      eval "$variable=$input"
      found=0
    fi
  done

}
function _select_list() {
  variable="$1"
  message="${2:-Please make a selection}"
  # Use array assignment to preserve array elements
  shift 2
  # Now use all remaining arguments as array elements
  list=("$@")
  is_danger=${list[${#list[@]}-1]}
  # Check if the last element is a boolean flag
  if [[ "$is_danger" != "true" && "$is_danger" != "false" ]]; then
    is_danger="false"
  else
    # Remove the last element if it's a boolean flag
    unset 'list[${#list[@]}-1]'
  fi
  
  # configure the select prompt via the PS3 variable
  PS3="$(printf '\e[0m')?> "

  if [[ "$is_danger" == "true" ]]; then
    printf "\e[31m> %s : \e[0m" "$message"
    printf "\n\e[31m"
  else
    _prompt "$message"
    printf "\n\e[35m"
  fi
  select input in "${list[@]}"; do
    re='^[0-9]+$'
    if [[ $REPLY =~ $re ]]; then
      eval "$variable=\"$input\""
      break
    else
      if ! [[ " ${list[*]} " =~ " ${REPLY} " ]]; then
        echo "$REPLY is not a valid selection."
      else
        eval "$variable=\"$REPLY\""
        break
      fi
    fi
  done
  printf "\e[0m"
}

function _select_number() {
  variable="$1"
  message="${2:-Please enter a number between 1 and 9}"

  _prompt "> $message : "
  read -r input
  re='^[1-9]$'
  while ! [[ "$input" =~ $re ]]; do
    _error "$input is not a valid value. Please enter a number from 1 to 9."
    _prompt "$message"
    read -r input
  done
  eval "$variable=$input"
  printf "\e[0m"
}

function _select_yes_no() {
  variable="$1"
  message="${2:-Please make a selection}"
  is_danger=${3}

  # configure the select prompt via the PS3 variable
  PS3="$(printf '\e[0m')?> "

  if [[ "$is_danger" == "true" ]]; then
    printf "\e[31m> %s : \e[0m" "$message"
    printf "\n\e[31m"
  else
    _prompt "$message"
    printf "\n\e[35m"
  fi
  select input in yes no; do
    re='^[0-9]+$'
    if [[ $REPLY =~ $re ]]; then
      eval "$variable=$input"
      break
    else
      case $REPLY in
      yes)
        eval "$variable=yes"
        break
        ;;

      no)
        eval "$variable=no"
        break
        ;;
      *)
        _error "$REPLY is an Invalid selection, please select yes or no"
        ;;
      esac
    fi
  done
  printf "\e[0m"
}

function _prompt_input {
  input_description=${1}
  input_name=${2}
  is_danger=${3}

  if [[ "$is_danger" == "true" ]]; then
    printf " \e[31m> %s : \e[0m" "$input_description"
  else
    echo -n "> $input_description : "
  fi

  read $input_name
}

