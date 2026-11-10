"""live.py: protection checks that only mean something on the Mac itself."""

import subprocess
import sys

from . import db


def checks():
    out = {"filevault": None}
    if db.mode() != "live" or sys.platform != "darwin":
        return out
    try:
        r = subprocess.run(["/usr/bin/fdesetup", "status"], capture_output=True, text=True, timeout=10)
        t = r.stdout.lower()
        if "filevault is on" in t:
            out["filevault"] = True
        elif "filevault is off" in t:
            out["filevault"] = False
    except (OSError, subprocess.SubprocessError):
        pass
    return out
