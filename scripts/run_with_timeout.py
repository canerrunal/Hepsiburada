#!/usr/bin/env python3
"""Komutu süre sınırıyla çalıştır, 30sn'de bir heartbeat bas. Trendyol run_with_timeout.py'nin minimal karşılığı."""
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
proc = subprocess.Popen(cleaned)
while proc.poll() is None:
    time.sleep(min(heartbeat, 5))
    elapsed = time.time() - start
    if int(elapsed) % heartbeat < 5:
        print(f"HEARTBEAT elapsed={int(elapsed)}s", flush=True)
    if elapsed > timeout:
        print(f"TIMEOUT {timeout}s, süreç grubu kapatılıyor", file=sys.stderr, flush=True)
        proc.kill()
        sys.exit(124)
sys.exit(proc.returncode)
