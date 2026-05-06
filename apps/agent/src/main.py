from __future__ import annotations

import atexit
import os
import pwd
import signal
import subprocess
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
MITM_PORT    = 8080

# Resolve the mitmdump binary from the monitored user's dev-env
def _find_mitmdump() -> str:
    """Find the mitmdump binary. It's in the dev-env, not on root's PATH."""
    username = os.environ.get("MONITORED_USER", os.environ.get("SUDO_USER", "allain"))
    try:
        home = Path(pwd.getpwnam(username).pw_dir)
    except KeyError:
        home = Path(f"/home/{username}")
    dev_env = home / "dev-env" / "bin" / "mitmdump"
    if dev_env.exists():
        return str(dev_env)
    # Fallback: check PATH
    import shutil
    found = shutil.which("mitmdump")
    if found:
        return found
    print(f"[WARN] mitmdump not found in dev-env ({dev_env}) or PATH", file=sys.stderr)
    return str(dev_env)  # will fail with a clear error

MITMDUMP_BIN = _find_mitmdump()


# ─── Root check ───────────────────────────────────────────────────────────────

def check_root() -> None:
    if os.geteuid() != 0:
        print(
            "\n[ERROR] This script must be run as root.\n"
            "        auditd log access and iptables require elevated privileges.\n"
            "\n"
            "  Run with:  sudo python main.py\n",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── Monitored-user helpers ───────────────────────────────────────────────────

def get_monitored_uid() -> int:
    """Return the UID of the user whose traffic we redirect through mitmproxy."""
    username = os.environ.get("MONITORED_USER", "allain")
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        print(f"[WARN] User '{username}' not found — falling back to UID 1000", file=sys.stderr)
        return 1000


def get_monitored_home(username: str | None = None) -> Path:
    uname = username or os.environ.get("MONITORED_USER", "allain")
    try:
        return Path(pwd.getpwnam(uname).pw_dir)
    except KeyError:
        return Path(f"/home/{uname}")


# ─── iptables transparent proxy ───────────────────────────────────────────────

_IPTABLES_ACTIVE: bool = False
_IPTABLES_UID:   int   = -1


def _iptables_cmd(action: str, uid: int, dport: str) -> list[str]:
    return [
        "iptables", "-t", "nat", action, "OUTPUT",
        "-p", "tcp", "--dport", dport,
        "-m", "owner", "--uid-owner", str(uid),
        "-j", "REDIRECT", "--to-port", str(MITM_PORT),
    ]


def setup_iptables(uid: int) -> None:
    global _IPTABLES_ACTIVE, _IPTABLES_UID
    print(f"[IPTABLES] Redirecting UID {uid} → port {MITM_PORT} (transparent proxy)")
    errors: list[str] = []
    for dport in ("443", "80"):
        result = subprocess.run(
            _iptables_cmd("-A", uid, dport),
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            errors.append(f"port {dport}: {result.stderr.strip()}")
    if errors:
        print(f"[IPTABLES] Warning — some rules may not have applied: {errors}", file=sys.stderr)
    else:
        _IPTABLES_ACTIVE = True
        _IPTABLES_UID    = uid
        print("[IPTABLES] Rules installed ✓")


def teardown_iptables(uid: int | None = None) -> None:
    global _IPTABLES_ACTIVE
    if not _IPTABLES_ACTIVE:
        return
    target_uid = uid if uid is not None else _IPTABLES_UID
    if target_uid < 0:
        return
    print(f"\n[IPTABLES] Removing redirect rules for UID {target_uid}…")
    for dport in ("443", "80"):
        subprocess.run(
            _iptables_cmd("-D", target_uid, dport),
            capture_output=True,
        )
    _IPTABLES_ACTIVE = False
    print("[IPTABLES] Rules removed ✓")


# ─── mitmproxy CA trust ───────────────────────────────────────────────────────

def trust_mitmproxy_ca() -> None:
    """
    Trust the mitmproxy CA cert system-wide so HTTPS interception works.
    This is idempotent — 'trust anchor' is a no-op if already trusted.
    """
    home = get_monitored_home()
    cert = home / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    if not cert.exists():
        print(
            f"[CA] mitmproxy CA cert not found at {cert}.\n"
            "     Start mitmproxy once first to generate it, then re-run.\n"
            "     Skipping CA trust step.",
            file=sys.stderr,
        )
        return
    result = subprocess.run(
        ["trust", "anchor", str(cert)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"[CA] mitmproxy CA trusted ✓  ({cert})")
    else:
        print(
            f"[CA] 'trust anchor' failed (may already be trusted): {result.stderr.strip()}",
            file=sys.stderr,
        )


# ─── mitmdump subprocess ──────────────────────────────────────────────────────

def start_mitmdump() -> subprocess.Popen:  # type: ignore[type-arg]
    """Launch mitmdump as a child process, inheriting stdout/stderr for visibility."""
    cmd = [
        MITMDUMP_BIN,
        "--mode", "transparent",
        "-p", str(MITM_PORT),
        "--scripts", str(PROXY_SCRIPT),
        "--ssl-insecure",
    ]
    print(f"[MITM]  Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=None, stderr=None)
    return proc


# ─── SQLite buffer ────────────────────────────────────────────────────────────

def init_buffer() -> LocalSQLiteBuffer:
    buf = LocalSQLiteBuffer()
    from apps.agent.src.core.buffer import DB_PATH
    print(f"[DB]   SQLite WAL buffer ready → {DB_PATH}")
    return buf


# ─── Audit monitor ────────────────────────────────────────────────────────────

def start_audit_monitor(buffer: LocalSQLiteBuffer) -> threading.Thread:
    monitor = ArchAuditMonitor(buffer=buffer)

    def _run() -> None:
        print("[AUDIT] ArchAuditMonitor started — tailing /var/log/audit/audit.log (live only)")
        monitor.run()

    t = threading.Thread(target=_run, daemon=True, name="audit-monitor")
    t.start()
    return t


# ─── Signal / atexit cleanup ──────────────────────────────────────────────────

def _make_cleanup(uid: int, mitm_proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    def _cleanup() -> None:
        teardown_iptables(uid)
        if mitm_proc.poll() is None:
            print("[MITM]  Terminating mitmdump…")
            mitm_proc.terminate()
            try:
                mitm_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mitm_proc.kill()

    atexit.register(_cleanup)

    def _sigterm_handler(signum: int, frame: object) -> None:
        print("\n[SHUTDOWN] SIGTERM received.")
        _cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sigterm_handler)


# ─── Status banner ────────────────────────────────────────────────────────────

def print_status(uid: int) -> None:
    sep = "─" * 64
    print(f"""
{sep}
  EZ-CATCH AGENT — bare-metal intercept mode
{sep}

  ✓  OS audit monitor  : running (tailing live events only)
  ✓  Transparent proxy : mitmdump on port {MITM_PORT}
  ✓  iptables redirect : UID {uid} → :{MITM_PORT}

  Dashboard → http://localhost:3000
  Backend   → http://localhost:8000

  Press Ctrl+C to stop and clean up all rules.
{sep}
""")


# ─── Main ─────────────────────────────────────────────────────────────────────

def ensure_auditd_rules() -> None:
    """Install auditd rules that generate EXECVE events for command monitoring."""
    # Check if we already have an execve rule
    result = subprocess.run(
        ["auditctl", "-l"],
        capture_output=True, text=True,
    )
    if "execve" in result.stdout.lower() or "EXECVE" in result.stdout:
        print("[AUDIT] Existing execve rules found ✓")
        return

    # Install rule: capture all execve syscalls
    print("[AUDIT] No execve rules found — installing audit rule...")
    r = subprocess.run(
        ["auditctl", "-a", "exit,always", "-F", "arch=b64", "-S", "execve"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print("[AUDIT] Rule installed: -a exit,always -F arch=b64 -S execve ✓")
    else:
        print(f"[AUDIT] Warning: could not install rule: {r.stderr.strip()}", file=sys.stderr)


def main() -> None:
    check_root()

    buffer = init_buffer()

    uid = get_monitored_uid()

    # Ensure auditd has rules to capture EXECVE events
    ensure_auditd_rules()

    # Trust mitmproxy CA before starting mitmdump (generates cert on first run)
    # Run mitmdump first so the cert gets created, then trust it.
    mitm_proc = start_mitmdump()

    import time as _time
    _time.sleep(1.5)          # give mitmdump time to write the cert on first run
    trust_mitmproxy_ca()

    setup_iptables(uid)

    # Register cleanup for normal exit and signals
    _make_cleanup(uid, mitm_proc)

    start_audit_monitor(buffer)

    forwarder = start_forwarder()

    print_status(uid)

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] KeyboardInterrupt — stopping agent monitor.")
        forwarder.stop()
        # atexit handler will run teardown_iptables and kill mitmdump
        sys.exit(0)


if __name__ == "__main__":
    main()