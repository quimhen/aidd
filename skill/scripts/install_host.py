"""install_host.py — non-destructive AIDD install for a non-Claude host.

aidd:FR-901 aidd:FR-902 aidd:FR-903 aidd:AC-005 (spec 009, plan Interface 2, task T-04)
aidd:FR-1103 aidd:FR-1104 aidd:AC-1103 (spec 011, plan Interface 2, task T-02)
aidd:FR-1112 aidd:FR-1113 aidd:AC-1111 aidd:AC-1112 (spec 011 Amendment 1, task T-13)
aidd:FR-1204 aidd:FR-1205 aidd:AC-1204 aidd:AC-1205 (spec 012, task T-06)

Usage:
    python install_host.py install <gemini|opencode|antigravity> <project-root> [--githooks] [--force] [--json]
    python install_host.py install <project-root> --githooks [--json]

Git hooks (spec 012 FR-1204, `--githooks`, alone or with a host):
- The hooks folder is `git -C <root> rev-parse --git-path hooks` (worktrees and
  `core.hooksPath` resolve to the folder git really runs), relative -> <root>.
- `pre-commit` / `pre-push` are POSIX sh with the `# aidd-githook` marker; they
  run `aidd guard commit|push` when `aidd` is on PATH, else
  `python .aidd/scripts/aidd_guard.py guard commit|push`, else exit 0 (fail
  open). No drive letter or user path is written (git runs hooks from the top
  of the work tree).
- A foreign hook gets ONE marked block appended (its lines are never rewritten);
  a hook that already holds the marker is `unchanged` (idempotent); a foreign
  hook with a non-sh shebang is `skipped` with a reason.
- A hooks folder or hook file that is a symlink/junction is refused (`skipped`),
  even with --force: `.git/` is git's own state. Writes are atomic (os.replace)
  and the file is made executable.

OpenCode (spec 012 FR-1205): plugins under `.opencode/plugins/` are
auto-discovered, so no relative `plugin` entry is added to `opencode.json`; an
existing one is never removed.

What it does (and what it never does):
- Copies the shipped `adapters/dot-aidd/` bundle into `<project-root>/.aidd/`
  FILE BY FILE, comparing bytes: identical -> `unchanged`; missing -> `written`;
  different -> `skipped` (kept) unless `--force` (then `written`).
- Never calls `aidd init` (its `--force` runs rmtree on `.aidd/`), never deletes
  anything, never touches `.aidd/memory/`, `.aidd/evidence/`, `.aidd/gate_spec`
  or `.aidd/active_spec`.
- Writes the host files and merges the host registration JSON by key, keeping
  every foreign entry and key; a corrupt existing JSON is left as is (`skipped`).
- Never writes through a symlink or junction (every host, spec 011 FR-1104):
  before any write, every path component from the project root down to the
  destination is checked. A link -> the file is `skipped (symlink -> <target>)`
  and nothing is written. With `--force` ONLY the link itself is removed
  (`os.unlink` / `os.rmdir`, never rmtree) and a real folder is created in its
  place; the link target is never followed for writing and never modified.
  Windows detection uses the reparse TAG (symlink or mount point/junction), not
  the plain reparse-point attribute (OneDrive placeholders set that one too).
- Writes every file atomically (spec 011 FR-1112): a temp file in the same
  folder, then `os.replace`, so a HARD link at the destination is broken, never
  written through. If the replace fails the file is `skipped` and the run fails.
- Exits 1 when the gate registration (`.agents/hooks.json`, `.gemini/settings.json`,
  `.opencode/opencode.json`) is `skipped` for any reason (spec 011 FR-1113).

The shipped source is located the same way `aidd/cli.py` does it: relative to
this file (skill/scripts/ -> repo root -> adapters/). There is no AIDD_HOME
fallback because cli.py has none.

Gemini CLI hook schema — taken from the official docs, fetched 2026-10-13:
  https://geminicli.com/docs/hooks/reference/  (hook definition: `matcher` regex
      for tool events, `sequential`, `hooks` array; hook config: `type`
      ("command"), `command`, `name`, `timeout`, `description`; hooks live in
      settings.json under the `hooks` object keyed by event, e.g. BeforeTool)
  https://geminicli.com/docs/hooks/  (settings.json example:
      {"hooks": {"BeforeTool": [{"matcher": "write_file|replace",
       "hooks": [{"name": ..., "type": "command", "command": ..., "timeout": ...}]}]}})
  https://geminicli.com/docs/reference/tools  (tool names: `write_file`,
      `replace`, `run_shell_command`)

Antigravity contract — observed with `agy` 1.0.13 (spec 011):
  project hooks live in `<project>/.agents/hooks.json`, a JSON object keyed by
  hook NAME; each entry has `enabled` and per-event arrays (`PreToolUse`,
  `PostToolUse`) of `{matcher, hooks: [{type: "command", command, timeout}]}`.
  The hook runs with cwd = `<project>/.agents`, hence the relative command
  `python ../.aidd/hooks/host_adapter.py antigravity pre|post`. Matcher `*` is
  the only syntax observed (the adapter itself allows non-write tools). The
  skill goes to `.agents/skills/aidd/SKILL.md` and the always-on rule to
  `.agents/rules/aidd.md`, both copied from `adapters/antigravity/`.
"""
import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HOSTS = ("gemini", "opencode", "antigravity")
PROTECTED_NAMES = {"memory", "evidence", "gate_spec", "active_spec"}
IGNORED_DIRS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}

