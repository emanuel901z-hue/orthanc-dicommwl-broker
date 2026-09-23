#!/usr/bin/env python3
r"""Drive DVTk's console emulators (`DVTCmd -estscp` / `-estscu`) from Python.

Why this exists: `DVTCmd -estscp` prints "Press ENTER to Stop the SCP Emulator"
and **exits as soon as its stdin closes**. Over SSH without a PTY — and with
`Start-Process` — stdin is at EOF immediately, so the emulator stops before
anyone can talk to it. A Python `Popen` with `stdin=subprocess.PIPE` keeps the
pipe open: the emulator runs until this script terminates it.

Two things the emulator needs besides the process handling (both cost an
afternoon to find):

* the session must be an **emulator** session (`SESSION-TYPE emulator`). The
  examples under `Scripts/...` are script sessions and fail with
  "ScriptSession kann nicht in EmulatorSession umgewandelt werden";
* `SUT-ROLE requestor` (DVTk is the SCP here) and the transfer syntax the
  caller uses (`SUPPORTED-TRANSFER-SYNTAX "1.2.840.10008.1.2.1"`), otherwise
  every association is rejected.

Runs **on the Windows machine** (it needs the DVTk install):

    python dvtk_emulator.py --mode estscp --session <Storage_SCP.ses> --seconds 600

It writes a log next to the session and prints a line once the process is up, so
the caller can wait for it:

    READY pid=1234 port=<DVT-PORT>

The port is read from the session file (`DVT-PORT`), which is what the emulator
listens on for `-estscp`.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_BIN = Path(r"D:\Projekte\orthanc-dicommwl-broker\DVTkdvt\Bin\DVTCmd.exe")


def session_port(session: Path, key: str = "DVT-PORT") -> int | None:
    """The port the emulator listens on, straight from the session file."""
    for line in session.read_text(errors="replace").splitlines():
        match = re.match(rf"\s*{key}\s+(\d+)\s*$", line)
        if match:
            return int(match.group(1))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="estscp", choices=("estscp", "estscu"))
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--bin", default=str(DEFAULT_BIN), type=Path)
    parser.add_argument("--seconds", type=int, default=600,
                        help="how long to keep the emulator running")
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args()

    if not args.bin.is_file():
        print(f"DVTCmd not found: {args.bin}", file=sys.stderr)
        return 2
    if not args.session.is_file():
        print(f"session not found: {args.session}", file=sys.stderr)
        return 2

    log_path = args.log or args.session.with_suffix(f".{args.mode}.log")
    port = session_port(args.session)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        # stdin stays open for the whole run — that is the whole point
        process = subprocess.Popen(
            [str(args.bin), f"-{args.mode}", str(args.session)],
            stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
        )
        print(f"READY pid={process.pid} port={port} log={log_path}", flush=True)
        deadline = time.time() + args.seconds
        try:
            while time.time() < deadline and process.poll() is None:
                time.sleep(2)
        except KeyboardInterrupt:
            pass
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
    print("STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
