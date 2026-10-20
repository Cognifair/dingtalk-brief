#!/usr/bin/env python3
"""Bring the local DingTalk cache up to date before a brief runs.

Steps:
  1. make sure the DingTalk desktop client is running (start it if DINGTALK_EXE is set)
  2. wait until its message database stops changing (sync settled)
  3. stop the local read-only web service
  4. re-decrypt the cache into the snapshot the bridge reads
  5. start the service again and wait for it to answer

Refreshing produces a plaintext copy of the whole account cache, not just the
selected groups - only run this where that is allowed.

Configuration (environment variables):
  DINGTALK_EXPORTER_DIR   required - checkout of the exporter with .venv/
  DINGTALK_EXE            optional - DingTalk.exe path, enables auto-launch
  DINGTALK_WAL            optional - encrypted dingtalk.db-wal to watch for sync
  DINGTALK_PORT           optional - service port, default 8090
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

EXPORTER = (os.environ.get("DINGTALK_EXPORTER_DIR") or "").strip()
DINGTALK_EXE = (os.environ.get("DINGTALK_EXE") or "").strip()
WAL = (os.environ.get("DINGTALK_WAL") or "").strip()
PORT = int(os.environ.get("DINGTALK_PORT") or "8090")

VENV_PY = os.path.join(EXPORTER, ".venv", "Scripts", "python.exe")
DECRYPTED = os.path.join(EXPORTER, "data", "decrypted", "dingtalk.db")
LOG = os.path.join(EXPORTER, "logs", "service.out.log")
HEALTH = f"http://127.0.0.1:{PORT}/api/conversations?limit=1"
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="mbcs", errors="replace")
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def dingtalk_pids() -> list[int]:
    code, out = run(["tasklist", "/FI", "IMAGENAME eq DingTalk.exe", "/NH", "/FO", "CSV"])
    pids = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].lower() == "dingtalk.exe" and len(parts) > 1 and parts[1].isdigit():
            pids.append(int(parts[1]))
    return pids


def start_dingtalk() -> str:
    if not DINGTALK_EXE:
        return "not-configured"
    if not os.path.isfile(DINGTALK_EXE):
        return "missing"
    subprocess.Popen([DINGTALK_EXE], creationflags=DETACHED, close_fds=True)
    for _ in range(60):
        if dingtalk_pids():
            return "started"
        time.sleep(1)
    return "timeout"


def wait_for_sync(max_wait: int = 90, quiet: int = 8) -> tuple[float, str]:
    """Wait until the WAL file stops changing, then a little longer."""
    if not WAL:
        time.sleep(5)
        return 5.0, "sleep-fallback"
    started = time.time()
    last = None
    stable = 0
    while time.time() - started < max_wait:
        try:
            current = os.path.getmtime(WAL), os.path.getsize(WAL)
        except OSError:
            current = None
        if current is not None and current == last:
            stable += 1
            if stable >= quiet:
                return round(time.time() - started, 1), "wal-quiet"
        else:
            stable = 0
        last = current
        time.sleep(1)
    return round(time.time() - started, 1), "timeout"


def listening_pid(port: int) -> int | None:
    code, out = run(["netstat", "-ano", "-p", "TCP"])
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line.upper():
            tail = line.split()
            if tail and tail[-1].isdigit():
                return int(tail[-1])
    return None


def stop_service() -> str:
    pid = listening_pid(PORT)
    if not pid:
        return "not-running"
    code, out = run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"])
    if "python" not in out.lower():
        return f"foreign-process:{pid}"
    run(["taskkill", "/PID", str(pid), "/F"])
    for _ in range(15):
        if listening_pid(PORT) != pid:
            return "stopped"
        time.sleep(1)
    return "stop-timeout"


def decrypt() -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        done = subprocess.run([VENV_PY, "decrypt.py"], cwd=EXPORTER, capture_output=True,
                              text=True, timeout=300, env=env, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)[:300]
    tail = ((done.stdout or "") + (done.stderr or "")).strip().splitlines()[-3:]
    return done.returncode == 0, " | ".join(tail)[-300:]


def start_service() -> bool:
    env = dict(os.environ)
    env["DINGTALK_AUTO_SYNC"] = "0"
    env["DINGTALK_SKIP_DISCOVERY"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "ab") as log:
        subprocess.Popen([VENV_PY, "main.py"], cwd=EXPORTER, env=env,
                         stdout=log, stderr=subprocess.STDOUT,
                         creationflags=DETACHED, close_fds=True)
    for _ in range(40):
        try:
            with urllib.request.urlopen(HEALTH, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1)
    return False


def main() -> int:
    if not EXPORTER or not os.path.isfile(VENV_PY):
        print(json.dumps({"ok": False,
                          "error": "set DINGTALK_EXPORTER_DIR to the exporter checkout",
                          "checked": EXPORTER}, ensure_ascii=False))
        return 2

    started = time.time()
    result = {"ok": False}

    if dingtalk_pids():
        result["dingtalk"] = "running"
    else:
        result["dingtalk"] = start_dingtalk()
        if result["dingtalk"] in ("missing", "timeout"):
            result["error"] = "cannot start DingTalk; set DINGTALK_EXE"
            print(json.dumps(result, ensure_ascii=False))
            return 1
        if result["dingtalk"] == "started":
            time.sleep(5)

    result["sync_wait_s"], result["sync_mode"] = wait_for_sync()
    result["service_before"] = stop_service()

    ok, detail = decrypt()
    result["decrypt_ok"] = ok
    if not ok:
        result["decrypt_detail"] = detail

    result["service"] = "ready" if start_service() else "unavailable"
    try:
        result["snapshot"] = datetime.fromtimestamp(os.path.getmtime(DECRYPTED)).isoformat(timespec="seconds")
    except OSError:
        result["snapshot"] = None
    result["elapsed_s"] = round(time.time() - started, 1)
    result["ok"] = bool(ok and result["service"] == "ready")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
