#!/bin/sh
# custom start-UI: same runtime as the stock start-UI.sh, but loads
# /3rd_rw/UI/custom.html instead of /3rd_rw/UI/index.html.
#
# Install (safe, file-level bind mount) via /3rd_rw/developer.sh:
#   mkdir -p /3rd_rw/patch
#   cp this file /3rd_rw/patch/start-UI-custom.sh
#   chmod 755 /3rd_rw/patch/start-UI-custom.sh
#   mount --bind /3rd_rw/patch/start-UI-custom.sh /3rd/opera4x/hisenseUI/start-UI.sh
#
# Or use the vendor full overlay /3rd_rw/patch/opera4x (see 04-modding.md, E.2).
set -e
cd /3rd/opera4x/hisenseUI
. ./opera_env.sh

export MEMORY_LIMIT=$(( 500*1024*1024 ))
STARTPAGE="file:///3rd_rw/UI/custom.html"

if [ -x /etc/scripts/ins_arm_mali_mod.sh ]; then
  /etc/scripts/ins_arm_mali_mod.sh
fi

export LD_PRELOAD="/3rd/opera4x/lib/libcurl.so.4.4.0"

cmd="./bin/hisenseUI"
cmd+=" --hw-gles"
cmd+=" --js-flags=\"--expose-gc\""
cmd+=" --jsplugins-dir=/3rd/UI_jsplugins"
cmd+=" --enable-gpu-rasterization"
cmd+=" --force-gpu-rasterization"
cmd+=" --force-gpu-mem-available-mb=512"
cmd+=" --disable-software-rasterizer"
cmd+=" --disable-web-security"
cmd+=" --http-cache-size=30"
cmd+=" -u ${STARTPAGE}"

if [ -e /3rd_rw/appdata/enable_developer_tools ]; then
  cmd+=" --remote-debugging-port=9223"
fi

cmd+=" $@"
exec $cmd
