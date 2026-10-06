#!/usr/bin/env python3
"""AIDD default DB-schema graph builder: SQL migrations -> node-link JSON (stdlib only, no database).

Usage:
    python sql_graph.py --root <project root> --out <graph .json> <migration dir or .sql file>...

Directories are scanned recursively for *.sql in natural order of their relative path; files that
do not decode are read with errors='replace'. Migrations are applied IN ORDER to an in-memory
model (CREATE/ALTER/DROP/COMMENT ...), so the FINAL schema state is what gets reported.
Output (deterministic, atomic): {"meta": {...counts, "coverage": {...}}, "nodes": [...], "edges": [...]}.

Node ids: db:<kind>:<name> (kind = table|view|column|function|index); column id db:column:<TABLE>.<COL>.
Edge relations: pertenece_a, fk, fk_col, idx_col, lee, escribe, lee_col, escribe_col, llama,
usa_col, dispara_trigger. Check constraints are not nodes. Any schema prefix is stripped.
Malformed statements are skipped (never raise) and counted in meta.skipped_statements.
Public API: build_graph(root, paths) -> dict.  Exit codes: 0 ok, 2 bad arguments.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ID = r'(?:"[^"]+"|[A-Za-z_][\w$]*)'
QID = rf'{ID}(?:\s*\.\s*{ID})*'
CONSTRAINT_KW = r'NOT\s+NULL|NULL|DEFAULT|PRIMARY\s+KEY|REFERENCES|UNIQUE|CHECK|CONSTRAINT|GENERATED|COLLATE'
ALIAS_STOP = set("""WHERE ON SET JOIN LEFT RIGHT INNER OUTER FULL CROSS GROUP ORDER LIMIT HAVING UNION USING
VALUES SELECT RETURNING INTO WHEN THEN AND OR FOR NATURAL WINDOW OFFSET FETCH EXCEPT INTERSECT LOOP END IF
ELSE BEGIN RETURN AS WITH""".split())
FLAGS = re.I | re.S


# ---------------------------------------------------------------- lexical helpers
def unq(s):
    s = s.strip()
    return s[1:-1] if len(s) > 1 and s[0] == '"' and s[-1] == '"' else s


def norm(qid):
    """Qualified identifier -> bare name (schema dropped, quotes removed)."""
    parts = [unq(p) for p in re.findall(ID, qid)]
    return parts[-1] if parts else qid.strip()


def split_statements(text):
    """-> [(statement text with comments blanked, 1-based start line)]; respects quotes and $tag$ bodies."""
    out, buf, i, n, line, start = [], [], 0, len(text), 1, None

    def put(piece):
        nonlocal line, start
        if start is None and piece.strip():
            start = line + (len(piece) - len(piece.lstrip())) * 0 + piece[:len(piece) - len(piece.lstrip())].count("\n")
        buf.append(piece)
        line += piece.count("\n")

    def flush():
        nonlocal buf, start
        s = "".join(buf).strip()
        if s and start is not None:
            out.append((s, start))
        buf, start = [], None

    dollar = re.compile(r'\$([A-Za-z_]\w*)?\$')
    while i < n:
        c = text[i]
        if text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            put(" ")
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            put(" " + "\n" * text.count("\n", i, j))
            i = j
        elif c in "'\"":
            j = i + 1
            while j < n:
                if text[j] == c:
                    if j + 1 < n and text[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            put(text[i:j + 1])
            i = j + 1
        elif c == "$" and (m := dollar.match(text, i)):
            tag = m.group(0)
            j = text.find(tag, m.end())
            j = n if j < 0 else j + len(tag)
            put(text[i:j])
            i = j
        elif c == ";":
            flush()
            i += 1
        else:
            put(c)
            i += 1
    flush()
    return out


def blank(s):
    """Drop comments and empty string literals (keeps length-insensitive structure) for analysis."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s.startswith("--", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
        elif s[i] == "'":
            j = i + 1
            while j < n:
                if s[j] == "'":
                    if j + 1 < n and s[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            out.append("''")
            i = j + 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def find_close(s, open_idx):
    depth, i, n = 0, open_idx, len(s)
    while i < n:
        c = s[i]
        if c in "'\"":
            j = s.find(c, i + 1)
            if j < 0:
                break
            i = j
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced parentheses")


def split_top(s):
    """Split on top-level commas (outside parens and quotes)."""
    parts, depth, cur, i, n = [], 0, [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "'\"":
            j = s.find(c, i + 1)
            j = n - 1 if j < 0 else j
            cur.append(s[i:j + 1])
            i = j + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    last = "".join(cur).strip()
    if last:
        parts.append(last)
    return parts


def id_list(s):
    return [unq(x).lower() for x in re.findall(ID, s)]


def natural_key(s):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


# ---------------------------------------------------------------- column / constraint parsing
def parse_column_def(text):
    m = re.match(rf"\s*({ID})\s*(.*)$", text, FLAGS)
    if not m:
        raise ValueError("bad column definition")
    name, rest = unq(m.group(1)), m.group(2)
    tm = re.match(rf"(.*?)(?=(?:^|\s)(?:{CONSTRAINT_KW})\b|$)", rest, FLAGS)
    ctype = tm.group(1).strip() or None
    tail = rest[tm.end():]
    col = {"name": name, "type": ctype, "nullable": True, "default": None, "comment": None}
    dm = re.search(rf"\bDEFAULT\s+(.+?)(?=\s+(?:{CONSTRAINT_KW.replace('DEFAULT|', '')})\b|$)", tail, FLAGS)
    if dm:
        col["default"] = dm.group(1).strip()
    if re.search(r"\bNOT\s+NULL\b", tail, re.I):
        col["nullable"] = False
    pk = bool(re.search(r"\bPRIMARY\s+KEY\b", tail, re.I))
    if pk:
        col["nullable"] = False
    fk = None
    rm = re.search(rf"\bREFERENCES\s+({QID})\s*(?:\(([^)]*)\))?", tail, re.I)
    if rm:
        fk = {"cols": [name.lower()], "ref_table": norm(rm.group(1)).lower(),
              "ref_cols": id_list(rm.group(2) or "")}
    return col, pk, fk


class Model:
    def __init__(self, root):
        self.root = Path(root)
        self.tables, self.views, self.funcs, self.indexes, self.triggers = {}, {}, {}, {}, {}
        self.skipped = 0
        self.files = []
        self.file = ""
        self.line = 0

    # -- statement dispatch
    def apply_file(self, rel, text):
        self.files.append(rel)
        self.file = rel
        for stmt, line in split_statements(text):
            self.line = line
            handler = self._route(stmt)
            if handler is None:
                continue
            try:
                handler(stmt)
            except Exception:  # malformed SQL must never abort the build
                self.skipped += 1

    def _route(self, s):
        routes = [
            (r"CREATE\s+(?:\w+\s+){0,3}?TABLE\b", self.create_table),
            (r"ALTER\s+TABLE\b", self.alter_table),
            (r"DROP\s+(?:TABLE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|PROCEDURE|INDEX|TRIGGER)\b", self.drop),
            (r"COMMENT\s+ON\b", self.comment_on),
            (r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:TEMP|TEMPORARY|RECURSIVE|MATERIALIZED)\s+)?VIEW\b", self.create_view),
            (r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\b", self.create_function),
            (r"CREATE\s+(?:UNIQUE\s+)?INDEX\b", self.create_index),
            (r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:CONSTRAINT\s+)?TRIGGER\b", self.create_trigger),
        ]
        for pat, fn in routes:
            if re.match(pat, s, re.I):
                return fn
        return None

    # -- helpers
    def tbl(self, qid):
        t = self.tables.get(norm(qid).lower())
        if t is None:
            raise ValueError("unknown table")
        return t

    def _add_column(self, t, text):
        col, pk, fk = parse_column_def(text)
        col["file"], col["line"] = self.file, self.line
        key = col["name"].lower()
        old = t["cols"].get(key)
        if old and old.get("comment"):
            col["comment"] = old["comment"]
        t["cols"][key] = col
        if pk and key not in t["pk"]:
            t["pk"].append(key)
        if fk:
            t["fks"].append(fk)

    def _table_constraint(self, t, text):
        text = re.sub(rf"^\s*CONSTRAINT\s+{ID}\s+", "", text, flags=re.I)
        m = re.match(r"PRIMARY\s+KEY\s*\(([^)]*)\)", text, re.I)
        if m:
            t["pk"] = id_list(m.group(1))
            for k in t["pk"]:
                if k in t["cols"]:
                    t["cols"][k]["nullable"] = False
            return
        m = re.match(rf"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+({QID})\s*(?:\(([^)]*)\))?", text, re.I)
        if m:
            t["fks"].append({"cols": id_list(m.group(1)), "ref_table": norm(m.group(2)).lower(),
                             "ref_cols": id_list(m.group(3) or "")})

    # -- CREATE TABLE
    def create_table(self, s):
        m = re.match(rf"CREATE\s+(?:(?:GLOBAL\s+|LOCAL\s+)?(?:TEMP|TEMPORARY)\s+|UNLOGGED\s+)?TABLE\s+"
                     rf"(?:IF\s+NOT\s+EXISTS\s+)?({QID})\s*\(", s, re.I)
        if not m:
            raise ValueError("unsupported CREATE TABLE")
        name = norm(m.group(1))
        body = s[m.end():find_close(s, m.end() - 1)]
        t = {"name": name, "cols": {}, "pk": [], "fks": [], "comment": None, "file": self.file, "line": self.line}
        for item in split_top(body):
            if re.match(r"(?:CONSTRAINT\s|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE\s*\(|CHECK\s*\(|EXCLUDE\b|LIKE\b)", item, re.I):
                self._table_constraint(t, item)
            else:
                self._add_column(t, item)
        if name.lower() in self.tables and re.search(r"IF\s+NOT\s+EXISTS", s[:m.end()], re.I):
            return
        self.tables[name.lower()] = t

    # -- ALTER TABLE
    def alter_table(self, s):
        m = re.match(rf"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?({QID})\s+(.*)$", s, FLAGS)
        if not m:
            raise ValueError("bad ALTER TABLE")
        t = self.tbl(m.group(1))
        for act in split_top(m.group(2)):
            self._alter_action(t, act)

    def _alter_action(self, t, a):
        m = re.match(r"RENAME\s+TO\s+(\S+)", a, re.I)
        if m:
            return self._rename_table(t, norm(m.group(1)))
        m = re.match(rf"RENAME\s+(?:COLUMN\s+)?({ID})\s+TO\s+({ID})", a, re.I)
        if m and not re.match(r"RENAME\s+CONSTRAINT", a, re.I):
            return self._rename_column(t, unq(m.group(1)), unq(m.group(2)))
        if re.match(r"ADD\s+(?:CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|EXCLUDE)\b", a, re.I):
            return self._table_constraint(t, re.sub(r"^ADD\s+", "", a, flags=re.I))
        m = re.match(r"ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(.*)$", a, FLAGS)
        if m:
            return self._add_column(t, m.group(1))
        m = re.match(rf"DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?({ID})", a, re.I)
        if m:
            k = unq(m.group(1)).lower()
            t["cols"].pop(k, None)
            t["pk"] = [x for x in t["pk"] if x != k]
            t["fks"] = [f for f in t["fks"] if k not in f["cols"]]
            for ix in self.indexes.values():
                if ix["table"] == t["name"].lower():
                    ix["cols"] = [c for c in ix["cols"] if c != k]
            return None
        m = re.match(rf"ALTER\s+(?:COLUMN\s+)?({ID})\s+(.*)$", a, FLAGS)
        if m:
            col = t["cols"].get(unq(m.group(1)).lower())
            if col is None:
                raise ValueError("unknown column")
            r = m.group(2).strip()
            if re.match(r"SET\s+NOT\s+NULL", r, re.I):
                col["nullable"] = False
            elif re.match(r"DROP\s+NOT\s+NULL", r, re.I):
                col["nullable"] = True
            elif re.match(r"DROP\s+DEFAULT", r, re.I):
                col["default"] = None
            elif re.match(r"SET\s+DEFAULT\s+", r, re.I):
                col["default"] = re.sub(r"^SET\s+DEFAULT\s+", "", r, flags=re.I).strip()
            elif re.match(r"(?:SET\s+DATA\s+)?TYPE\s+", r, re.I):
                ty = re.sub(r"^(?:SET\s+DATA\s+)?TYPE\s+", "", r, flags=re.I)
                col["type"] = re.split(r"\s+USING\b", ty, flags=re.I)[0].strip()
            else:
                new, _, _ = parse_column_def(f"{col['name']} {r}")
                col["type"] = new["type"] or col["type"]
                col["nullable"] = new["nullable"]
        return None

    def _rename_table(self, t, new):
        old = t["name"].lower()
        if new.lower() in self.tables:
            raise ValueError("target exists")
        del self.tables[old]
        t["name"] = new
        self.tables[new.lower()] = t
        for o in self.tables.values():
            for f in o["fks"]:
                if f["ref_table"] == old:
                    f["ref_table"] = new.lower()
        for ix in self.indexes.values():
            if ix["table"] == old:
                ix["table"] = new.lower()
        self.triggers = {(new.lower() if k[0] == old else k[0], k[1]): dict(v, table=new.lower()
                         if v["table"] == old else v["table"]) for k, v in self.triggers.items()}

    def _rename_column(self, t, a, b):
        ka, kb = a.lower(), b.lower()
        col = t["cols"].pop(ka, None)
        if col is None:
            raise ValueError("unknown column")
        col["name"] = b
        t["cols"][kb] = col
        t["pk"] = [kb if x == ka else x for x in t["pk"]]
        me = t["name"].lower()
        for o in self.tables.values():
            for f in o["fks"]:
                if o is t:
                    f["cols"] = [kb if x == ka else x for x in f["cols"]]
                if f["ref_table"] == me:
                    f["ref_cols"] = [kb if x == ka else x for x in f["ref_cols"]]
        for ix in self.indexes.values():
            if ix["table"] == me:
                ix["cols"] = [kb if x == ka else x for x in ix["cols"]]

    # -- DROP
    def drop(self, s):
        m = re.match(r"DROP\s+(MATERIALIZED\s+VIEW|TABLE|VIEW|FUNCTION|PROCEDURE|INDEX|TRIGGER)\s+"
                     r"(?:CONCURRENTLY\s+)?(?:IF\s+EXISTS\s+)?(.*?)(?:\s+(?:CASCADE|RESTRICT))?\s*$", s, FLAGS)
        if not m:
            raise ValueError("bad DROP")
        kind, rest = m.group(1).upper().split()[-1], m.group(2)
        if kind == "TRIGGER":
            mt = re.match(rf"({ID})\s+ON\s+({QID})", rest, re.I)
            if mt:
                self.triggers.pop((norm(mt.group(2)).lower(), unq(mt.group(1)).lower()), None)
            return
        for item in split_top(rest):
            if kind in ("FUNCTION", "PROCEDURE"):
                self._drop_function(item)
                continue
            key = norm(item).lower()
            if kind == "TABLE":
                self.tables.pop(key, None)
                self.indexes = {k: v for k, v in self.indexes.items() if v["table"] != key}
                self.triggers = {k: v for k, v in self.triggers.items() if k[0] != key}
            elif kind == "VIEW":
                self.views.pop(key, None)
            else:
                self.indexes.pop(key, None)

    def _drop_function(self, item):
        m = re.match(rf"({QID})\s*(?:\((.*)\))?\s*$", item, FLAGS)
        if not m:
            raise ValueError("bad function ref")
        key = norm(m.group(1)).lower()
        f = self.funcs.get(key)
        if f is None:
            return
        if m.group(2) is None:
            del self.funcs[key]
            return
        sig = re.sub(r"\s+", " ", m.group(2)).strip().lower()
        f["overloads"] = [o for o in f["overloads"] if re.sub(r"\s+", " ", o["args"]).strip().lower() != sig]
        if not f["overloads"]:
            del self.funcs[key]

    # -- COMMENT ON
    def comment_on(self, s):
        m = re.match(r"COMMENT\s+ON\s+(TABLE|VIEW|MATERIALIZED\s+VIEW|COLUMN|FUNCTION|PROCEDURE)\s+(.+?)\s+IS\s+"
                     r"(NULL|'(?:[^']|'')*')\s*$", s, FLAGS)
        if not m:
            raise ValueError("bad COMMENT")
        kind, target, lit = m.group(1).upper().split()[-1], m.group(2), m.group(3)
        text = None if lit.upper() == "NULL" else lit[1:-1].replace("''", "'")
        if kind == "TABLE":
            self.tbl(target)["comment"] = text
        elif kind == "VIEW":
            v = self.views.get(norm(target).lower())
            if v is not None:
                v["comment"] = text
        elif kind == "COLUMN":
            parts = re.findall(ID, target)
            if len(parts) < 2:
                raise ValueError("bad column ref")
            t = self.tables.get(unq(parts[-2]).lower())
            if t is None:
                if unq(parts[-2]).lower() in self.views:
                    return
                raise ValueError("unknown table")
            c = t["cols"].get(unq(parts[-1]).lower())
            if c is None:
                raise ValueError("unknown column")
            c["comment"] = text
        else:
            f = self.funcs.get(norm(target.split("(")[0]).lower())
            if f is None:
                raise ValueError("unknown function")
            f["comment"] = text

    # -- views / functions / indexes / triggers
    def create_view(self, s):
        m = re.match(rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:TEMP|TEMPORARY|RECURSIVE|MATERIALIZED)\s+)?VIEW\s+"
                     rf"(?:IF\s+NOT\s+EXISTS\s+)?({QID})\s*(?:\([^)]*\))?\s*(?:WITH\s*\([^)]*\)\s*)?AS\s+(.*)$", s, FLAGS)
        if not m:
            raise ValueError("bad CREATE VIEW")
        name = norm(m.group(1))
        old = self.views.get(name.lower())
        self.views[name.lower()] = {"name": name, "sql": m.group(2), "file": self.file, "line": self.line,
                                    "comment": old["comment"] if old else None}

    def create_function(self, s):
        m = re.match(rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+({QID})\s*\(", s, FLAGS)
        if not m:
            raise ValueError("bad CREATE FUNCTION")
        end = find_close(s, m.end() - 1)
        args, rest = s[m.end():end].strip(), s[end + 1:]
        bm = re.search(r"\$([A-Za-z_]\w*)?\$(.*?)\$\1\$", rest, re.S) if "$" in rest else None
        if bm:
            body = bm.group(2)
        else:
            qm = re.search(r"\bAS\s+'((?:[^']|'')*)'", rest, FLAGS)
            body = qm.group(1).replace("''", "'") if qm else rest
        lm = re.search(r"\bLANGUAGE\s+'?(\w+)'?", rest, re.I)
        name = norm(m.group(1))
        f = self.funcs.setdefault(name.lower(), {"name": name, "overloads": [], "comment": None})
        sig = re.sub(r"\s+", " ", args).strip().lower()
        f["overloads"] = [o for o in f["overloads"] if re.sub(r"\s+", " ", o["args"]).strip().lower() != sig]
        f["overloads"].append({"args": re.sub(r"\s+", " ", args).strip(), "body": body,
                               "language": lm.group(1).lower() if lm else None})
        f["file"], f["line"] = self.file, self.line

    def create_index(self, s):
        m = re.match(rf"CREATE\s+(UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
                     rf"(?:({ID})\s+)?ON\s+(?:ONLY\s+)?({QID})\s*(?:USING\s+\w+\s*)?\(", s, FLAGS)
        if not m:
            raise ValueError("bad CREATE INDEX")
        table = norm(m.group(3)).lower()
        body = s[m.end():find_close(s, m.end() - 1)]
        cols = []
        for item in split_top(body):
            im = re.match(rf"\s*({ID})\s*(?:ASC|DESC|NULLS|COLLATE|\w+_ops|$)?", item, re.I)
            if im and not item.strip().startswith("("):
                cols.append(unq(im.group(1)).lower())
        name = unq(m.group(2)) if m.group(2) else f"{table}_{'_'.join(cols)}_idx"
        self.indexes[name.lower()] = {"name": name, "table": table, "cols": cols, "unique": bool(m.group(1)),
                                      "file": self.file, "line": self.line}

    def create_trigger(self, s):
        m = re.match(rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:CONSTRAINT\s+)?TRIGGER\s+({ID})\s+.*?\bON\s+({QID})"
                     rf".*?\bEXECUTE\s+(?:FUNCTION|PROCEDURE)\s+({QID})\s*\(", s, FLAGS)
        if not m:
            raise ValueError("bad CREATE TRIGGER")
        table = norm(m.group(2)).lower()
        self.triggers[(table, unq(m.group(1)).lower())] = {"name": unq(m.group(1)), "table": table,
                                                            "func": norm(m.group(3)).lower()}


# ---------------------------------------------------------------- body / view analysis
def _blank_spans(s, spans):
    chars = list(s)
    for a, b in spans:
        for k in range(a, b):
            chars[k] = " "
    return "".join(chars)


def analyze_sql(model, text):
    """-> dict(tables={name: ops}, views=set, col_reads=set((t,c)), col_writes=set((t,c)), dynamic=bool)."""
    clean = blank(text)
    res = {"tables": {}, "views": set(), "col_reads": set(), "col_writes": set(),
           "dynamic": bool(re.search(r"\bEXECUTE\b(?!\s+(?:FUNCTION|PROCEDURE))|\bEXEC\s*\(|\bsp_executesql\b",
                                     clean, re.I))}
    alias_re = rf"(?:\s+(?:AS\s+)?({ID}))?"

    def known(qid):
        k = norm(qid).lower()
        return k if (k in model.tables or k in model.views) else None

    def alias_of(g):
        return g.lower() if g and unq(g).upper() not in ALIAS_STOP else None

    for stmt in clean.split(";"):
        refs, spans, writes = [], [], {}  # refs: (key, alias, op)
        del_starts = set()
        for rx, op in ((rf"\bINSERT\s+INTO\s+({QID})", "INSERT"),
                       (rf"\bUPDATE\s+(?:ONLY\s+)?({QID}){alias_re}(?=\s+SET\b)", "UPDATE"),
                       (rf"\bDELETE\s+FROM\s+(?:ONLY\s+)?({QID}){alias_re}", "DELETE"),
                       (rf"\bMERGE\s+INTO\s+({QID}){alias_re}", "UPDATE")):
            for m in re.finditer(rx, stmt, re.I):
                k = known(m.group(1))
                if op == "DELETE":
                    del_starts.add(m.start(1))
                if k:
                    refs.append((k, alias_of(m.group(2)) if m.lastindex and m.lastindex >= 2 else None, op))
                    writes[k] = op
                    spans.append(m.span(1))
        for m in re.finditer(rf"\b(?:FROM|JOIN|USING)\s+(?:ONLY\s+)?({QID}){alias_re}", stmt, re.I):
            if m.start(1) in del_starts:
                continue
            k = known(m.group(1))
            if k:
                refs.append((k, alias_of(m.group(2)), "SELECT"))
                spans.append(m.span(1))
            pos = m.end()
            while True:  # FROM a x, b y
                cm = re.compile(rf"\s*,\s*({QID}){alias_re}", re.I).match(stmt, pos)
                if not cm:
                    break
                k2 = known(cm.group(1))
                if k2:
                    refs.append((k2, alias_of(cm.group(2)), "SELECT"))
                    spans.append(cm.span(1))
                pos = cm.end()
        for k, _, op in refs:
            if k in model.tables or k in model.views:
                if k in model.views:
                    res["views"].add(k)
                else:
                    res["tables"].setdefault(k, set()).add(op)
        tabs = {}
        for k, al, _ in refs:
            if k in model.tables:
                tabs[k] = k
                if al:
                    tabs[al] = k
        if not tabs:
            continue
        work = _blank_spans(stmt, spans)
        # write columns
        wspans = []
        for m in re.finditer(rf"\bINSERT\s+INTO\s+({QID})\s*\(([^()]*)\)", stmt, re.I):
            k = known(m.group(1))
            if k in model.tables:
                wspans.append(m.span(2))
                for c in id_list(m.group(2)):
                    if c in model.tables[k]["cols"]:
                        res["col_writes"].add((k, c))
        sm = re.search(r"\bSET\b(.*?)(?=\bWHERE\b|\bFROM\b|\bRETURNING\b|$)", stmt, FLAGS)
        if sm and re.search(r"\bUPDATE\b", stmt, re.I):
            targets = [k for k, _, op in refs if op == "UPDATE"]
            for m in re.finditer(rf"(?:^|,)\s*(?:{ID}\s*\.\s*)?({ID})\s*=(?!=)", sm.group(1)):
                c = unq(m.group(1)).lower()
                for k in targets:
                    if c in model.tables[k]["cols"]:
                        res["col_writes"].add((k, c))
                        wspans.append((sm.start(1) + m.start(1), sm.start(1) + m.end(1)))
        work = _blank_spans(work, wspans)
        # qualified alias.col
        qspans = []
        for m in re.finditer(rf"(?<![\w.])({ID})\s*\.\s*({ID})", work):
            q, c = unq(m.group(1)).lower(), unq(m.group(2)).lower()
            k = tabs.get(q)
            if k and c in model.tables[k]["cols"]:
                res["col_reads"].add((k, c))
            qspans.append(m.span())
        work = _blank_spans(work, qspans)
        # unqualified: only when exactly one referenced table owns the column
        for m in re.finditer(rf"(?<![\w.$:@])({ID})(?![\w.(])", work):
            c = unq(m.group(1)).lower()
            owners = {k for k in set(tabs.values()) if c in model.tables[k]["cols"]}
            if len(owners) == 1:
                res["col_reads"].add((next(iter(owners)), c))
    return res


# ---------------------------------------------------------------- purpose rules
def infer_purpose(model, table, col, key, is_fk, fk_target):
    """-> (purpose, source). COMMENT ON wins; otherwise deterministic name/type rules."""
    if col.get("comment"):
        return col["comment"], "comment"
    if fk_target:
        return f"Reference to {fk_target}", "inferred_rule"
    name = col["name"]
    low = name.lower().replace("_", "")
    ctype = (col.get("type") or "").lower()
    if low == "id" or (key in table["pk"] and low.endswith("id") and len(table["pk"]) == 1):
        return "Primary identifier of the record", "inferred_rule"
    if re.search(r"[a-z]Id$", name) or name.lower().endswith("_id"):
        stem = re.sub(r"(_?[iI]d)$", "", name).lower().replace("_", "")
        for tk, t in model.tables.items():
            if tk.replace("_", "") in (stem, stem + "s"):
                return f"Identifier of the related {t['name']} entity", "inferred_rule"
        return "Identifier/reference of another entity", "inferred_rule"
    rules = [
        (lambda: low.endswith("code"), "Code identifying the entity"),
        (lambda: low in ("createdate", "createdat", "createdon", "createddate", "creationdate"), "Creation timestamp of the record"),
        (lambda: low in ("updatedate", "updatedat", "updatedon", "updateddate", "modifieddate", "lastupdate"), "Last update timestamp of the record"),
        (lambda: low in ("recordstate", "status", "state"), "Record state/status"),
        (lambda: low.endswith(("amt", "amount")) or low in ("total", "price") or low.endswith("price"), "Monetary amount"),
        (lambda: low.endswith(("qty", "quantity")), "Quantity"),
        (lambda: low.endswith(("pct", "percent", "percentage")), "Percentage"),
        (lambda: name.lower().startswith(("is_", "has_")) or ctype.startswith(("bool", "bit")),
         "Boolean flag: " + re.sub(r"^(is|has)_?", "", name, flags=re.I).replace("_", " ")),
    ]
    for test, text in rules:
        if test():
            return text, "inferred_rule"
    return None, "none"


# ---------------------------------------------------------------- graph assembly
def _collect(root, paths):
    out, seen = [], set()
    for p in paths:
        p = Path(p)
        if not p.is_absolute():
            p = Path.cwd() / p
        if p.is_dir():
            found = sorted((f for f in p.rglob("*.sql") if f.is_file()),
                           key=lambda f: natural_key(f.relative_to(p).as_posix()))
        elif p.is_file():
            found = [p]
        else:
            raise FileNotFoundError(str(p))
        for f in found:
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def _rel(root, f):
    try:
        return Path(f).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(f).as_posix()


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def build_graph(root, paths):
    root = Path(root)
    model = Model(root)
    for f in _collect(root, paths):
        model.apply_file(_rel(root, f), f.read_bytes().decode("utf-8", errors="replace"))
    nodes, edges = {}, set()

    def node(nid, **kw):
        nodes[nid] = {k: v for k, v in dict(id=nid, **kw).items() if v is not None}

    def edge(src, tgt, rel, conf, op=None):
        edges.add((src, tgt, rel, conf, op or ""))

    def tid(k):
        return f"db:table:{model.tables[k]['name']}"

    fk_cols = {}
    for tk, t in model.tables.items():
        for f in t["fks"]:
            ref = model.tables.get(f["ref_table"])
            for i, c in enumerate(f["cols"]):
                rc = f["ref_cols"][i] if i < len(f["ref_cols"]) else (ref["pk"][i] if ref and i < len(ref["pk"]) else None)
                fk_cols[(tk, c)] = (f["ref_table"], rc)
    ncols = npurp = 0
    for tk, t in sorted(model.tables.items()):
        node(tid(tk), label=t["name"], type="table", name=t["name"], source_file=t["file"],
             source_location=str(t["line"]), comment=t["comment"], purpose=t["comment"],
             purpose_source="comment" if t["comment"] else "none")
    for vk, v in sorted(model.views.items()):
        node(f"db:view:{v['name']}", label=v["name"], type="view", name=v["name"], source_file=v["file"],
             source_location=str(v["line"]), comment=v["comment"], purpose=v["comment"],
             purpose_source="comment" if v["comment"] else "none")
    for tk, t in sorted(model.tables.items()):
        for ck, c in t["cols"].items():
            ref = fk_cols.get((tk, ck))
            target = None
            if ref:
                rt = model.tables.get(ref[0])
                target = f"{rt['name'] if rt else ref[0]}" + (
                    f".{rt['cols'][ref[1]]['name'] if rt and ref[1] in rt['cols'] else ref[1]}" if ref[1] else "")
            purpose, src = infer_purpose(model, t, c, ck, bool(ref), target)
            ncols += 1
            npurp += src != "none"
            nid = f"db:column:{t['name']}.{c['name']}"
            node(nid, label=f"{t['name']}.{c['name']}", type="column", table=t["name"], name=c["name"],
                 data_type=c["type"], nullable=c["nullable"], is_pk=ck in t["pk"], is_fk=bool(ref),
                 default=c["default"], purpose=purpose, purpose_source=src, comment=c["comment"],
                 source_file=c["file"], source_location=str(c["line"]))
            edge(nid, tid(tk), "pertenece_a", "EXTRACTED")
            if ref:
                edge(tid(tk), f"db:table:{model.tables[ref[0]]['name']}" if ref[0] in model.tables else "", "fk", "EXTRACTED")
                if ref[0] in model.tables and ref[1] in model.tables[ref[0]]["cols"]:
                    rt = model.tables[ref[0]]
                    edge(nid, f"db:column:{rt['name']}.{rt['cols'][ref[1]]['name']}", "fk_col", "EXTRACTED")
    for ix in sorted(model.indexes.values(), key=lambda i: i["name"]):
        if ix["table"] not in model.tables:
            continue
        t = model.tables[ix["table"]]
        iid = f"db:index:{ix['name']}"
        node(iid, label=ix["name"], type="index", name=ix["name"], table=t["name"], unique=ix["unique"],
             source_file=ix["file"], source_location=str(ix["line"]))
        edge(iid, tid(ix["table"]), "pertenece_a", "EXTRACTED")
        for c in ix["cols"]:
            if c in t["cols"]:
                edge(iid, f"db:column:{t['name']}.{t['cols'][c]['name']}", "idx_col", "EXTRACTED")
    # functions
    nfunc = nan = 0
    for fk_, f in sorted(model.funcs.items()):
        res = {"tables": {}, "views": set(), "col_reads": set(), "col_writes": set(), "dynamic": False}
        for o in f["overloads"]:
            r = analyze_sql(model, o["body"])
            for k, ops in r["tables"].items():
                res["tables"].setdefault(k, set()).update(ops)
            res["views"] |= r["views"]
            res["col_reads"] |= r["col_reads"]
            res["col_writes"] |= r["col_writes"]
            res["dynamic"] |= r["dynamic"]
        langs = sorted({o["language"] for o in f["overloads"] if o["language"]})
        nid = f"db:function:{f['name']}"
        node(nid, label=f["name"], type="function", name=f["name"], language=langs[0] if langs else None,
             signatures=sorted(o["args"] for o in f["overloads"]), analyzed=not res["dynamic"],
             analysis_reason="dynamic SQL (EXECUTE)" if res["dynamic"] else None, comment=f["comment"],
             purpose=f["comment"], purpose_source="comment" if f["comment"] else "none",
             source_file=f.get("file"), source_location=str(f.get("line", "")) or None)
        nfunc += 1
        nan += not res["dynamic"]
    for fk_, f in sorted(model.funcs.items()):
        nid = f"db:function:{f['name']}"
        res = {"tables": {}, "views": set(), "col_reads": set(), "col_writes": set()}
        called = set()
        for o in f["overloads"]:
            r = analyze_sql(model, o["body"])
            for k, ops in r["tables"].items():
                res["tables"].setdefault(k, set()).update(ops)
            res["views"] |= r["views"]
            res["col_reads"] |= r["col_reads"]
            res["col_writes"] |= r["col_writes"]
            for m in re.finditer(rf"\b({ID})\s*\(", blank(o["body"])):
                n = unq(m.group(1)).lower()
                if n in model.funcs and n != fk_:
                    called.add(n)
        for k, ops in res["tables"].items():
            for op in ops:
                edge(nid, tid(k), "escribe" if op != "SELECT" else "lee", "EXTRACTED", op)
        for k in res["views"]:
            edge(nid, f"db:view:{model.views[k]['name']}", "lee", "EXTRACTED", "SELECT")
        for rel, cols in (("lee_col", res["col_reads"]), ("escribe_col", res["col_writes"])):
            for k, c in cols:
                t = model.tables[k]
                edge(nid, f"db:column:{t['name']}.{t['cols'][c]['name']}", rel, "INFERRED")
        for n in called:
            edge(nid, f"db:function:{model.funcs[n]['name']}", "llama", "INFERRED")
    for vk, v in model.views.items():
        r = analyze_sql(model, v["sql"])
        for k, c in r["col_reads"]:
            t = model.tables[k]
            edge(f"db:view:{v['name']}", f"db:column:{t['name']}.{t['cols'][c]['name']}", "usa_col", "INFERRED")
    for (tk, _), tr in sorted(model.triggers.items()):
        if tk in model.tables and tr["func"] in model.funcs:
            edge(tid(tk), f"db:function:{model.funcs[tr['func']]['name']}", "dispara_trigger", "EXTRACTED")
    edges = {e for e in edges if e[0] in nodes and e[1] in nodes}
    edge_list = [{"source": s, "target": t, "relation": r, "confidence": c, **({"op": op} if op else {})}
                 for s, t, r, c, op in sorted(edges)]
    counts = {k: sum(1 for n in nodes.values() if n["type"] == k)
              for k in ("table", "view", "column", "function", "index")}
    meta = {"kind": "db-schema", "files": sorted(model.files), "tables": counts["table"], "views": counts["view"],
            "columns": counts["column"], "functions": counts["function"], "indexes": counts["index"],
            "edges": len(edge_list), "skipped_statements": model.skipped,
            "coverage": {"cols_total": ncols, "cols_with_purpose_pct": _pct(npurp, ncols),
                         "funcs_total": nfunc, "funcs_analyzed_pct": _pct(nan, nfunc)}}
    return {"meta": meta, "nodes": [nodes[k] for k in sorted(nodes)], "edges": edge_list}


def write_atomic(out, graph):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(graph, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a DB-schema graph from SQL migrations (no database).")
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args(argv)  # bad args -> SystemExit(2)
    try:
        graph = build_graph(args.root, args.paths)
    except FileNotFoundError as e:
        print(f"sql_graph: path not found: {e}", file=sys.stderr)
        return 2
    write_atomic(args.out, graph)
    m, c = graph["meta"], graph["meta"]["coverage"]
    print(f"sql_graph: {m['tables']} tables, {m['views']} views, {m['columns']} columns, {m['functions']} functions, "
          f"{m['indexes']} indexes, {m['edges']} edges, {m['skipped_statements']} skipped -> {args.out}")
    print(f"coverage: cols_with_purpose {c['cols_with_purpose_pct']}% of {c['cols_total']}; "
          f"funcs_analyzed {c['funcs_analyzed_pct']}% of {c['funcs_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
