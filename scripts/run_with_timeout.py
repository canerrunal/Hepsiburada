#!/usr/bin/env python3
"""Run a command with a timeout, process-group cleanup and durable heartbeats.

Every invocation writes a small run record under ``.runtime/runs``. The
runtime directory is intentionally ignored by git; it is operational state,
not marketplace data. The record lets the dashboard distinguish a live worker
from a stale command line after a crash or a machine restart.
"""
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime" / "runs"
TZ = dt.timezone(dt.timedelta(hours=3))


def stamp():
    return dt.datetime.now(TZ).isoformat(timespec="seconds")


def today():
    return dt.datetime.now(TZ).strftime("%Y-%m-%d")


def parse_args(argv):
    timeout = 1200
    heartbeat = 30
    component = None
    cleaned = []
    i = 0
    while i < len(argv):
        if argv[i] == "--timeout":
            timeout = int(argv[i + 1])
            i += 2
        elif argv[i] == "--heartbeat":
            heartbeat = int(argv[i + 1])
            i += 2
        elif argv[i] == "--component":
            component = argv[i + 1]
            i += 2
        elif argv[i] == "--":
            cleaned = argv[i + 1:]
            break
        else:
            i += 1
    if not cleaned:
        print("kullanım: run_with_timeout.py --timeout 1200 --heartbeat 30 [--component ad] -- <komut>", file=sys.stderr)
        sys.exit(2)
    if timeout <= 0 or heartbeat <= 0:
        print("timeout ve heartbeat pozitif olmalı", file=sys.stderr)
        sys.exit(2)
    return timeout, heartbeat, component, cleaned


def infer_component(command):
    text = " ".join(command)
    if "hb_taxonomy_crawl.py" in text:
        return "taxonomy-discovery"
    if "hb_taxonomy_collect.py" in text:
        return "taxonomy-products"
    if "hb_collect_pw.py" in text:
        return "listing-collector"
    if "hb_detail_pw.py" in text:
        return "detail-collector"
    if "hb_taxonomy_merge.py" in text:
        return "taxonomy-merge"
    return "worker"


def write_record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    temporary.replace(path)


def main():
    timeout, heartbeat, component, command = parse_args(sys.argv[1:])
    component = component or infer_component(command)
    run_id = f"{today()}-{component}-{uuid.uuid4().hex[:10]}"
    record_path = RUNTIME / today() / f"{run_id}.json"
    started = time.monotonic()
    record = {
        "runId": run_id,
        "component": component,
        "command": command,
        "pid": None,
        "status": "STARTING",
        "startedAt": stamp(),
        "updatedAt": stamp(),
        "finishedAt": None,
        "elapsedSeconds": 0,
        "timeoutSeconds": timeout,
        "heartbeatSeconds": heartbeat,
        "exitCode": None,
        "timeout": False,
    }
    write_record(record_path, record)

    proc = None

    def update(status=None, **extra):
        if status:
            record["status"] = status
        record.update(extra)
        record["updatedAt"] = stamp()
        record["elapsedSeconds"] = round(time.monotonic() - started, 1)
        write_record(record_path, record)

    def terminate_group(force=False):
        if proc is None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass

    def handle_signal(signum, _frame):
        update("CANCELLED", finishedAt=stamp(), exitCode=128 + signum)
        terminate_group()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            terminate_group(force=True)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    try:
        proc = subprocess.Popen(command, start_new_session=True)
        record["pid"] = proc.pid
        update("RUNNING")
        next_heartbeat = time.monotonic()
        while proc.poll() is None:
            now = time.monotonic()
            if now >= next_heartbeat:
                update("RUNNING")
                print(f"HEARTBEAT component={component} run={run_id} elapsed={int(now - started)}s", flush=True)
                next_heartbeat = now + heartbeat
            if now - started > timeout:
                print(f"TIMEOUT {timeout}s, süreç grubu kapatılıyor", file=sys.stderr, flush=True)
                update("TIMEOUT", finishedAt=stamp(), timeout=True)
                terminate_group()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    terminate_group(force=True)
                update("TIMEOUT", finishedAt=record["finishedAt"], exitCode=124, timeout=True)
                return 124
            wait_for = max(0.2, min(1.0, next_heartbeat - time.monotonic()))
            time.sleep(wait_for)
        code = proc.returncode
        update("SUCCEEDED" if code == 0 else "FAILED", finishedAt=stamp(), exitCode=code)
        return code
    except SystemExit:
        raise
    except Exception as error:
        update("FAILED", finishedAt=stamp(), exitCode=1, error=str(error)[:300])
        raise


if __name__ == "__main__":
    sys.exit(main())
