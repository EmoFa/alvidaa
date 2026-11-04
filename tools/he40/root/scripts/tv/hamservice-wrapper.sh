#!/bin/sh
# /3rd_rw/hamservice/HamService  (wrapper; install via deploy_sshd.sh)
# Early-ish boot hook (startHam.sh, after ~15 s): starts the root loop and
# Dropbear, then executes the real HamService. Reversible:
#   rm /3rd_rw/hamservice/HamService
#   ln -s /3rd/hamservice/HamService /3rd_rw/hamservice/HamService
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH

/bin/sh /3rd_rw/appdata/root_loop.sh >/dev/null 2>&1 &
[ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh >/dev/null 2>&1 &

exec /3rd/hamservice/HamService "$@"
