#!/usr/bin/env python3
"""Stop hook: refuse to end a response while the project record is inconsistent.

Stop fires at the end of EVERY response, not only at the end of a session,
so this runs only the fast consistency check, "tools/status.py --check",
and blocks at most once per turn: when the input has stop_hook_active set,
Claude is already continuing because of this hook, and it may stop.

Exit code 2 blocks, so it is used only for a real, stated reason.  Until
status.py exists there is nothing to check and this exits 0 -- which is why
the hook points here rather than at status.py: python3 itself exits with
code 2 when the script it is given does not exist, and a Stop hook aimed
straight at an unbuilt tool would block every response (manual 12.8).
Any failure inside this script exits 0.
"""
import json
import os
import subprocess
import sys

TIMEOUT = 60
MAX_REPORT = 4000


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if data.get("stop_hook_active"):
        return 0
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    status = os.path.join(root, "tools", "status.py")
    if not os.path.isfile(status):
        return 0
    try:
        r = subprocess.run([sys.executable, status, "--check"], cwd=root,
                           capture_output=True, text=True, timeout=TIMEOUT)
    except Exception:
        return 0
    if r.returncode == 0:
        return 0
    report = ((r.stdout or "") + (r.stderr or "")).strip()[:MAX_REPORT]
    sys.stderr.write(
        "The project record is inconsistent (tools/status.py --check):\n"
        + (report or "(no details printed)") + "\n"
        "Fix these, or record in the ledger why they must wait, before "
        "ending the response.\n")
    return 2


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0
    sys.exit(code)
