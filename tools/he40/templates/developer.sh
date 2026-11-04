#!/bin/sh
# /3rd_rw/developer.sh
#
# EARLY root boot hook. Called by /basic/autorun.sh at line ~90, i.e. BEFORE:
#   ms_service (162) -> hisenseUI (168) -> app_man (177) -> delayrun (190)
#
# Use it for:
#   - bind-mounting modified /basic/am_start.ini, am_config, delayrun.sh
#   - stubbing unwanted services (ms_service, start-UI.sh, ...)
#   - starting your own root service
#   - starting root_loop/sshd earlier than the late HamService wrapper
#
# Keep it idempotent and log everything. If it breaks the UI/AM, remove it via
# SSH/root_loop and reboot.
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/basic/bin
export PATH

# Everything to a log (comment out for serial/debug)
exec >>/3rd_rw/developer.log 2>&1
echo "=== developer.sh $(date) boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null) ==="
# set -x

# ---------------------------------------------------------------------------
# 1) Your own root service
# ---------------------------------------------------------------------------
# mkdir -p /3rd_rw/bin
# /3rd_rw/bin/mydaemon &
# echo "mydaemon started: $!"

# ---------------------------------------------------------------------------
# 2) Replace a ro config BEFORE app_man reads it (am_start/am_config)
#    Put modified copies under /3rd_rw/etc/.
# ---------------------------------------------------------------------------
# mount --bind /3rd_rw/etc/am_start.ini /basic/am_start.ini
# mount --bind /3rd_rw/etc/am_config    /basic/am_config
# echo "am configs bound"

# ---------------------------------------------------------------------------
# 3) Replace a ro service script/binary BEFORE autorun runs it.
#    Example: stub ms_service (autorun line 162)
# ---------------------------------------------------------------------------
# mkdir -p /3rd_rw/stubs
# printf '#!/bin/sh\nexit 0\n' > /3rd_rw/stubs/true
# chmod 755 /3rd_rw/stubs/true
# mount --bind /3rd_rw/stubs/true /3rd/ms-screen/ms_service
# echo "ms_service stubbed"

# Example: custom UI start script (autorun line 168)
# mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
# echo "custom start-UI bound"

# Example: modified delayrun (autorun line 190)
# mount --bind /3rd_rw/etc/delayrun.sh /basic/delayrun.sh
# echo "delayrun bound"

# ---------------------------------------------------------------------------
# 4) Start root loop / SSH earlier (optional; the HamService wrapper also does)
# ---------------------------------------------------------------------------
# /bin/sh /3rd_rw/appdata/root_loop.sh &
# [ -x /3rd_rw/sshd/start_sshd.sh ] && /bin/sh /3rd_rw/sshd/start_sshd.sh &

echo "=== developer.sh done ==="
exit 0
