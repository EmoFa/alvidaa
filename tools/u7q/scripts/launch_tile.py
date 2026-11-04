#!/usr/bin/env python3
"""Launch (or re-launch) a tile on the TV over MQTT.

This is the only step that needs a pairing session. It shells out to a
`sidee` checkout (https://github.com/alvidaa/sidee) which holds the MQTT
client and your session file. Nothing from that session is stored here.

    SIDEE=/path/to/sidee python3 launch_tile.py APPID TITLE URL

Environment:
    SIDEE   path to the sidee checkout (default: /tmp/sidee-check)
"""
import os
import sys


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 1
    appid, title, url = sys.argv[1:4]
    sidee = os.environ.get("SIDEE", "/tmp/sidee-check")
    if not os.path.isdir(os.path.join(sidee, "core")):
        print("sidee checkout not found at %s" % sidee)
        print("set SIDEE=/path/to/sidee, or launch the tile manually:")
        print("  %s  (%s)" % (url, appid))
        return 2
    sys.path.insert(0, sidee)
    from core import client  # noqa: E402

    session = client.Session.load()
    client.launch_tile(session, appid, title, url)
    print("launched %s -> %s" % (appid, url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
