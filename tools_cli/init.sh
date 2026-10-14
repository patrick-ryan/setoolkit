# set up folder, .env, and aliases


alias ,rt="cd \$(,print_rt)"

function ,qs() {
    ,print_qs $1 && cd $(cat /tmp/qs)
}