GEMINI_MATCHER = "write_file|replace|run_shell_command"
GEMINI_HOOKS = (
    ("BeforeTool", "aidd-gate", "python .aidd/hooks/host_adapter.py gemini pre"),
    ("AfterTool", "aidd-record", "python .aidd/hooks/host_adapter.py gemini post"),
)
AIDD_NAMES = {name for _, name, _ in GEMINI_HOOKS}
OPENCODE_PLUGIN_ENTRY = ".opencode/plugins/aidd.js"
# The files that register the AIDD gate with each host; skipping one exits 1.
GATE_REGISTRATIONS = {".agents/hooks.json", ".gemini/settings.json", ".opencode/opencode.json"}

ANTIGRAVITY_HOOK_NAME = "aidd"
ANTIGRAVITY_MATCHER = "*"
ANTIGRAVITY_TIMEOUT = 30
ANTIGRAVITY_COMMANDS = (
    ("PreToolUse", "python ../.aidd/hooks/host_adapter.py antigravity pre"),
    ("PostToolUse", "python ../.aidd/hooks/host_adapter.py antigravity post"),
)

# Git hooks (spec 012 FR-1204). The marker identifies an aidd hook or block.
GITHOOK_MARKER = "# aidd-githook"
GITHOOK_NAMES = ("pre-commit", "pre-push")
GITHOOK_MODES = {"pre-commit": "commit", "pre-push": "push"}
GITHOOK_SH_SHELLS = {"sh", "bash", "dash", "zsh", "ksh"}
GIT_TIMEOUT = 10  # seconds for `git rev-parse`
# Hosts with no write gate in 2.x: the install offers `--githooks` after them.
GITHOOK_OFFER_HOSTS = ("opencode", "antigravity")

# Windows reparse tags (stat exposes them since 3.8; literal fallback just in case).
_TAG_SYMLINK = getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C)
_TAG_MOUNT_POINT = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)
_ATTR_DIRECTORY = getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0x10)


def antigravity_entry() -> dict:
    """The `aidd` entry of `.agents/hooks.json` (a fresh dict on every call)."""
    entry = {"enabled": True}
    for event, command in ANTIGRAVITY_COMMANDS:
        entry[event] = [{"matcher": ANTIGRAVITY_MATCHER,
                         "hooks": [{"type": "command", "command": command,
                                    "timeout": ANTIGRAVITY_TIMEOUT}]}]
    return entry


def githook_lines(name: str) -> list:
    """The portable sh lines that call the guard for one hook (no shebang).

    Repo-relative fallback path only: git runs hooks from the work-tree top, so
    no drive letter or user folder is ever written. Neither aidd nor python
    available -> nothing runs and the hook exits 0 (fail open).
    """
    mode = GITHOOK_MODES[name]
    return [
        f"{GITHOOK_MARKER}: {name} runs `aidd guard {mode}` (AIDD spec 012); fails open when AIDD is absent",
        "if command -v aidd >/dev/null 2>&1; then",
        f"  aidd guard {mode} || exit $?",
        "elif [ -f .aidd/scripts/aidd_guard.py ] && command -v python >/dev/null 2>&1; then",
        f"  python .aidd/scripts/aidd_guard.py guard {mode} || exit $?",
        "fi",
    ]


