#!/bin/sh
# alvidaa root hook v13 — CANONICAL TEMPLATE (tools/otaTest-hook.sh)
#
# This is the exact script the installer (launcher/hookinstall.html) writes
# to /var/local/otaTest.sh, where it runs as root at every boot. The
# installer injects the install timestamp into the header line below.
#
# Changelog
#   v13 (2026-11-05, ds41-acked design; NOT yet deployed to the TV):
#     - Watchdog loop unbound: 40x30s (~20 min) -> immortal, so dropbear/
#       telnetd/alvidaa-bridge keep getting resurrected for the life of the
#       boot instead of only the first ~20 minutes.
#     - KILL-SWITCH RE-CHECKED PER ITERATION: v12 checks /var/local/hook.off
#       once at script start, so an immortal loop would bypass it forever.
#       The loop body now exits cleanly the moment the flag appears —
#       hook.off still disarms everything without editing the hook (resurrect
#       ions stop immediately; already-running daemons wind down at next
#       boot). sleep 30 cadence kept — no busy spin. The kill -9
#       $(pidof dropbear) line is unchanged (separate known issue, out of
#       scope per ds41).
#   v12 (2026-11-04, live on 50A51HUV 09.01O.P0813, md5 of the running copy
#        fde595a0251cf4ef6b964f9f6ffb72ed — its header/footer still say
#        "v11" cosmetically; this template is the corrected canonical):
#     - EARLY bridge start: right after tvrc/tvfw sourcing, a pidof-guarded
#       retry loop (60 x 2s) starts alvidaa-bridge as soon as its binary
#       exists — loopback MQTT needs no LAN and the bridge retries mosquitto
#       internally, so the bridge is up ~15s into boot instead of ~2min.
#     - LATE-start guard: the "Start native alvidaa bridge" block gained
#       `&& ! pidof alvidaa-bridge` so the late block can never double-start
#       against the early loop (two servers would fight over one MQTT
#       client identity and kick each other off the broker).
#     - Watchdog keepalive: the 30s watchdog now also restarts
#       alvidaa-bridge if it dies (pidof-guarded) and refreshes the 8770
#       iptables ACCEPT alongside 2222/2323.
#     - Boot-time iptables gained the 8770 ACCEPT (v11 opened only
#       2222/2323 at boot).
#   v11 (2026-10-30): tvtools fetch over /dev/tcp, telnetd 2323, dropbear
#       2222 (keys-only, -D /var/local/roothome), rootdumps, watchdog.
#
# Remove entirely: rm -rf /var/local/otaTest.sh /var/local/tvtools /var/local/roothome
# Kill-switch: touch /var/local/hook.off (this script exits 0 before anything).
[ -f /var/local/hook.off ] && exit 0
# alvidaa root hook v13 — installed <ISO timestamp injected by hookinstall.html>
# remove: rm -rf /var/local/otaTest.sh /var/local/tvtools /var/local/roothome
exec > /var/local/otaTest.log 2>&1
chmod 644 /var/local/otaTest.log
[ -f /var/local/tvrc ] && . /var/local/tvrc
[ -f /var/local/tvfw ] && . /var/local/tvfw
# alvidaa bridge v12 early start: loopback MQTT needs no LAN and the bridge
# retries mosquitto internally, so it comes up ~15s into boot instead of
# ~2min. Watchdog below and this loop are both pidof-guarded.
(if [ -f /var/local/alvidaa/alvidaa-bridge ]; then
  n=0
  while [ $n -lt 60 ]; do
    pidof alvidaa-bridge > /dev/null 2>&1 || /var/local/alvidaa/alvidaa-bridge -keys /var/local/alvidaa/keys -assets /var/local/alvidaa/launcher -config /var/local/alvidaa/config.json -addr 0.0.0.0:8770 -mqtt 127.0.0.1:36669 >> /var/local/alvidaa/bridge.log 2>&1 &
    pidof alvidaa-bridge > /dev/null 2>&1 && break
    sleep 2; n=$((n+1))
  done
fi) &
date
if [ 1 = 1 ]; then
  n=0
  while [ $n -lt 30 ]; do
    ifconfig 2>/dev/null | grep -q 'inet addr' && break
    sleep 2; n=$((n+1))
  done
  date; echo network wait: $n
  ok=0
  for i in 1 2 3 4 5; do
    exec 3<>/dev/tcp/192.168.0.85/4444 && ok=1 && break
    sleep 5
  done
  if [ $ok = 1 ]; then
    cat <&3 > /var/local/tvtools.tar.gz
    exec 3<&-
    sync
    mkdir -p /var/local/tvtools
    tar xzf /var/local/tvtools.tar.gz -C /var/local/tvtools && echo UNTAR-OK
    chmod 755 /var/local/tvtools/busybox /var/local/tvtools/dropbear /var/local/tvtools/dropbearkey
  else
    echo FETCH-FAILED
  fi
