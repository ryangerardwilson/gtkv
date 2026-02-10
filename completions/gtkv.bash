_gtkv_complete() {
  local cur
  cur="${COMP_WORDS[COMP_CWORD]}"
  COMPREPLY=(
    $(compgen -f -- "${cur}" | grep -E '\.gtkv\.html$' || true)
  )
}

complete -F _gtkv_complete gtkv