def githook_script(name: str) -> bytes:
    """A whole hook file written when no hook exists yet (LF line endings)."""
    return ("\n".join(["#!/bin/sh"] + githook_lines(name)) + "\n").encode("utf-8")


def githook_block(name: str) -> bytes:
    """The block appended once to a foreign hook (starts with a blank line)."""
    return ("\n" + "\n".join(githook_lines(name)) + "\n").encode("utf-8")


def is_sh_hook(data: bytes) -> bool:
    """True when a hook has no shebang or an sh-family shebang (sh, bash, ...)."""
    first = data.split(b"\n", 1)[0].strip()
    if not first.startswith(b"#!"):
        return True
    words = first[2:].decode("utf-8", "replace").split()
    if not words:
        return True
    prog = words[0].replace("\\", "/").rsplit("/", 1)[-1]
    if prog == "env" and len(words) > 1:
        prog = words[1]
    return prog in GITHOOK_SH_SHELLS


def is_link(path: Path) -> bool:
    """True for a symlink or a junction; never follows the link.

    On Windows the reparse TAG decides (symlink or mount point); the plain
    reparse-point attribute is NOT used because cloud placeholders set it on
    real folders. Elsewhere, or if the tag is unavailable, os.path.islink.
    """
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if os.name == "nt":
        try:
            tag = st.st_reparse_tag
        except AttributeError:
            return os.path.islink(path)
        return tag in (_TAG_SYMLINK, _TAG_MOUNT_POINT)
    return os.path.islink(path)


def link_target(path: Path) -> str:
    """Best-effort text of a link's target (never raises)."""
    try:
        target = os.readlink(path)
    except (OSError, ValueError, NotImplementedError):
        return "<unknown target>"
    target = str(target)
    for prefix in ("\\\\?\\", "\\??\\"):
        if target.startswith(prefix):
            target = target[len(prefix):]
    return target


