#!/bin/sh
# Normalize only this plugin's Skill calls and directly typed commands.
# Requires json-util.sh with a detected parser.

skillu_name() {
  _SKU_EVENT=$(jsonu_get_root_string "$1" "hook_event_name")
  if [ "$_SKU_EVENT" = "UserPromptExpansion" ]; then
    [ "$(jsonu_get_root_string "$1" "expansion_type")" = "slash_command" ] || return 1
    _SKU_NAME=$(jsonu_get_root_string "$1" "command_name")
    _SKU_NAME=${_SKU_NAME#/}
    case "$_SKU_NAME" in
      rtl-agent-team:*) ;;
      *)
        # Some clients report a short name. Require a qualified original prompt
        # so another plugin's identically named command cannot acquire RAT state.
        _SKU_PROMPT=$(jsonu_get_root_string "$1" "prompt")
        _SKU_QUALIFIED=${_SKU_PROMPT%% *}
        [ "$_SKU_QUALIFIED" = "/rtl-agent-team:$_SKU_NAME" ] || return 1
        _SKU_NAME="rtl-agent-team:$_SKU_NAME"
        ;;
    esac
  else
    _SKU_NAME=$(jsonu_get_input_string "$1" "skill")
  fi
  case "$_SKU_NAME" in
    rtl-agent-team:*)
      _SKU_SHORT=${_SKU_NAME#rtl-agent-team:}
      case "$_SKU_SHORT" in ''|*[!a-z0-9-]*) return 1 ;; esac
      printf '%s' "$_SKU_NAME"
      ;;
    *) return 1 ;;
  esac
}
