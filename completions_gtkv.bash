_gtkv_complete() {
  local cur
  cur="${COMP_WORDS[COMP_CWORD]}"
  case "${cur}" in
    --image=*)
      COMPREPLY=( $(compgen -f -- "${cur#--image=}") )
      ;;
    -*)
      COMPREPLY=( $(compgen -W "-h --help -v --version -u --upgrade --image" -- "${cur}") )
      ;;
    *)
      COMPREPLY=( $(compgen -f -X '!*.docv' -- "${cur}") )
      ;;
  esac
  compopt -o filenames 2>/dev/null || true
}

complete -F _gtkv_complete gtkv
