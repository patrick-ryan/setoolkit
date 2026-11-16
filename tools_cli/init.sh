# set up folder, .env, and aliases


function ,rt() {
    local target
    target="$(,print_rt)" || return $?
    cd -- "$target"
}

function ,qs() {
    local result target exit_code
    result="$(mktemp "${TMPDIR:-/tmp}/setoolkit-qs.XXXXXXXX")" || return $?
    exit_code=0
    if ,print_qs --output "$result" "$@"; then
        target="$(cat "$result")" || exit_code=$?
    else
        exit_code=$?
    fi
    rm -f -- "$result"
    if [ "$exit_code" -ne 0 ]; then
        return "$exit_code"
    fi
    [ -n "$target" ] || return 1
    cd -- "$target"
}
