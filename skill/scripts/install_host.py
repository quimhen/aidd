"""install_host.py — non-destructive AIDD install for a non-Claude host.

aidd:FR-901 aidd:FR-902 aidd:FR-903 aidd:AC-005 (spec 009, plan Interface 2, task T-04)

Usage:
    python install_host.py install <gemini|opencode> <project-root> [--force] [--json]

What it does (and what it never does):
- Copies the shipped `adapters/dot-aidd/` bundle into `<project-root>/.aidd/`
  FILE BY FILE, comparing bytes: identical -> `unchanged`; missing -> `written`;
  different -> `skipped` (kept) unless `--force` (then `written`).
- Never calls `aidd init` (its `--force` runs rmtree on `.aidd/`), never deletes
  anything, never touches `.aidd/memory/`, `.aidd/evidence/`, `.aidd/gate_spec`
  or `.aidd/active_spec`.
- Writes the host files and merges the host registration JSON by key, keeping
  every foreign entry and key; a corrupt existing JSON is left as is (`skipped`).

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
"""
import argparse
import json
import sys
from pathlib import Path

HOSTS = ("gemini", "opencode")
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

    # -- reporting ---------------------------------------------------------
    def _record(self, target: Path, status: str, reason: str = "") -> None:
        try:
            rel = target.relative_to(self.project_root).as_posix()
        except ValueError:
            rel = str(target)
        self.results.append({"path": rel, "status": status, "reason": reason})

    # -- low-level io ------------------------------------------------------
    @staticmethod
    def _read_bytes(path: Path):
        try:
            return path.read_bytes(), ""
        except OSError as exc:
            return None, f"cannot read {path}: {exc}"

    def _write_bytes(self, target: Path, data: bytes) -> bool:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return True
        except OSError as exc:
            self._record(target, "skipped", f"cannot write: {exc}")
            self.failed = True
            return False

    def _copy_file(self, source: Path, target: Path) -> None:
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

    def _save_json(self, target: Path, data: dict, existed: bool) -> None:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if self._write_bytes(target, text.encode("utf-8")):
            self._record(target, "written", "merged" if existed else "created")

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

    # -- entry ---------------------------------------------------------------
    def run(self) -> None:
        self.install_dot_aidd()
        if self.host == "gemini":
            self.install_gemini()
        else:
            self.install_opencode()


def _repo_root() -> Path:
    # skill/scripts/install_host.py -> repo root (same lookup as aidd/cli.py).
    return Path(__file__).resolve().parent.parent.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="install_host.py",
                                     description="Non-destructive AIDD install for Gemini CLI or OpenCode.")
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
