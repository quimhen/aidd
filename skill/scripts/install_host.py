"""install_host.py — non-destructive AIDD install for a non-Claude host.

aidd:FR-901 aidd:FR-902 aidd:FR-903 aidd:AC-005 (spec 009, plan Interface 2, task T-04)
aidd:FR-1103 aidd:FR-1104 aidd:AC-1103 (spec 011, plan Interface 2, task T-02)

Usage:
    python install_host.py install <gemini|opencode|antigravity> <project-root> [--force] [--json]

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

ANTIGRAVITY_HOOK_NAME = "aidd"
ANTIGRAVITY_MATCHER = "*"
ANTIGRAVITY_TIMEOUT = 30
ANTIGRAVITY_COMMANDS = (
    ("PreToolUse", "python ../.aidd/hooks/host_adapter.py antigravity pre"),
    ("PostToolUse", "python ../.aidd/hooks/host_adapter.py antigravity post"),
)

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
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return True
        except OSError as exc:
            self._record(target, "skipped", f"cannot write: {exc}")
            self.failed = True
            return False

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
        plugins = data.setdefault("plugin", [])
        if not isinstance(plugins, list):
            self._record(target, "skipped", "`plugin` is not an array, left untouched")
            return
        if any(self._is_aidd_plugin(p) for p in plugins):
            self._record(target, "unchanged")
            return
        plugins.append(OPENCODE_PLUGIN_ENTRY)
        self._save_json(target, data, target.exists())

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

    # -- entry ---------------------------------------------------------------
    def run(self) -> None:
        self.install_dot_aidd()
        if self.host == "gemini":
            self.install_gemini()
        elif self.host == "antigravity":
            self.install_antigravity()
        else:
            self.install_opencode()


def _repo_root() -> Path:
    # skill/scripts/install_host.py -> repo root (same lookup as aidd/cli.py).
    return Path(__file__).resolve().parent.parent.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="install_host.py",
                                     description="Non-destructive AIDD install for Gemini CLI, OpenCode or Antigravity.")
    sub = parser.add_subparsers(dest="action", required=True)
    p_install = sub.add_parser("install", help="install AIDD for one host into a project")
    p_install.add_argument("host", choices=HOSTS)
    p_install.add_argument("project_root")
    p_install.add_argument("--force", action="store_true", help="overwrite locally modified shipped files")
    p_install.add_argument("--json", action="store_true", help="print a JSON list of {path,status,reason}")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

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
        print(f"AIDD install ({args.host}) into {project_root}: "
              f"{counts['written']} written, {counts['unchanged']} unchanged, {counts['skipped']} skipped"
              + (" -- some targets were not writable" if installer.failed else ""))
    return 1 if installer.failed else 0


if __name__ == "__main__":
    sys.exit(main())
