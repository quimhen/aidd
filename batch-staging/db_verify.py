#!/usr/bin/env python3
"""eDoc DB verifier: build a clean database, apply every migration and seed, report failures.

Reproducible, stdlib only. It drives the `psql` client through subprocess, so no Python
DB driver is needed. No credentials live in this file: connection parameters come from
the standard libpq environment variables (PGHOST, PGPORT, PGUSER, PGPASSWORD, ...) or
from EDOC_DB_PSQL (see below).

What it does (in order)
  1. CREATE DATABASE <unique temp name> (admin connection, default db `postgres`, used only
     to run CREATE/DROP DATABASE; no data in it is read or changed).
  2. Optional bootstrap of the Supabase pieces a plain Postgres lacks (roles anon /
     authenticated / service_role, schemas auth / storage / vault / extensions, auth.uid()
     / auth.jwt() / auth.role(), auth.users, storage.buckets/objects, vault stubs,
     publication supabase_realtime). Only objects that are missing are created.
  3. Apply, each file in its own psql run with ON_ERROR_STOP=1:
        migrations 0001-0099 -> seeds 001-099 -> migrations 0100+ -> seeds 100+
     (phased order, so a seed can rely on the tables created by earlier migrations).
     Lists exactly which files failed and the first error psql reported.
  4. Optional pgTAP (`--tap`): pg_prove if available and not in docker mode, else psql.
  5. Optional plpgsql_check (`--plpgsql-check`): static check of every plpgsql function body
     (catches references to non-existent columns/relations) when the extension exists.
     Findings listed in the baseline (`--plpgsql-baseline`, default
     eDoc/tools/plpgsql_check_baseline.txt) are reported as accepted; only findings that are
     not in the baseline fail the gate, so the check still catches regressions.
  6. DROP DATABASE (unless --keep-db).

--apply-only runs steps 1-3 only (no pgTAP, no plpgsql_check).

Connection modes
  * Host psql (CI):      export PGHOST=localhost PGPORT=5432 PGUSER=postgres PGPASSWORD=...
                         python eDoc/tools/db_verify.py --tap --plpgsql-check
  * Local docker stack:  EDOC_DB_PSQL="docker exec -i supabase_db_edoc psql -U postgres" \
                         python eDoc/tools/db_verify.py --tap --plpgsql-check
    EDOC_DB_PSQL (or --psql) is the command prefix used to launch psql; SQL is passed on stdin,
    so it also works through `docker exec -i`.

Exit code: 0 all good, 1 verification failures, 2 usage / infrastructure error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # eDoc/
MIG_DIR = ROOT / "supabase" / "migrations"
SEED_DIR = ROOT / "supabase" / "seed"
TEST_DIR = ROOT / "supabase" / "tests"
DB_PREFIX = "edoc_verify_"
PROTECTED = {"postgres", "template0", "template1", "_supabase"}

BOOTSTRAP_SQL = r"""
-- Idempotent Supabase shims for a plain Postgres. Only creates what is missing.
DO $b$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role','authenticator','supabase_auth_admin'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', r);
    END IF;
  END LOOP;
END $b$;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS vault;
GRANT USAGE ON SCHEMA extensions, auth, storage TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

CREATE TABLE IF NOT EXISTS auth.users (
  instance_id uuid, id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  aud varchar(255), role varchar(255), email varchar(255), encrypted_password varchar(255),
  email_confirmed_at timestamptz, invited_at timestamptz, confirmation_token varchar(255),
  confirmation_sent_at timestamptz, recovery_token varchar(255), recovery_sent_at timestamptz,
  email_change_token_new varchar(255), email_change varchar(255), email_change_sent_at timestamptz,
  last_sign_in_at timestamptz, raw_app_meta_data jsonb, raw_user_meta_data jsonb,
  is_super_admin boolean, created_at timestamptz, updated_at timestamptz, phone text,
  phone_confirmed_at timestamptz, phone_change text DEFAULT '', phone_change_token varchar(255) DEFAULT '',
  phone_change_sent_at timestamptz, confirmed_at timestamptz, email_change_token_current varchar(255) DEFAULT '',
  email_change_confirm_status smallint DEFAULT 0, banned_until timestamptz,
  reauthentication_token varchar(255) DEFAULT '', reauthentication_sent_at timestamptz,
  is_sso_user boolean DEFAULT false, deleted_at timestamptz, is_anonymous boolean DEFAULT false
);
GRANT SELECT ON auth.users TO service_role;

-- Same default privileges the Supabase stack gives schema public (must precede the migrations).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role;

