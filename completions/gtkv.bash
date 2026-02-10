_gtkv_complete() {
  local cur
  cur="${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=( $(compgen -f -X '!*.gtkv.html' -- "${cur}") )
  compopt -o filenames 2>/dev/null || true
}

complete -F _gtkv_complete gtkv
