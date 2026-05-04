from __future__ import annotations

import os
import re
import subprocess
import sys
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

sys.path.insert(0, str(_find_root()))

from packages.schemas.events import TerminalAction
from apps.agent.src.core.buffer import LocalSQLiteBuffer

AUDIT_LOG = "/var/log/audit/audit.log"

NOISE_EXECUTABLES = frozenset({
    "/usr/lib/systemd/systemd", "/usr/bin/dbus-daemon", "/usr/bin/Xorg",
    "/usr/bin/pulseaudio", "/usr/lib/polkit-1/polkitd", "/usr/sbin/auditd",
    "/usr/bin/gdm", "/usr/lib/gdm-wayland-session", "/usr/lib/gvfsd",
    "/usr/bin/ibus-daemon", "/usr/lib/at-spi2-core/at-spi2-registryd",
    "/usr/bin/dconf", "/usr/lib/gvfs/gvfsd", "audispd", "/sbin/auditctl",
})

TERMINAL_PARENTS = frozenset({
    "bash", "zsh", "fish", "sh", "dash", "ksh", "tcsh",
    "alacritty", "kitty", "gnome-terminal", "konsole", "xterm",
    "tmux", "screen", "wezterm", "foot",
    "code", "cursor", "nvim", "vim", "emacs", "helix",
    "claude", "python", "python3", "node", "cargo",
})

_RE_TYPE       = re.compile(r'^type=(\S+)')
_RE_MSG_ID     = re.compile(r'msg=audit\(([^)]+)\)')
_RE_PID        = re.compile(r'\bpid=(\d+)')
_RE_PPID       = re.compile(r'\bppid=(\d+)')
_RE_EXE        = re.compile(r'\bexe="([^"]+)"')
_RE_ARG        = re.compile(r'\ba(\d+)=(?:"([^"]*)"|([0-9A-Fa-f]+))')
_RE_CWD_VAL    = re.compile(r'\bcwd="([^"]+)"')
_RE_UID        = re.compile(r'\buid=(\d+)')


def _decode_hex_arg(hex_str: str) -> str:
    try:
        return bytes.fromhex(hex_str).decode("utf-8", errors="replace")
    except ValueError:
        return hex_str


def _parse_execve_record(line: str) -> dict | None:
    if "type=EXECVE" not in line and "type=SYSCALL" not in line and "type=CWD" not in line:
        return None
    rec: dict = {}
    m = _RE_TYPE.match(line)
    if m:
        rec["rec_type"] = m.group(1)
    m = _RE_MSG_ID.search(line)
    if m:
        rec["msg_id"] = m.group(1)
    m = _RE_PID.search(line)
    if m:
        rec["pid"] = int(m.group(1))
    m = _RE_PPID.search(line)
    if m:
        rec["ppid"] = int(m.group(1))
    m = _RE_EXE.search(line)
    if m:
        rec["exe"] = m.group(1)
    m = _RE_UID.search(line)
    if m:
        rec["uid"] = m.group(1)
    m = _RE_CWD_VAL.search(line)
    if m:
        rec["cwd"] = m.group(1)
    args: dict[int, str] = {}
    for idx_str, quoted, hexval in _RE_ARG.findall(line):
        idx = int(idx_str)
        args[idx] = quoted if quoted is not None and quoted != "" else _decode_hex_arg(hexval)
    if args:
        rec["args"] = [args[k] for k in sorted(args)]
    return rec if rec else None


def _uid_to_username(uid: str) -> str:
    try:
        import pwd
        return pwd.getpwuid(int(uid)).pw_name
    except Exception:
        return uid


def _is_interesting(exe: str, ppid: int) -> bool:
    if exe in NOISE_EXECUTABLES:
        return False
    exe_name = Path(exe).name
    if exe_name in NOISE_EXECUTABLES:
        return False
    try:
        comm_path = f"/proc/{ppid}/comm"
        parent_comm = Path(comm_path).read_text().strip()
        if parent_comm in TERMINAL_PARENTS:
            return True
    except OSError:
        pass
    return exe_name not in NOISE_EXECUTABLES


class ArchAuditMonitor:
    def __init__(self, buffer: LocalSQLiteBuffer | None = None) -> None:
        self._buffer = buffer or LocalSQLiteBuffer()
        self._pending: dict[str, dict] = {}

    def _flush_event(self, ctx: dict) -> None:
        exe  = ctx.get("exe", "")
        pid  = ctx.get("pid", 0)
        ppid = ctx.get("ppid", 0)

        if not exe or not _is_interesting(exe, ppid):
            return

        args  = ctx.get("args", [])
        cmd   = " ".join(args) if args else exe
        uid   = ctx.get("uid", "0")
        cwd   = ctx.get("cwd")

        parent_name: str | None = None
        try:
            parent_name = Path(f"/proc/{ppid}/comm").read_text().strip()
        except OSError:
            pass

        event = TerminalAction(
            source_process=Path(exe).name,
            pid=pid,
            event_type="terminal_action",
            command_executed=cmd,
            working_directory=cwd,
            user=_uid_to_username(uid),
            parent_process=parent_name,
        )
        self._buffer.push_event(event)

    def _handle_line(self, line: str) -> None:
        rec = _parse_execve_record(line)
        if not rec:
            return

        msg_id   = rec.get("msg_id", "")
        rec_type = rec.get("rec_type", "")

        if msg_id not in self._pending:
            self._pending[msg_id] = {}

        ctx = self._pending[msg_id]

        if rec_type == "SYSCALL":
            ctx.update({k: rec[k] for k in ("pid", "ppid", "exe", "uid") if k in rec})
        elif rec_type == "EXECVE":
            if "args" in rec:
                ctx["args"] = rec["args"]
        elif rec_type == "CWD":
            if "cwd" in rec:
                ctx["cwd"] = rec["cwd"]

        if "exe" in ctx and "args" in ctx:
            self._flush_event(ctx)
            del self._pending[msg_id]

        if len(self._pending) > 2048:
            oldest = next(iter(self._pending))
            del self._pending[oldest]

    def run(self) -> None:
        proc = subprocess.Popen(
            ["tail", "-F", AUDIT_LOG],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert proc.stdout is not None
        try:
            while True:
                raw = proc.stdout.readline()
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8", errors="replace").rstrip()
                except Exception:
                    continue
                try:
                    self._handle_line(line)
                except Exception:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            proc.terminate()


if __name__ == "__main__":
    ArchAuditMonitor().run()