DO $b$
BEGIN
  IF to_regprocedure('auth.jwt()') IS NULL THEN
    CREATE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS
      $f$ SELECT coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $f$;
  END IF;
  IF to_regprocedure('auth.uid()') IS NULL THEN
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
      $f$ SELECT nullif(coalesce(nullif(current_setting('request.jwt.claim.sub', true), ''),
                                 (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')), '')::uuid $f$;
  END IF;
  IF to_regprocedure('auth.role()') IS NULL THEN
    CREATE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS
      $f$ SELECT coalesce(nullif(current_setting('request.jwt.claim.role', true), ''),
                          (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')) $f$;
  END IF;
END $b$;

CREATE TABLE IF NOT EXISTS storage.buckets (
  id text PRIMARY KEY, name text NOT NULL, owner uuid, public boolean DEFAULT false,
  file_size_limit bigint, allowed_mime_types text[],
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS storage.objects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), bucket_id text REFERENCES storage.buckets(id),
  name text, owner uuid, metadata jsonb, path_tokens text[],
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
DO $b$
BEGIN
  IF to_regprocedure('storage.foldername(text)') IS NULL THEN
    CREATE FUNCTION storage.foldername(name text) RETURNS text[] LANGUAGE sql IMMUTABLE AS
      $f$ SELECT (string_to_array(name, '/'))[1:array_length(string_to_array(name, '/'), 1) - 1] $f$;
  END IF;
END $b$;

-- vault stubs (only if the real supabase_vault extension is not installed)
DO $b$
BEGIN
  IF to_regclass('vault.secrets') IS NULL
     AND NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'supabase_vault') THEN
    CREATE TABLE vault.secrets (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text UNIQUE,
                                description text DEFAULT '', secret text);
    CREATE VIEW vault.decrypted_secrets AS
      SELECT id, name, description, secret, secret AS decrypted_secret FROM vault.secrets;
    CREATE FUNCTION vault.create_secret(new_secret text, new_name text DEFAULT NULL, new_description text DEFAULT '')
      RETURNS uuid LANGUAGE sql AS
      $f$ INSERT INTO vault.secrets(name, description, secret) VALUES (new_name, new_description, new_secret) RETURNING id $f$;
  END IF;
END $b$;

DO $b$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    CREATE PUBLICATION supabase_realtime;
  END IF;
END $b$;
"""


@dataclass
class StepResult:
    name: str
    ok: bool
    seconds: float = 0.0
    error: str = ""


@dataclass
class Report:
    database: str = ""
    steps: list[StepResult] = field(default_factory=list)
    tap: list[dict] = field(default_factory=list)
    plpgsql_check: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class Psql:
    """Launch psql using the configured command prefix; SQL is supplied on stdin."""

    def __init__(self, prefix: list[str]):
        self.prefix = prefix

    def run(self, db: str, sql: str, *, stop_on_error: bool = True, tuples: bool = False,
            single_tx: bool = False, timeout: int = 900) -> subprocess.CompletedProcess:
        cmd = list(self.prefix) + ["-X", "-q", "-d", db, "-v", f"ON_ERROR_STOP={1 if stop_on_error else 0}"]
        if tuples:
            cmd += ["-At", "-F", "\t"]
        if single_tx:
            cmd.append("-1")
        cmd += ["-f", "-"]
        # SQL goes as bytes: text mode turns every LF into CRLF on Windows, which corrupts
        # multi-line string literals (pgTAP expectations) and makes tests fail only under this runner.
        r = subprocess.run(cmd, input=sql.encode("utf-8"), capture_output=True, timeout=timeout)
        return subprocess.CompletedProcess(r.args, r.returncode,
                                           r.stdout.decode("utf-8", errors="replace"),
                                           r.stderr.decode("utf-8", errors="replace"))


TPL_KEEP = 3          # templates kept: one per migration set in use (base, +Payroll/Selection, ...)
WORK_DB = DB_PREFIX + "work"


def acquire_lock(wait_s: int):
    """OS file lock on a temp file (released automatically when the process ends or is killed). Returns the open
    file (keep a reference until exit) or None after `wait_s` seconds."""
    f = open(Path(tempfile.gettempdir()) / "edoc_verify_work.lock", "a+")
    deadline, announced = time.time() + wait_s, False
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() > deadline:
                return None
            if not announced:
                print("Waiting for another db_verify run to finish (single shared test database)...", flush=True)
                announced = True
            time.sleep(2)


def gc_databases(psql: "Psql", admin_db: str) -> int:
    """Drop idle edoc_verify_* databases left by old runs/agents; keep the work db and the TPL_KEEP newest templates.
    Databases with an open session are skipped (never drops what someone is using)."""
    rows = psql.run(admin_db,
                    "SELECT d.datname, pg_database_size(d.datname), "
                    "(SELECT count(*) FROM pg_stat_activity a WHERE a.datname = d.datname), "
                    "split_part(coalesce(shobj_description(d.oid,'pg_database'),'0'),'|',1) "
                    f"FROM pg_database d WHERE d.datname LIKE '{DB_PREFIX}%' ORDER BY 1;", tuples=True).stdout.splitlines()
    dbs = [r.split("\t") for r in rows if r.strip()]
    tpls = sorted((d for d in dbs if d[0].startswith(DB_PREFIX + "tpl_")),
                  key=lambda d: float(d[3]) if d[3].replace(".", "", 1).isdigit() else 0.0, reverse=True)
    keep = {WORK_DB} | {d[0] for d in tpls[:TPL_KEEP]}
    dropped = freed = 0
    for name, size, sessions, _ in dbs:
        if name in keep or name in PROTECTED:
            continue
        if int(sessions) > 0:
            print(f"skip   {name}: {sessions} open session(s)")
            continue
        r = psql.run(admin_db, f'DROP DATABASE IF EXISTS "{name}";')
        print(("dropped " if r.returncode == 0 else "FAILED  ") + f"{name} ({int(size) // 1048576} MB)")
        if r.returncode == 0:
            dropped, freed = dropped + 1, freed + int(size)
    print(f"== gc: {dropped} database(s) dropped, {freed // 1048576} MB freed; kept {sorted(keep)}")
    return 0


def template_failed(psql: "Psql", admin_db: str, tpl: str) -> list:
    """Apply failures recorded with the template (comment `<epoch>|<json list of [file, error]>`)."""
    out = psql.run(admin_db, f"SELECT coalesce(shobj_description(oid,'pg_database'),'') FROM pg_database "
                             f"WHERE datname='{tpl}';", tuples=True).stdout.strip()
    try:
        return json.loads(out.split("|", 1)[1]) if "|" in out else []
    except Exception:
        return []


def touch_template(psql: "Psql", admin_db: str, tpl: str, failed: list | None = None) -> None:
    """Record last-use epoch + the build's apply failures in the template's comment (best effort). The epoch picks
    the newest TPL_KEEP templates; the failures are replayed on every clone so a cached build reports the same
    failing files (and exit code) as a fresh one. `failed=None` keeps what is already recorded."""
    if failed is None:
        failed = template_failed(psql, admin_db, tpl)
    note = f"{int(time.time())}|{json.dumps(failed, ensure_ascii=False)}".replace("'", "''")
    psql.run(admin_db, f"COMMENT ON DATABASE \"{tpl}\" IS '{note}';")


def apply_batched(psql: "Psql", db: str, plan: list, with_dirs: bool) -> list[tuple[str, str]]:
    """Apply every migration/seed in ONE psql session (a `docker exec psql` process costs ~0.4 s to start, which for
    ~1000 files dwarfs the SQL itself on an empty database). Each file is preceded by ROLLBACK + DISCARD ALL so a
    session-level SET / SET ROLE / open transaction of one file cannot leak into the next, like separate sessions.
    ON_ERROR_STOP is off: a failing file reports its first error (attributed by input line range) and the run
    continues; unlike the per-file mode (--exact-apply) the rest of a failing file is still executed."""
    parts, ranges, line = [], [], 1
    for kind, path in plan:
        sql = path.read_text(encoding="utf-8")
        if not sql.endswith("\n"):
            sql += "\n"
        block = "ROLLBACK;\nDISCARD ALL;\n" + sql
        n = block.count("\n")
        ranges.append((line, line + n - 1, f"{kind} {str(path) if with_dirs else path.name}"))
        parts.append(block)
        line += n
    r = psql.run(db, "".join(parts), stop_on_error=False, timeout=3600)
    first: dict[int, str] = {}
    for m in re.finditer(r"psql:<stdin>:(\d+): (?:ERROR|FATAL|PANIC):\s*(.*)", r.stderr):
        ln = int(m.group(1))
        for i, (lo, hi, _name) in enumerate(ranges):
            if lo <= ln <= hi:
                first.setdefault(i, m.group(2).strip())
                break
    if r.returncode != 0 and not first:
        return [("apply (one psql session)", first_error(r.stderr, r.stdout))]
    return [(ranges[i][2], first[i]) for i in sorted(first)]


def docker_container_ip(prefix: list[str]) -> str | None:
    """Non-loopback IP of the container when the psql prefix is `docker exec ... <container> psql ...`."""
    if len(prefix) < 3 or prefix[0] != "docker" or prefix[1] != "exec":
        return None
    rest = prefix[2:]
    container = next((a for a in rest if not a.startswith("-")), None)
    if not container:
        return None
    try:
        r = subprocess.run(["docker", "exec", container, "hostname", "-i"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    ips = r.stdout.decode("utf-8", errors="replace").split()
    return ips[0] if r.returncode == 0 and ips else None


def first_error(stderr: str, stdout: str = "") -> str:
    text = (stderr or "") + "\n" + (stdout or "")
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if "ERROR:" in ln:
            ctx = [ln]
            for extra in lines[i + 1:i + 4]:
                if re.search(r"(LINE \d+|DETAIL:|HINT:|CONTEXT:|QUERY:)", extra):
                    ctx.append(extra)
            return " | ".join(c.strip() for c in ctx)
    return lines[-1].strip() if lines else "(no output)"


def sort_key(p: Path) -> tuple:
    m = re.match(r"(\d+)", p.name)
    return (int(m.group(1)) if m else 10**9, p.name)


def collect(directory: Path) -> list[Path]:
    # *_local_only.sql seeds (demo company/users for the local stack) must never reach CI/verify runs.
    return sorted((p for p in directory.glob("*.sql") if not p.name.endswith("_local_only.sql")), key=sort_key)


def num(p: Path) -> int:
    m = re.match(r"(\d+)", p.name)
    return int(m.group(1)) if m else 10**9


# aidd:FR-013
def build_plan(extra_dirs: list[Path] | None = None) -> list[tuple[str, Path]]:
    migs, seeds = collect(MIG_DIR), collect(SEED_DIR)
    plan = [("migration", p) for p in migs if num(p) < 100]
    plan += [("seed", p) for p in seeds if num(p) < 100]
    plan += [("migration", p) for p in migs if num(p) >= 100]
    plan += [("seed", p) for p in seeds if num(p) >= 100]
    if extra_dirs:
        for ed in extra_dirs:
            ed_mig_dir = ed / "supabase" / "migrations" if (ed / "supabase" / "migrations").exists() else ed / "migrations"
            ed_seed_dir = ed / "supabase" / "seed" if (ed / "supabase" / "seed").exists() else ed / "seed"
            ed_migs = collect(ed_mig_dir) if ed_mig_dir.exists() else []
            ed_seeds = collect(ed_seed_dir) if ed_seed_dir.exists() else []
            plan += [("migration", p) for p in ed_migs]
            plan += [("seed", p) for p in ed_seeds]
    return plan


def parse_tap(stdout: str) -> dict:
    planned = None
    ok = notok = 0
    failed: list[str] = []
    for ln in stdout.splitlines():
        m = re.match(r"^1\.\.(\d+)", ln)
        if m:
            planned = int(m.group(1))
        elif re.match(r"^not ok\b.*#\s*TODO\b", ln, re.IGNORECASE):
            ok += 1  # TAP: a failing TODO test is expected and is not a failure
        elif re.match(r"^not ok\b", ln):
            notok += 1
            failed.append(ln.strip())
        elif ln.strip().startswith("#") and failed:
            failed[-1] += "\n       " + ln.strip()
        elif re.match(r"^ok\b", ln):
            ok += 1
    return {"planned": planned, "ok": ok, "not_ok": notok, "failed": failed}


def _tap_batch_source(path: Path, allowlist: set[str]) -> str | None:
    """Only explicit, transaction-bounded files without obvious session hazards.

    The allowlist must itself be reviewed: lexical checks cannot prove a called
    function has no outside side effects. Anything ambiguous runs individually.
    """
    try:
        if str(path.resolve()) not in allowlist:
            return None
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?m)^\s*\\", text):
            return None
        if re.search(r"\b(?:COMMIT|DBLINK\w*|PG_SLEEP\w*|LISTEN|NOTIFY|COPY|DISCARD)\b", text, re.I):
            return None
        if not (re.search(r"\bBEGIN\s*;", text, re.I) and re.search(r"\bROLLBACK\s*;", text, re.I)):
            return None
        return text
    except (OSError, UnicodeError):
        return None


def tap_batch_eligible(path: Path, allowlist: set[str]) -> bool:
    return _tap_batch_source(path, allowlist) is not None


def run_tap_batch(psql: Psql, db: str, tests: list[Path], tap_prefix: str,
                  timeout: int, admin_db: str) -> list[tuple[Path, subprocess.CompletedProcess, float]]:
    """Run approved files via one psql process; reconnect before each file.

    Files are sent one at a time. EOF, timeout or SQL errors fail the active
    file; only files not yet started use a fresh process. Never retry a test
    that might have executed. stdout and stderr share one ordered pipe.
    """
    results = []
    batch_started = time.monotonic()
    launches = 0
    proc = None
    output = None

    def terminate():
        nonlocal proc
        if proc is None:
            return
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            else:
                import signal
                os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            proc.kill()
            proc.wait(timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
        for stream in (proc.stdin, proc.stdout):
            try:
                stream.close()
            except (OSError, AttributeError):
                pass
        proc = None

    def launch():
        nonlocal proc, output, launches
        cmd = list(psql.prefix) + ['-X', '-q', '-d', db, '-v', 'ON_ERROR_STOP=1', '-At', '-F', '\t', '-f', '-']
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=(os.name != 'nt'))
        launches += 1
        output = queue.Queue()
        target, process = output, proc
        def reader():
            try:
                for line in iter(process.stdout.readline, b''):
                    target.put(line)
            finally:
                target.put(None)
        threading.Thread(target=reader, daemon=True).start()

    try:
        for path in tests:
            start = time.monotonic()
            lines = []
            try:
                # Recheck immediately before use; send precisely the bytes inspected.
                source = _tap_batch_source(path, {str(path.resolve())})
                if source is None:
                    raise RuntimeError('batch eligibility changed before execution')
                if proc is None or proc.poll() is not None:
                    terminate()
                    launch()
                token = '__AIDD_TAP_' + uuid.uuid4().hex + '__'
                begin, end = token + '_BEGIN', token + '_END'
                # \p flushes stdout in psql even when stdout is a pipe.
                payload = ('\\connect ' + db + '\n\\echo ' + begin + '\n\\p\n' + tap_prefix +
                           source + '\nROLLBACK;\nDISCARD ALL;\n\\echo ' + end + '\n\\p\n').encode('utf-8')
                stream = proc.stdin
                writer_error = []
                def writer(data=payload, target_stream=stream, errors=writer_error):
                    try:
                        target_stream.write(data)
                        target_stream.flush()
                    except (OSError, ValueError) as exc:
                        errors.append(str(exc))
                threading.Thread(target=writer, daemon=True).start()
                deadline = start + timeout
                begun = complete = False
                prelude = []
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired('psql batch', timeout)
                    try:
                        line = output.get(timeout=remaining)
                    except queue.Empty:
                        raise subprocess.TimeoutExpired('psql batch', timeout)
                    if line is None:
                        break
                    decoded = line.decode('utf-8', errors='replace')
                    if decoded.strip() == begin:
                        begun = True
                    elif decoded.strip() == end and begun:
                        complete = True
                        break
                    elif begun:
                        lines.append(decoded)
                    else:
                        prelude.append(decoded)
                if not complete:
                    lines[:0] = prelude
                    raise RuntimeError('psql session ended before the test completed' +
                                       (': ' + writer_error[0] if writer_error else ''))
                if proc.poll() is not None:
                    raise RuntimeError('psql session ended while reporting the test')
                if path.read_text(encoding='utf-8') != source:
                    raise RuntimeError('test file changed during execution')
                results.append((path, subprocess.CompletedProcess([], 0, ''.join(lines), ''), time.monotonic() - start))
            except (OSError, UnicodeError, RuntimeError, subprocess.TimeoutExpired) as exc:
                terminate()
                if isinstance(exc, subprocess.TimeoutExpired):
                    try:
                        psql.run(admin_db, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db}' AND pid <> pg_backend_pid();")
                    except Exception:
                        pass
                results.append((path, subprocess.CompletedProcess([], 1, ''.join(lines),
                                f'{type(exc).__name__}: {exc}'), time.monotonic() - start))
    finally:
        terminate()
    print(f'== pgTAP batch: {len(tests)} file(s), {launches} psql process(es), '
          f'{time.monotonic() - batch_started:.2f}s')
    return results


PLPGSQL_CHECK_SQL = r"""
WITH fns AS (
  SELECT p.oid, p.oid::regprocedure::text AS sig, 0::oid AS relid,
         NULL::name AS newtable, NULL::name AS oldtable
  FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE l.lanname = 'plpgsql' AND n.nspname = ANY (string_to_array('{schemas}', ','))
    AND p.prorettype <> 'pg_catalog.trigger'::regtype
    {fn_filter}
  UNION
  SELECT p.oid, p.oid::regprocedure::text, t.tgrelid, t.tgnewtable, t.tgoldtable
  FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
  JOIN pg_language l ON l.oid = p.prolang JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE NOT t.tgisinternal AND l.lanname = 'plpgsql' AND n.nspname = ANY (string_to_array('{schemas}', ','))
    {fn_filter}
)
SELECT f.sig, c.level, c.lineno, c.message
FROM fns f
CROSS JOIN LATERAL plpgsql_check_function_tb(f.oid, f.relid, fatal_errors => false,
                                         newtable => f.newtable, oldtable => f.oldtable) c
WHERE c.level = 'error' OR ({warnings} AND c.level LIKE 'warning%')
ORDER BY f.sig, c.lineno;
"""


def finding_key(row: list[str]) -> tuple[str, str]:
    """Identity of a plpgsql_check finding: signature + message (line numbers drift)."""
    sig = row[0].strip() if row else ""
    msg = row[3].strip() if len(row) > 3 else ""
    return (sig, msg)


def load_plpgsql_baseline(path: str) -> set[tuple[str, str]]:
    """Read a `signature | message | reason` baseline; `#` comments and blank lines are ignored."""
    entries: set[tuple[str, str]] = set()
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        entries.add((parts[0], parts[1]))
    return entries


def main() -> int:
    # Test output can carry any character (e.g. a BOM in a failure detail). On Windows a redirected stdout is cp1252
    # and printing it crashed the run before plpgsql_check and the RESULT line: never fail on output encoding.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--psql", default=os.environ.get("EDOC_DB_PSQL", "psql"),
                    help="psql command prefix (default: $EDOC_DB_PSQL or 'psql'), e.g. "
                         "'docker exec -i supabase_db_edoc psql -U postgres'")
    ap.add_argument("--admin-db", default=os.environ.get("EDOC_DB_ADMIN", "postgres"),
                    help="existing db used ONLY to run CREATE/DROP DATABASE (default: postgres)")
    ap.add_argument("--db-name", default=None, help=f"temp db name (must start with {DB_PREFIX}); default unique")
    ap.add_argument("--apply-only", action="store_true", help="only create db + bootstrap + apply migrations/seeds")
    ap.add_argument("--tap", action="store_true", help="run pgTAP tests in eDoc/supabase/tests")
    ap.add_argument("--runner", choices=["auto", "psql", "pg_prove"], default="auto")
    ap.add_argument("--plpgsql-check", action="store_true", help="run plpgsql_check if the extension exists")
    ap.add_argument("--check-schemas", default="public", help="comma list of schemas for plpgsql_check")
    ap.add_argument("--check-warnings", action="store_true", help="include plpgsql_check warnings (default errors only)")
    ap.add_argument("--no-check-gate", action="store_true", help="plpgsql_check findings do not change the exit code")
    ap.add_argument("--plpgsql-baseline", default="auto", metavar="PATH",
                    help="baseline of accepted plpgsql_check findings ('auto' = eDoc/tools/plpgsql_check_baseline.txt "
                         "when it exists; pass an empty string to disable). New findings still fail the gate.")
    ap.add_argument("--write-plpgsql-baseline", default=None, metavar="PATH",
                    help="write the current findings to PATH as a baseline skeleton (review before committing)")
    ap.add_argument("--bootstrap", choices=["auto", "always", "never"], default="auto",
                    help="create missing Supabase shims (auto/always: yes, idempotent; never: skip)")
    ap.add_argument("--fail-fast", action="store_true", help="stop at the first failing migration/seed")
    ap.add_argument("--single-tx", action="store_true", help="run each file with psql -1 (single transaction)")
    ap.add_argument("--extra-dir", action="append", default=[],
                    help="extra directory containing supabase/migrations, supabase/seed, supabase/tests (repeatable)")
    ap.add_argument("--dblink-host", default=os.environ.get("EDOC_DB_DBLINK_HOST"),
                    help="host the dblink-based pgTAP test uses when inet_server_addr() is NULL "
                         "(default: container IP in `docker exec` mode, else 127.0.0.1)")
    ap.add_argument("--test-timeout", type=int, default=600, help="seconds allowed per pgTAP file (default 600)")
    ap.add_argument("--no-template-cache", action="store_true",
                    help="always build the temp db from scratch (default: clone a cached template db built from the "
                         "same bootstrap + migrations + seeds; the template key is a hash of their contents, so any "
                         "edit rebuilds it)")
    ap.add_argument("--exact-apply", action="store_true",
                    help="apply each file in its own psql process, stopping a file at its first error (slow: ~0.4 s "
                         "per file in docker mode). Default: all files in one psql session")
    ap.add_argument("--gc", action="store_true",
                    help="drop every idle edoc_verify_* database except the work db and the newest templates, then exit")
    ap.add_argument("--lock-wait", type=int, default=1800,
                    help="seconds to wait for another db_verify run to release the single test database (default 1800)")
    ap.add_argument("--keep-db", action="store_true", help="do not drop the test database after the run")
    ap.add_argument("--json", metavar="PATH", help="write a JSON report")
    ap.add_argument("--only-tests", default=None, help="substring filter for pgTAP file names")
    ap.add_argument("--tap-batch-allowlist", metavar="PATH",
                    help="opt in to persistent psql for reviewed test files listed one project-relative path per line")
    ap.add_argument("--only-functions", default=None,
                    help="regex/substring pattern for function names in plpgsql_check (e.g. 'trace' or 'pos_')")
    ap.add_argument("--skip-tests", default="", metavar="NAMES",
                    help="comma list of pgTAP file names (exact, e.g. foo.test.sql) to skip; each skip is printed "
                         "so it is explicit in the log. Use only for documented known failures.")
    args = ap.parse_args()

    if args.tap_batch_allowlist and (not args.tap or args.runner == 'pg_prove'):
        print('ERROR: --tap-batch-allowlist requires --tap and the psql runner.', file=sys.stderr)
        return 2

    extra_dirs_list = [Path(d).resolve() for d in args.extra_dir]
    if not extra_dirs_list and os.environ.get("DB_VERIFY_EXTRA_DIRS"):
        extra_dirs_list = [Path(d.strip()).resolve() for d in os.environ["DB_VERIFY_EXTRA_DIRS"].split(",") if d.strip()]

    batch_allowlist = set()
    if args.tap_batch_allowlist:
        try:
            repo = ROOT.parent.resolve()
            for line in Path(args.tap_batch_allowlist).read_text(encoding='utf-8-sig').splitlines():
                raw = line.strip()
                if not raw or raw.startswith('#'):
                    continue
                rel = Path(raw)
                if rel.is_absolute() or '..' in rel.parts or len(rel.parts) < 2:
                    raise ValueError(f'allowlist entry must be a project-relative path: {raw}')
                candidate = (repo / rel).resolve(strict=True)
                candidate.relative_to(repo)
                if not candidate.is_file() or not candidate.name.endswith('.test.sql'):
                    raise ValueError(f'not a pgTAP test file: {raw}')
                batch_allowlist.add(str(candidate))
            if not batch_allowlist:
                raise ValueError('allowlist has no test files')
        except (OSError, UnicodeError, ValueError) as exc:
            print(f'ERROR: invalid pgTAP batch allowlist: {exc}', file=sys.stderr)
            return 2


    prefix = shlex.split(args.psql, posix=(os.name != "nt")) if args.psql else ["psql"]
    if shutil.which(prefix[0]) is None:
        print(f"ERROR: '{prefix[0]}' not found in PATH. Install the PostgreSQL client or set EDOC_DB_PSQL.", file=sys.stderr)
        return 2
    psql = Psql(prefix)

    if args.gc:
        return gc_databases(psql, args.admin_db)

    # ONE test database: a fixed work db, reset from the template on every run. A custom/unique name used to leave
    # one database per agent and per killed run; any --db-name is now mapped to the work db (see RULE-ONE-TEST-DB).
    if args.db_name and args.db_name != WORK_DB:
        print(f"NOTE: --db-name {args.db_name} ignored: the single test database {WORK_DB} is used "
              f"(docs/RULE-ONE-TEST-DB.md).")
    db = WORK_DB
    if not db.startswith(DB_PREFIX) or db in PROTECTED:
        print(f"ERROR: refusing db name '{db}': must start with '{DB_PREFIX}'.", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[a-z0-9_]+", db):
        print("ERROR: db name must match [a-z0-9_]+", file=sys.stderr)
        return 2

    rep = Report(database=db)
    failures = 0

    def step(name: str, fn):
        t0 = time.time()
        r = fn()
        res = StepResult(name, r.returncode == 0, round(time.time() - t0, 2),
                         "" if r.returncode == 0 else first_error(r.stderr, r.stdout))
        rep.steps.append(res)
        return r, res

    # Template cache: applying ~1000 migrations dominates the run time, and `aidd verify` runs db_verify once
    # per Verification row. The built (pre-pgTAP) database is kept as a template named by a content hash.
    extra_plan = build_plan(extra_dirs_list)
    use_tpl = not args.no_template_cache and not args.apply_only and args.bootstrap != "never"
    h = hashlib.sha1(f"{args.bootstrap}|{args.single_tx}|{BOOTSTRAP_SQL}".encode("utf-8"))
    for kind, path in extra_plan:
        h.update(f"|{kind}|{path.name}|".encode("utf-8"))
        h.update(path.read_bytes())
    tpl = f"{DB_PREFIX}tpl_{h.hexdigest()[:16]}"
    cached = False
    if use_tpl:
        r = psql.run(args.admin_db, f"SELECT 1 FROM pg_database WHERE datname='{tpl}';", tuples=True)
        cached = r.returncode == 0 and r.stdout.strip() == "1"

    # Serialize runs on the shared work db (the OS drops the lock if the process is killed, so it never goes stale),
    # then reset it. FORCE also cleans what a previously killed run left behind.
    lock = acquire_lock(args.lock_wait)
    if lock is None:
        print(f"ERROR: another db_verify run kept the test database busy for {args.lock_wait} s.", file=sys.stderr)
        return 2
    current = hashlib.sha1(f"{args.bootstrap}|{args.single_tx}|{BOOTSTRAP_SQL}".encode("utf-8"))
    for kind, path in build_plan(extra_dirs_list):
        current.update(f"|{kind}|{path.name}|".encode("utf-8"))
        current.update(path.read_bytes())
    if current.hexdigest() != h.hexdigest():
        print('ERROR: database inputs changed while waiting for the lock; retry after the wave is stable.', file=sys.stderr)
        return 2
    if use_tpl:
        r = psql.run(args.admin_db, f"SELECT 1 FROM pg_database WHERE datname='{tpl}';", tuples=True)
        cached = r.returncode == 0 and r.stdout.strip() == "1"
    psql.run(args.admin_db, f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')

    print(f"== db_verify: test database {db}")
    r = psql.run(args.admin_db, f'CREATE DATABASE "{db}" TEMPLATE "{tpl}";' if cached else f'CREATE DATABASE "{db}";')
    if r.returncode != 0 and cached:
        print(f"NOTE: template {tpl} unusable ({first_error(r.stderr, r.stdout)}); building from scratch")
        cached = False
        r = psql.run(args.admin_db, f'CREATE DATABASE "{db}";')
    elif cached:
        touch_template(psql, args.admin_db, tpl)
    if r.returncode != 0:
        print(f"ERROR: cannot create database: {first_error(r.stderr, r.stdout)}", file=sys.stderr)
        return 2
    created = True

    try:
        psql.run(args.admin_db, f"ALTER DATABASE \"{db}\" SET search_path = public, extensions;")
        # Throwaway database: no need to wait for WAL flush on every commit.
        psql.run(args.admin_db, f"ALTER DATABASE \"{db}\" SET synchronous_commit = off;")
        # dblink-based tests (inventory/trace concurrency) need a TCP host when psql connects through a
        # unix socket (docker exec) and the password of the connecting role. `postgres` is not superuser
        # in the Supabase image, so ALTER DATABASE ... SET <custom guc> is denied; the values are set per
        # session instead (see tap_prefix) and prepended to every pgTAP file.
        # Loopback is `trust` in the Supabase image, and dblink refuses a password-less connection for a
        # non-superuser ("password is required"). In docker mode use the container's own bridge IP, which
        # pg_hba.conf covers with scram-sha-256 (password: PGPASSWORD or the Supabase local default in the tests).
        dblink_host = args.dblink_host or docker_container_ip(psql.prefix) or "127.0.0.1"
        tap_gucs = {"dblink_host": dblink_host}
        if os.environ.get("PGPASSWORD"):
            tap_gucs["dblink_password"] = os.environ["PGPASSWORD"]
        tap_prefix = "".join(f"SET {ns}.{k} = '{v.replace(chr(39), chr(39) * 2)}';\n"
                             for ns in ("inventory", "trace") for k, v in tap_gucs.items())
        if cached:
            print(f"[cache] cloned template {tpl}: bootstrap + migrations + seeds already applied")
            cached_failed = template_failed(psql, args.admin_db, tpl)
            if cached_failed:
                print(f"Failed files of the cached build (same as a fresh apply; {len(cached_failed)}):")
                for n, e in cached_failed:
                    print(f"  - {n}: {e}")
                failures += len(cached_failed)
        if args.bootstrap != "never" and not cached:
            r, res = step("bootstrap supabase shims", lambda: psql.run(db, BOOTSTRAP_SQL))
            print(f"[{'ok' if res.ok else 'FAIL'}] bootstrap shims {res.error}")
            if not res.ok:
                failures += 1

        # ---- apply
        plan = [] if cached else extra_plan
        failed_files: list[tuple[str, str]] = []
        batched = bool(plan) and not (args.exact_apply or args.single_tx or args.fail_fast)
        if batched:
            t_apply = time.time()
            failed_files = apply_batched(psql, db, plan, bool(extra_dirs_list))
            failures += len(failed_files)
            for n, e in failed_files:
                print(f"[FAIL] {n}  -> {e}")
            rep.steps.append(StepResult("apply (one psql session)", not failed_files,
                                        round(time.time() - t_apply, 2), ""))
            print(f"[ok]   applied {len(plan)} files in one session ({round(time.time() - t_apply, 1)}s)")
        for kind, path in ([] if batched else plan):
            sql = path.read_text(encoding="utf-8")
            display_name = str(path) if extra_dirs_list else path.name
            r, res = step(f"{kind} {display_name}",
                          lambda sql=sql: psql.run(db, sql, single_tx=args.single_tx))
            if res.ok:
                print(f"[ok]   {kind:9} {path.name}  ({res.seconds}s)")
            else:
                print(f"[FAIL] {kind:9} {path.name}  -> {res.error}")
                failed_files.append((f"{kind} {display_name}", res.error))
                failures += 1
                if args.fail_fast:
                    break
        print(f"\n== apply summary: {len(plan) - len(failed_files)}/{len(plan)} files ok")
        if failed_files:
            print("Failed files (later failures may cascade from earlier ones):")
            for n, e in failed_files:
                print(f"  - {n}: {e}")

        current = hashlib.sha1(f"{args.bootstrap}|{args.single_tx}|{BOOTSTRAP_SQL}".encode("utf-8"))
        for kind, path in build_plan(extra_dirs_list):
            current.update(f"|{kind}|{path.name}|".encode("utf-8"))
            current.update(path.read_bytes())
        if current.hexdigest() != h.hexdigest():
            print('ERROR: database inputs changed during setup; verification is invalid.', file=sys.stderr)
            failures += 1
        if use_tpl and not cached and not args.fail_fast and failures == len(failed_files):
            # No session is open on `db` between psql calls, so it can be the template source. A concurrent run
            # may win the race (CREATE then fails harmlessly). The database comment holds the last-use epoch;
            # only the TPL_KEEP most recently used templates are kept (different --extra-dir sets have own keys).
            for _attempt in range(3):
                # Supabase background workers can hold a session on any database: end them on OUR temp db
                # (never on another), then clone; retry because a worker may reconnect between the two calls.
                psql.run(args.admin_db, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                        f"WHERE datname = '{db}' AND pid <> pg_backend_pid();")
                r = psql.run(args.admin_db, f'CREATE DATABASE "{tpl}" TEMPLATE "{db}";')
                if r.returncode == 0:
                    break
                time.sleep(2)
            print(f"[cache] template {tpl} " + ("saved" if r.returncode == 0 else f"not saved ({first_error(r.stderr, r.stdout)})"))
            if r.returncode == 0:
                touch_template(psql, args.admin_db, tpl, [list(x) for x in failed_files])
                old = psql.run(args.admin_db,
                               f"SELECT datname FROM pg_database WHERE datname LIKE '{DB_PREFIX}tpl%' "
                               f"ORDER BY split_part(coalesce(shobj_description(oid,'pg_database'),'0'),'|',1)::numeric "
                               f"DESC OFFSET {TPL_KEEP};",
                               tuples=True).stdout.split()
                for o in old:
                    psql.run(args.admin_db, f'DROP DATABASE IF EXISTS "{o}" WITH (FORCE);')

        if not args.apply_only:
            # ---- pgTAP
            if args.tap:
                has_tap = psql.run(db, "SELECT 1 FROM pg_available_extensions WHERE name='pgtap';",
                                   tuples=True).stdout.strip() == "1"
                if not has_tap:
                    rep.notes.append("pgTAP extension not available: tests skipped")
                    print("NOTE: pgTAP extension not available; skipping tests")
                    failures += 1
                else:
                    psql.run(db, "CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;")
                    use_prove = (args.runner == "pg_prove" or
                                 (args.runner == "auto" and prefix == ["psql"] and shutil.which("pg_prove")))
                    if batch_allowlist:
                        use_prove = False
                    tests = sorted(TEST_DIR.glob("*.test.sql"))
                    if extra_dirs_list:
                        for ed in extra_dirs_list:
                            ed_tests_dir = ed / "supabase" / "tests" if (ed / "supabase" / "tests").exists() else ed / "tests"
                            if ed_tests_dir.exists():
                                tests.extend(sorted(ed_tests_dir.glob("*.test.sql"), key=sort_key))
                    discovered_files = {str(t.resolve()) for t in tests}
                    if batch_allowlist - discovered_files:
                        print('ERROR: batch allowlist includes files outside the selected test directories.', file=sys.stderr)
                        failures += 1
                        tests = []
                    if args.only_tests:
                        tests = [t for t in tests if args.only_tests in t.name]
                    skip = {n.strip() for n in args.skip_tests.split(",") if n.strip()}
                    for t in tests:
                        if t.name in skip:
                            print(f"[SKIP] {t.name} (explicit --skip-tests)")
                            rep.notes.append(f"pgTAP skipped explicitly: {t.name}")
                    tests = [t for t in tests if t.name not in skip]
                    print(f"\n== pgTAP: {len(tests)} files via {'pg_prove' if use_prove else 'psql'}")
                    if batch_allowlist:
                        eligible = sum(tap_batch_eligible(t, batch_allowlist) for t in tests)
                        print(f'== pgTAP batch candidates: {eligible}/{len(tests)}; other files remain isolated')
                    if not tests:
                        print('ERROR: pgTAP selected no test files.', file=sys.stderr)
                        failures += 1
                    batch_end, batch_items = 0, iter(())
                    for test_index, t in enumerate(tests):
                        if not use_prove and test_index >= batch_end and tap_batch_eligible(t, batch_allowlist):
                            batch_end = test_index
                            while batch_end < len(tests) and tap_batch_eligible(tests[batch_end], batch_allowlist):
                                batch_end += 1
                            batch_items = iter(run_tap_batch(psql, db, tests[test_index:batch_end],
                                                             tap_prefix, args.test_timeout, args.admin_db))
                        if use_prove:
                            p = subprocess.run(["pg_prove", "-d", db, str(t)], capture_output=True,
                                               text=True, encoding="utf-8", errors="replace")
                            out, rc = p.stdout + p.stderr, p.returncode
                            info = {"planned": None, "ok": 0, "not_ok": 0 if rc == 0 else 1,
                                    "failed": [] if rc == 0 else [first_error(out)]}
                        else:
                            try:
                                if test_index < batch_end:
                                    _, p, test_seconds = next(batch_items)
                                else:
                                    t_started = time.monotonic()
                                    p = psql.run(db, tap_prefix + t.read_text(encoding="utf-8"), tuples=True,
                                                 timeout=args.test_timeout)
                                    test_seconds = time.monotonic() - t_started
                            except subprocess.TimeoutExpired:
                                p = subprocess.CompletedProcess([], 124, "", f"ERROR: test timed out after {args.test_timeout}s")
                                test_seconds = args.test_timeout
                                # kill the orphaned server backend so it does not keep running
                                psql.run(args.admin_db, f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db}' AND pid <> pg_backend_pid();")
                            info = parse_tap(p.stdout)
                            info['seconds'] = round(test_seconds, 3)
                            rc = p.returncode
                            if rc != 0:
                                info["failed"].append("psql error: " + first_error(p.stderr, p.stdout))
                                info["not_ok"] += 1
                            elif info["planned"] is None or info["planned"] == 0:
                                info["failed"].append("missing or empty TAP plan")
                                info["not_ok"] += 1
                            elif info["planned"] != info["ok"] + info["not_ok"]:
                                info["failed"].append(f"plan mismatch: planned {info['planned']}, ran {info['ok'] + info['not_ok']}")
                                info["not_ok"] += 1
                        info["file"] = str(t) if extra_dirs_list else t.name
                        rep.tap.append(info)
                        good = info["not_ok"] == 0
                        elapsed = f" {info['seconds']:.3f}s" if 'seconds' in info else ''
                        print(f"[{'ok' if good else 'FAIL'}] {t.name}: ok={info['ok']} not_ok={info['not_ok']} planned={info['planned']}{elapsed}")
                        for f in info["failed"][:8]:
                            print(f"       {f}")
                        if not good:
                            failures += 1


            # ---- plpgsql_check
            if args.plpgsql_check:
                avail = psql.run(db, "SELECT 1 FROM pg_available_extensions WHERE name='plpgsql_check';",
                                 tuples=True).stdout.strip() == "1"
                if not avail:
                    rep.notes.append("plpgsql_check extension not available: static check skipped")
                    print("\nNOTE: plpgsql_check extension not available; skipping static check "
                          "(use an image with it, e.g. supabase/postgres)")
                else:
                    r = psql.run(db, "CREATE EXTENSION IF NOT EXISTS plpgsql_check WITH SCHEMA extensions;")
                    if r.returncode != 0:
                        print(f"NOTE: cannot create plpgsql_check: {first_error(r.stderr, r.stdout)}")
                        rep.notes.append("plpgsql_check create failed")
                    else:
                        schemas = ",".join(s.strip() for s in args.check_schemas.split(",") if s.strip())
                        if not re.fullmatch(r"[A-Za-z0-9_,]+", schemas):
                            print("ERROR: invalid --check-schemas", file=sys.stderr)
                            return 2
                        if args.only_functions:
                            pats = "|".join(re.escape(p.strip()) for p in args.only_functions.split(",") if p.strip())
                            fn_filter = f"AND p.proname ~* '({pats})'"
                        else:
                            fn_filter = ""
                        sql = PLPGSQL_CHECK_SQL.format(schemas=schemas,
                                                       warnings="true" if args.check_warnings else "false",
                                                       fn_filter=fn_filter)
                        r = psql.run(db, sql, tuples=True, stop_on_error=False)
                        rows = [ln.split("\t") for ln in r.stdout.splitlines() if ln.strip()]
                        if args.write_plpgsql_baseline:
                            out = [f"{row[0].strip()} | {row[3].strip() if len(row) > 3 else ''} | "
                                   for row in rows]
                            Path(args.write_plpgsql_baseline).write_text(
                                "\n".join(out) + ("\n" if out else ""), encoding="utf-8")
                            print(f"\n== plpgsql_check baseline written: {args.write_plpgsql_baseline} "
                                  f"({len(out)} entries)")
                        baseline_path = args.plpgsql_baseline
                        if baseline_path == "auto":
                            candidate = ROOT / "tools" / "plpgsql_check_baseline.txt"
                            baseline_path = str(candidate) if candidate.exists() else ""
                        baseline = load_plpgsql_baseline(baseline_path) if baseline_path else set()
                        new_rows = [row for row in rows if finding_key(row) not in baseline]
                        known = len(rows) - len(new_rows)
                        rep.plpgsql_check = {
                            "findings": rows,
                            "new": new_rows,
                            "baselined": known,
                            "baseline": baseline_path,
                            "stderr": first_error(r.stderr) if r.stderr.strip() else "",
                        }
                        print(f"\n== plpgsql_check: {len(rows)} finding(s) (schemas: {schemas}; "
                              f"{known} baselined, {len(new_rows)} new)")
                        for row in new_rows[:200]:
                            print("  - " + " | ".join(row))
                        if known and baseline_path:
                            print(f"  ({known} accepted finding(s) listed in {baseline_path})")
                        if r.stderr.strip():
                            print("  (psql stderr) " + first_error(r.stderr))
                        if (new_rows or r.stderr.strip()) and not args.no_check_gate:
                            failures += 1
        try:
            current = hashlib.sha1(f"{args.bootstrap}|{args.single_tx}|{BOOTSTRAP_SQL}".encode("utf-8"))
            for kind, path in build_plan(extra_dirs_list):
                current.update(f"|{kind}|{path.name}|".encode("utf-8"))
                current.update(path.read_bytes())
            if current.hexdigest() != h.hexdigest():
                print('ERROR: database inputs changed during tests; verification is invalid.', file=sys.stderr)
                failures += 1
        except OSError as exc:
            print(f'ERROR: database inputs unavailable after tests: {exc}', file=sys.stderr)
            failures += 1
    finally:
        if created and not args.keep_db:
            r = psql.run(args.admin_db, f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE);')
            if r.returncode != 0:
                print(f"WARNING: could not drop {db}: {first_error(r.stderr, r.stdout)}", file=sys.stderr)
            else:
                print(f"\n== dropped {db}")
        elif args.keep_db:
            print(f"\n== kept {db} (drop it manually)")

    if args.json:
        Path(args.json).write_text(json.dumps(asdict(rep), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n== RESULT: {'FAIL' if failures else 'OK'} ({failures} failing item(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
