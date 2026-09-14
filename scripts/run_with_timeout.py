#!/usr/bin/env python3
"""Komutu süre sınırıyla çalıştır, 30sn'de bir heartbeat bas. Trendyol run_with_timeout.py'nin minimal karşılığı."""
import os
import signal
import subprocess
import sys
import time

timeout = 1200
heartbeat = 30
args = sys.argv[1:]
if args[:2] == ["--timeout", args[1] if len(args) > 1 else ""]:
    pass
cleaned = []
skip_next = 0
i = 0
while i < len(args):
    if args[i] == "--timeout":
        timeout = int(args[i + 1]); i += 2
    elif args[i] == "--heartbeat":
        heartbeat = int(args[i + 1]); i += 2
    elif args[i] == "--":
        cleaned = args[i + 1:]; break
    else:
        i += 1

if not cleaned:
    print("kullanım: run_with_timeout.py --timeout 1200 --heartbeat 30 -- <komut>", file=sys.stderr)
    sys.exit(2)

start = time.time()
proc = subprocess.Popen(cleaned, start_new_session=True)


def terminate_group(force=False):
    try:
        os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass


def handle_signal(signum, _frame):
    terminate_group()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        terminate_group(force=True)
    raise SystemExit(128 + signum)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)
while proc.poll() is None:
    time.sleep(min(heartbeat, 5))
    elapsed = time.time() - start
    if int(elapsed) % heartbeat < 5:
        print(f"HEARTBEAT elapsed={int(elapsed)}s", flush=True)
    if elapsed > timeout:
        print(f"TIMEOUT {timeout}s, süreç grubu kapatılıyor", file=sys.stderr, flush=True)
        terminate_group()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            terminate_group(force=True)
        sys.exit(124)
sys.exit(proc.returncode)
