from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

def _find_root():
    curr = Path(__file__).resolve().parent
    for _ in range(10):
        if (curr / "apps").exists() or (curr / "packages").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    return curr

ROOT_DIR = _find_root()
sys.path.insert(0, str(ROOT_DIR))

from apps.agent.src.core.buffer import LocalSQLiteBuffer
from apps.agent.src.core.forwarder import start_forwarder
from apps.agent.src.interceptors.os_monitor import ArchAuditMonitor

PROXY_SCRIPT = ROOT_DIR / "apps" / "agent" / "src" / "interceptors" / "network_proxy.py"
MITM_PORT = 8080


def check_root() -> None:
    if os.geteuid() != 0:
        print(
            "\n[ERROR] This script must be run as root.\n"
            "        auditd log access requires elevated privileges.\n"
            "\n"
            "  Run with:  sudo python main.py\n",
            file=sys.stderr,
        )
        sys.exit(1)


def init_buffer() -> LocalSQLiteBuffer:
    buf = LocalSQLiteBuffer()
    from apps.agent.src.core.buffer import DB_PATH
    print(f"[DB]  SQLite WAL buffer ready → {DB_PATH}")
    return buf


def print_proxy_instructions() -> None:
    separator = "─" * 64
    print(f"""
{separator}
  AGENT MONITOR — bare-metal intercept mode
{separator}

  ✓  OS audit monitor  : running (this process)
  ✗  Network proxy     : NOT started

  Open a SECOND terminal and run:

    mitmdump -p {MITM_PORT} --scripts {PROXY_SCRIPT}

  Then configure your AI agent / browser to use:

    HTTP proxy  →  127.0.0.1:{MITM_PORT}
    HTTPS proxy →  127.0.0.1:{MITM_PORT}

  For system-wide interception (Arch Linux):

    export http_proxy=http://127.0.0.1:{MITM_PORT}
    export https_proxy=http://127.0.0.1:{MITM_PORT}

  To trust the mitmproxy CA certificate:

    sudo trust anchor ~/.mitmproxy/mitmproxy-ca-cert.pem

{separator}
  Press Ctrl+C to stop the OS monitor.
{separator}
""")


def start_audit_monitor(buffer: LocalSQLiteBuffer) -> threading.Thread:
    monitor = ArchAuditMonitor(buffer=buffer)

    def _run() -> None:
        print("[AUDIT] ArchAuditMonitor started — tailing /var/log/audit/audit.log")
        monitor.run()

    t = threading.Thread(target=_run, daemon=True, name="audit-monitor")
    t.start()
    return t


def main() -> None:
    check_root()
    buffer = init_buffer()
    print_proxy_instructions()
    start_audit_monitor(buffer)

    # Start the background forwarder that ships buffered events to the backend.
    forwarder = start_forwarder()

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] KeyboardInterrupt received — stopping agent monitor.")
        forwarder.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()