class HostInstaller:
    """Installs AIDD for one host into one project root, reporting per file."""

    def __init__(self, host: str, project_root: Path, force: bool, repo_root: Path):
        self.host = host
        self.project_root = project_root
        self.force = force
        self.repo_root = repo_root
        self.adapters_dir = repo_root / "adapters"
        self.results = []  # list of {path, status, reason}
        self.failed = False  # an unwritable target
        self._link_notes = {}  # target -> note about a link replaced with --force

    # -- reporting ---------------------------------------------------------
    def _record(self, target: Path, status: str, reason: str = "") -> None:
        try:
            rel = target.relative_to(self.project_root).as_posix()
        except ValueError:
            rel = str(target)
        note = self._link_notes.pop(target, "")
        if note:
            reason = f"{note}; {reason}" if reason else note
        self.results.append({"path": rel, "status": status, "reason": reason})
        if status == "skipped" and rel in GATE_REGISTRATIONS:
            self.failed = True  # spec 011 FR-1113: a skipped gate registration fails the install

    # -- symlink safety ----------------------------------------------------
    @staticmethod
    def _remove_link(link: Path) -> None:
        """Remove ONLY the link itself (never its target, never rmtree)."""
        if os.name == "nt":
            try:
                attrs = os.lstat(link).st_file_attributes
            except (OSError, AttributeError):
                attrs = 0
            if attrs & _ATTR_DIRECTORY:
                os.rmdir(link)  # directory symlink or junction: removes the link only
                return
        os.unlink(link)  # file link (Windows) or any symlink (POSIX)

    def _guard_links(self, target: Path) -> bool:
        """Check every component from the project root down to target.

        Returns True when the path is safe to write. A link component makes the
        file `skipped (symlink -> <target>)` unless --force, which removes only
        the link and creates a real folder in its place (not for the final
        component: that one becomes the written file).
        """
        try:
            rel = target.relative_to(self.project_root)
        except ValueError:
            self._record(target, "skipped", "outside the project root")
            return False
        parts = rel.parts
        for depth in range(1, len(parts) + 1):
            comp = self.project_root.joinpath(*parts[:depth])
            if not is_link(comp):
                if not os.path.lexists(comp):
                    return True  # nothing below exists yet: no link possible
                continue
            dest = link_target(comp)
            comp_rel = Path(*parts[:depth]).as_posix()
            if not self.force:
                where = "" if depth == len(parts) else f" at {comp_rel}"
                self._record(target, "skipped",
                             f"symlink{where} -> {dest}; pass --force to replace the link with a real folder")
                return False
            try:
                self._remove_link(comp)
                if depth < len(parts):
                    comp.mkdir()
            except OSError as exc:
                self._record(target, "skipped", f"cannot replace symlink {comp_rel} -> {dest}: {exc}")
                self.failed = True
                return False
            what = "real folder" if depth < len(parts) else "real file"
            self._link_notes[target] = f"symlink {comp_rel} -> {dest} replaced by a {what} (--force)"
        return True

    # -- low-level io ------------------------------------------------------
    @staticmethod
    def _read_bytes(path: Path):
        try:
            return path.read_bytes(), ""
        except OSError as exc:
            return None, f"cannot read {path}: {exc}"

    def _write_bytes(self, target: Path, data: bytes) -> bool:
        if not self._guard_links(target):
            return False
        return self._atomic_write(target, data)

    def _atomic_write(self, target: Path, data: bytes) -> bool:
        """Write data to target atomically; the caller has checked for links."""
        # Atomic write (spec 011 FR-1112): a temp file in the same folder, then
        # os.replace. A hard link at the destination is broken (the name gets a
        # new inode), never written through. No in-place fallback, ever.
        tmp = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.parent / f".{target.name}.{os.getpid()}.{os.urandom(4).hex()}.aidd-tmp"
            fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o666)
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
            finally:
                os.close(fd)
        except OSError as exc:
            self._record(target, "skipped", f"cannot write: {exc}")
            self.failed = True
            self._unlink_quiet(tmp)
            return False
        try:
            os.replace(tmp, target)
            return True
        except OSError as exc:
            self._record(target, "skipped", f"cannot replace the destination (held open?), left as is: {exc}")
            self.failed = True
            return False
        finally:
            self._unlink_quiet(tmp)

    @staticmethod
    def _unlink_quiet(path) -> None:
        """Remove a leftover temp file; never raises."""
        if path is None:
            return
        try:
            if os.path.lexists(path):
                os.unlink(path)
        except OSError:
            pass

    def _copy_file(self, source: Path, target: Path) -> None:
        if not self._guard_links(target):
            return  # before is_dir/exists: those follow links
        data, err = self._read_bytes(source)
        if data is None:
            self._record(target, "skipped", err)
            self.failed = True
            return
        if target.is_dir():
            self._record(target, "skipped", "a directory exists at this path")
            return
        if target.exists():
            current, err = self._read_bytes(target)
            if current is None:
                self._record(target, "skipped", err)
                return
            if current == data:
                self._record(target, "unchanged")
                return
            if not self.force:
                self._record(target, "skipped", "modified locally; pass --force to overwrite")
                return
            if self._write_bytes(target, data):
                self._record(target, "written", "overwritten (--force)")
            return
        if self._write_bytes(target, data):
            self._record(target, "written")

    # -- .aidd bundle --------------------------------------------------------
    def install_dot_aidd(self) -> None:
        source_root = self.adapters_dir / "dot-aidd"
        target_root = self.project_root / ".aidd"
        try:
            files = sorted(p for p in source_root.rglob("*") if p.is_file())
        except OSError as exc:
            self._record(target_root, "skipped", f"cannot list {source_root}: {exc}")
            self.failed = True
            return
        for source in files:
            rel = source.relative_to(source_root)
            if any(part in IGNORED_DIRS for part in rel.parts) or source.suffix in IGNORED_SUFFIXES:
                continue
            if rel.parts and rel.parts[0] in PROTECTED_NAMES:
                continue  # owner's state: never touched
            self._copy_file(source, target_root / rel)

    # -- JSON merge ----------------------------------------------------------
    def _load_json(self, target: Path):
        """Return (data, error). Missing file -> ({}, ""). Corrupt -> (None, reason)."""
        if not target.exists():
            return {}, ""
        try:
            text = target.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            return None, f"cannot read: {exc}"
        if not text.strip():
            return {}, ""
        try:
            data = json.loads(text)
        except ValueError as exc:
            return None, f"not valid JSON, left untouched: {exc}"
        if not isinstance(data, dict):
            return None, "top-level JSON is not an object, left untouched"
        return data, ""

    def _save_json(self, target: Path, data: dict, existed: bool, reason: str = "") -> None:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if self._write_bytes(target, text.encode("utf-8")):
            self._record(target, "written", reason or ("merged" if existed else "created"))

    # -- gemini --------------------------------------------------------------
    def _merge_gemini_hooks(self, data: dict):
        """Mutate data in place; return (changed, error)."""
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            return False, "`hooks` is not an object, left untouched"
        changed = False
        for event, name, command in GEMINI_HOOKS:
            groups = hooks.setdefault(event, [])
            if not isinstance(groups, list):
                return False, f"`hooks.{event}` is not an array, left untouched"
            wanted = {"name": name, "type": "command", "command": command}
            found = False
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                    continue
                aidd_idx = [i for i, e in enumerate(group["hooks"])
                            if isinstance(e, dict) and e.get("name") == name]
                if not aidd_idx:
                    continue
                only_aidd = all(isinstance(e, dict) and e.get("name") in AIDD_NAMES for e in group["hooks"])
                if only_aidd:
                    found = True
                    for entry in (group["hooks"][i] for i in aidd_idx):
                        for key, value in wanted.items():
                            if entry.get(key) != value:
                                entry[key] = value
                                changed = True
                    if group.get("matcher") != GEMINI_MATCHER:
                        group["matcher"] = GEMINI_MATCHER
                        changed = True
                    break
                # mixed group: keep its matcher and foreign hooks; the aidd entry moves to its own group
                group["hooks"] = [e for i, e in enumerate(group["hooks"]) if i not in aidd_idx]
                changed = True
            if not found:
                groups.append({"matcher": GEMINI_MATCHER, "hooks": [wanted]})
                changed = True
        return changed, ""

    def install_gemini(self) -> None:
        self._copy_file(self.adapters_dir / "GEMINI.md", self.project_root / "GEMINI.md")
        target = self.project_root / ".gemini" / "settings.json"
        if not self._guard_links(target):
            return  # never read or merge through a link
        data, err = self._load_json(target)
        if data is None:
            self._record(target, "skipped", err)
            return
        changed, err = self._merge_gemini_hooks(data)
        if err:
            self._record(target, "skipped", err)
        elif changed:
            self._save_json(target, data, target.exists())
        else:
            self._record(target, "unchanged")

    # -- opencode ------------------------------------------------------------
    @staticmethod
    def _is_aidd_plugin(entry) -> bool:
        if not isinstance(entry, str):
            return False
        norm = entry.replace("\\", "/").strip()
        return norm.rsplit("/", 1)[-1] == "aidd.js"

    def install_opencode(self) -> None:
        oc_src = self.adapters_dir / "opencode"
        oc_dst = self.project_root / ".opencode"
        self._copy_file(oc_src / "skills" / "aidd" / "SKILL.md", oc_dst / "skills" / "aidd" / "SKILL.md")
        self._copy_file(oc_src / "plugins" / "aidd.js", oc_dst / "plugins" / "aidd.js")
        target = oc_dst / "opencode.json"
        if not self._guard_links(target):
            return  # never read or merge through a link
        data, err = self._load_json(target)
        if data is None:
            self._record(target, "skipped", err)
            return
        # spec 012 FR-1205: `.opencode/plugins/` is auto-discovered, so no relative
        # entry is added any more; an existing one is never removed.
        if not target.exists():
            return  # nothing to register: the file is not created
        plugins = data.get("plugin")
        if isinstance(plugins, list) and any(self._is_aidd_plugin(p) for p in plugins):
            self._record(target, "unchanged", "existing aidd plugin entry kept")
        else:
            self._record(target, "unchanged", "no plugin entry needed (plugins/ is auto-discovered)")

    # -- antigravity ---------------------------------------------------------
    def install_antigravity(self) -> None:
        ag_src = self.adapters_dir / "antigravity"
        ag_dst = self.project_root / ".agents"
        self._copy_file(ag_src / "skills" / "aidd" / "SKILL.md", ag_dst / "skills" / "aidd" / "SKILL.md")
        self._copy_file(ag_src / "rules" / "aidd.md", ag_dst / "rules" / "aidd.md")
        target = ag_dst / "hooks.json"
        if not self._guard_links(target):
            return  # never read or merge through a link
        data, err = self._load_json(target)
        if data is None:
            self._record(target, "skipped", err)
            return
        wanted = antigravity_entry()
        current = data.get(ANTIGRAVITY_HOOK_NAME)
        if current == wanted:
            self._record(target, "unchanged")
            return
        existed = target.exists()
        if current is not None and not self.force:
            self._record(target, "skipped",
                         f"the `{ANTIGRAVITY_HOOK_NAME}` entry differs from the shipped one; pass --force to update it")
            return
        data[ANTIGRAVITY_HOOK_NAME] = wanted
        reason = f"updated the `{ANTIGRAVITY_HOOK_NAME}` entry (--force)" if current is not None else ""
        self._save_json(target, data, existed, reason)

    # -- git hooks (spec 012 FR-1204) ---------------------------------------
    def _git_hooks_dir(self):
        """Return (hooks_dir, error) from `git rev-parse --git-path hooks`."""
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.project_root), "rev-parse", "--git-path", "hooks"],
                capture_output=True, text=True, timeout=GIT_TIMEOUT)
        except FileNotFoundError:
            return None, "git is not on PATH"
        except subprocess.TimeoutExpired:
            return None, f"`git rev-parse` timed out after {GIT_TIMEOUT} s"
        except OSError as exc:
            return None, f"cannot run git: {exc}"
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out:
            detail = (proc.stderr or "").strip().splitlines()
            return None, "not a git repository" + (f": {detail[0]}" if detail else "")
        hooks = Path(out)
        if not hooks.is_absolute():
            hooks = self.project_root / hooks
        return hooks, ""

    def _hook_links_refused(self, hooks_dir: Path, hook: Path) -> bool:
        """Record and return True when the hooks folder or hook file is a link.

        Inside the project root every component is checked; outside it (a
        worktree's shared `.git/hooks`) the hooks folder and the file are. A link
        is refused even with --force: `.git/` is git's state, not ours.
        """
        checks = [hooks_dir, hook]
        try:
            rel = hook.relative_to(self.project_root)
            checks = [self.project_root.joinpath(*rel.parts[:d]) for d in range(1, len(rel.parts) + 1)]
        except ValueError:
            pass
        for comp in checks:
            if is_link(comp):
                self._record(hook, "skipped", f"symlink {comp} -> {link_target(comp)}; hooks are never written through a link")
                self.failed = True
                return True
        return False

    def _make_executable(self, hook: Path, base_mode: int) -> None:
        try:
            os.chmod(hook, base_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass  # Windows ignores the bits; git for Windows runs hooks by shebang

    def _install_one_githook(self, hooks_dir: Path, name: str) -> None:
        hook = hooks_dir / name
        if self._hook_links_refused(hooks_dir, hook):
            return
        if hook.is_dir():
            self._record(hook, "skipped", "a directory exists at this path")
            self.failed = True
            return
        if not os.path.lexists(hook):
            if self._atomic_write(hook, githook_script(name)):
                self._make_executable(hook, 0o644)
                self._record(hook, "written", "created")
            return
        current, err = self._read_bytes(hook)
        if current is None:
            self._record(hook, "skipped", err)
            self.failed = True
            return
        if GITHOOK_MARKER.encode("utf-8") in current:
            self._record(hook, "unchanged")
            return
        if not is_sh_hook(current):
            self._record(hook, "skipped", "foreign hook is not a sh script; add `aidd guard` to it by hand")
            self.failed = True
            return
        try:
            mode = stat.S_IMODE(os.stat(hook).st_mode)
        except OSError:
            mode = 0o644
        sep = b"" if not current or current.endswith(b"\n") else b"\n"
        if self._atomic_write(hook, current + sep + githook_block(name)):
            self._make_executable(hook, mode)
            self._record(hook, "written", "aidd block appended to the existing hook")

    def install_githooks(self) -> None:
        """Write or extend `pre-commit` and `pre-push` so they run `aidd guard`."""
        hooks_dir, err = self._git_hooks_dir()
        if hooks_dir is None:
            self._record(self.project_root / ".git" / "hooks", "skipped", err)
            self.failed = True
            return
        for name in GITHOOK_NAMES:
            self._install_one_githook(hooks_dir, name)

    # -- entry ---------------------------------------------------------------
    def run(self) -> None:
        if self.host is None:
            return  # `--githooks` alone: main() calls install_githooks
        self.install_dot_aidd()
        if self.host == "gemini":
            self.install_gemini()
        elif self.host == "antigravity":
            self.install_antigravity()
        else:
            self.install_opencode()


def _repo_root() -> Path:
    # skill/scripts/install_host.py -> repo root when run from a clone. When the scripts come from the INSTALLED skill
    # (~/.claude/skills/aidd/scripts, see aidd/cli.py) there is no sibling adapters/: use the copy bundled in the aidd
    # package (aidd/_data), which `pip install` of this repo refreshes.
    here = Path(__file__).resolve()
    candidates = [here.parent.parent.parent]
    try:
        import importlib.util
        spec = importlib.util.find_spec("aidd")
        if spec and spec.origin:
            candidates.append(Path(spec.origin).parent / "_data")
    except Exception:
        pass
    for c in candidates:
        if (c / "adapters" / "dot-aidd").is_dir():
            return c
    return candidates[0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="install_host.py",
                                     description="Non-destructive AIDD install for Gemini CLI, OpenCode or Antigravity.")
    sub = parser.add_subparsers(dest="action", required=True)
    p_install = sub.add_parser("install", help="install AIDD for one host into a project")
    p_install.add_argument("targets", nargs="+", metavar="[host] project_root",
                           help=f"host ({'|'.join(HOSTS)}) and project root; the host may be omitted with --githooks")
    p_install.add_argument("--githooks", action="store_true",
                           help="write git pre-commit/pre-push hooks that run `aidd guard` (alone or with a host)")
    p_install.add_argument("--force", action="store_true", help="overwrite locally modified shipped files")
    p_install.add_argument("--json", action="store_true", help="print a JSON list of {path,status,reason}")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    host, root_arg, err = _split_targets(args.targets, args.githooks)
    if err:
        parser.print_usage(sys.stderr)
        print(f"install_host.py: error: {err}", file=sys.stderr)
        return 1
    args.host, args.project_root = host, root_arg

    repo_root = _repo_root()
    if not (repo_root / "adapters" / "dot-aidd").is_dir():
        print(f"error: shipped bundle not found at {repo_root / 'adapters' / 'dot-aidd'}", file=sys.stderr)
        return 1
    project_root = Path(args.project_root)
    try:
        project_root = project_root.resolve()
    except OSError as exc:
        print(f"error: cannot resolve {args.project_root}: {exc}", file=sys.stderr)
        return 1
    if not project_root.is_dir():
        print(f"error: project root is not a directory: {project_root}", file=sys.stderr)
        return 1

    installer = HostInstaller(args.host, project_root, args.force, repo_root)
    installer.run()
    if args.githooks:
        installer.install_githooks()
    label = args.host if args.host else "githooks"
    if args.host and args.githooks:
        label = f"{args.host} + githooks"

    if args.json:
        print(json.dumps(installer.results, indent=2, ensure_ascii=False))
    else:
        for item in installer.results:
            line = f"{item['status']} {item['path']}"
            if item["reason"]:
                line += f"  ({item['reason']})"
            print(line)
        counts = {s: sum(1 for r in installer.results if r["status"] == s)
                  for s in ("written", "unchanged", "skipped")}
        print(f"AIDD install ({label}) into {project_root}: "
              f"{counts['written']} written, {counts['unchanged']} unchanged, {counts['skipped']} skipped"
              + (" -- some targets were not writable or the gate registration was skipped" if installer.failed else ""))
        if args.host in GITHOOK_OFFER_HOSTS and not args.githooks:
            print(f"hint: {args.host} 2.x has no write gate; enforce AIDD at commit time with "
                  f"`aidd install --githooks {project_root}`")
    return 1 if installer.failed else 0


def _split_targets(targets: list, githooks: bool):
    """Return (host, project_root, error) from `[host] project_root`."""
    if len(targets) == 2:
        if targets[0] not in HOSTS:
            return None, None, f"invalid host {targets[0]!r} (choose from {', '.join(HOSTS)})"
        return targets[0], targets[1], ""
    if len(targets) == 1:
        if targets[0] in HOSTS:
            return None, None, "the project root is required"
        if not githooks:
            return None, None, f"a host ({', '.join(HOSTS)}) is required unless --githooks is given"
        return None, targets[0], ""
    return None, None, "expected `[host] project_root`"


if __name__ == "__main__":
    sys.exit(main())