else
  echo tvtools already present — skipping fetch
fi
/var/local/tvtools/busybox echo busybox-ok
mkdir -p /var/local/roothome/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAKLC19p1Uj2t18xmrhWoryFKCEe4X/fjB+hU3sNNcmj alvidaa-tv-root' > /var/local/roothome/authorized_keys
cp /var/local/roothome/authorized_keys /var/local/roothome/.ssh/authorized_keys
chown root:root /var/local/roothome/authorized_keys /var/local/roothome/.ssh/authorized_keys
chmod 600 /var/local/roothome/authorized_keys /var/local/roothome/.ssh/authorized_keys
chmod 755 /var/local/roothome; chmod 700 /var/local/roothome/.ssh
[ -f /var/local/tvtools/host_ed25519 ] || /var/local/tvtools/dropbearkey -t ed25519 -f /var/local/tvtools/host_ed25519
iptables -C INPUT -p tcp --dport 2222 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 2222 -j ACCEPT
iptables -C INPUT -p tcp --dport 2323 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 2323 -j ACCEPT
iptables -C INPUT -p tcp --dport 8770 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 8770 -j ACCEPT
(i=0; while [ $i -lt 12 ]; do sleep 15; iptables -C INPUT -p tcp --dport 2222 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 2222 -j ACCEPT; iptables -C INPUT -p tcp --dport 2323 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 2323 -j ACCEPT; iptables -C INPUT -p tcp --dport 8770 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 8770 -j ACCEPT; i=$((i+1)); done) &
echo '--- authorized_keys on disk ---'
cat /var/local/roothome/authorized_keys
md5sum /var/local/tvtools/dropbear /var/local/roothome/authorized_keys
/var/local/tvtools/busybox telnetd -p 2323 -l /bin/sh && echo TELNETD-OK-2323
kill -9 $(pidof dropbear) 2>/dev/null
/var/local/tvtools/dropbear -F -E -p 2222 -r /var/local/tvtools/host_ed25519 -D /var/local/roothome -s > /var/local/dropbear.log 2>&1 &
sleep 1; chmod 644 /var/local/dropbear.log; pgrep -f dropbear > /dev/null && echo DROPBEAR-OK-2222
# v13 watchdog: immortal, but the kill-switch is re-checked every iteration
# so /var/local/hook.off still disarms it without editing the hook.
(while [ 1 = 1 ]; do sleep 30; [ -f /var/local/hook.off ] && exit 0; pgrep -f 'dropbear -F' > /dev/null || { kill -9 $(pidof dropbear) 2>/dev/null; /var/local/tvtools/dropbear -F -E -p 2222 -r /var/local/tvtools/host_ed25519 -D /var/local/roothome -s >> /var/local/dropbear.log 2>&1 & chmod 644 /var/local/dropbear.log; }; pidof telnetd > /dev/null || /var/local/tvtools/busybox telnetd -p 2323 -l /bin/sh; [ -f /var/local/alvidaa/alvidaa-bridge ] && { pidof alvidaa-bridge > /dev/null || /var/local/alvidaa/alvidaa-bridge -keys /var/local/alvidaa/keys -assets /var/local/alvidaa/launcher -config /var/local/alvidaa/config.json -addr 0.0.0.0:8770 -mqtt 127.0.0.1:36669 >> /var/local/alvidaa/bridge.log 2>&1 & }; done) &
D=/var/local/rootdumps; mkdir -p $D; chmod 755 $D; chmod 644 $D/* 2>/dev/null
ps
iptables -L -n 2>&1 | head -60
cp /etc/0001-cli-login-aes.pem $D/ 2>/dev/null
cp /etc/0002-cli-login-sign-public.pem $D/ 2>/dev/null
cp /usr/local/bin/check_usb_key $D/ 2>/dev/null
chmod 644 $D/* 2>/dev/null
# Start native alvidaa bridge (late fallback — early loop above owns first
# start; this is guarded so the two can never double-start)
if [ -f /var/local/alvidaa/alvidaa-bridge ] && ! pidof alvidaa-bridge > /dev/null 2>&1; then
  /var/local/alvidaa/alvidaa-bridge \
    -keys /var/local/alvidaa/keys \
    -assets /var/local/alvidaa/launcher \
    -config /var/local/alvidaa/config.json \
    -addr 0.0.0.0:8770 \
    -mqtt 127.0.0.1:36669 > /var/local/alvidaa/bridge.log 2>&1 &
fi

echo 'hook v13 done'
