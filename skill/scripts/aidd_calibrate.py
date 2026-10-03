#!/usr/bin/env python3
"""AIDD calibration: measured agent minutes / tokens per effort class (stdlib only)."""
import re
import sys
from pathlib import Path

SEED = {"human_factor": 3.0,
        "classes": {"Low": {"agent_min": 1.0, "tokens_k": 45.0, "source": "seed-004"},
                    "Medium": {"agent_min": 2.0, "tokens_k": 62.0, "source": "seed-004"},
                    "High": {"agent_min": 4.0, "tokens_k": 90.0, "source": "seed-004"}}}
ORDER = ("Low", "Medium", "High")


def _num(s, default=0.0):
    try:
        return float(str(s).strip().rstrip("kK"))
    except (ValueError, TypeError):
        return default


def _seed():
    return {"human_factor": SEED["human_factor"],
            "classes": {k: dict(v) for k, v in SEED["classes"].items()}, "runs": []}


def _path(root):
    return Path(root) / ".aidd" / "calibration.toon"


def load_calibration(root):
    data = _seed()
    try:
        text = _path(root).read_text(encoding="utf-8-sig")
        hf, classes, runs, sect = None, {}, [], None
        for line in text.splitlines():
            if not line.strip():
                continue
            m = re.match(r"^human_factor:\s*(\S+)", line)
            if m:
                hf = float(m.group(1))
                continue
            m = re.match(r"^(\w+)\[\d*\]\{[^}]*\}:\s*$", line)
            if m:
                sect = m.group(1)
                continue
            cols = [c.strip() for c in line.strip().split(",")]
            if sect == "classes" and len(cols) == 4:
                classes[cols[0]] = {"agent_min": float(cols[1]), "tokens_k": float(cols[2]),
                                    "source": cols[3]}
            elif sect == "runs" and len(cols) == 4:
                runs.append({"spec": cols[0], "class": cols[1],
                             "agent_min": float(cols[2]), "tokens_k": float(cols[3])})
        if hf is None or not classes:
            return data
        return {"human_factor": hf, "classes": classes, "runs": runs}
    except Exception:
        return _seed()


def parse_closed_tasks(tasks_text, measured=None):
    out = {}
    try:
        blocks = re.split(r"(?m)^###\s+", tasks_text or "")[1:]
        for b in blocks:
            tid = (b.split(None, 1) or [""])[0].strip()
            e = re.search(r"(?m)^\s*-\s*Effort:\s*(Low|Medium|High)\b", b, re.I)
            if not e:
                continue
            cls = e.group(1).capitalize()
            am = re.search(r"(?m)^\s*-\s*Agent min:\s*([\d.]+)", b)
            tk = re.search(r"(?m)^\s*-\s*Tokens \(est\):\s*([\d.]+)\s*k?", b, re.I)
            a, t = _num(am.group(1)) if am else 0.0, _num(tk.group(1)) if tk else 0.0
            m = (measured or {}).get(tid)
            if isinstance(m, dict):
                a, t = _num(m.get("agent_min", a)), _num(m.get("tokens_k", t))
            r = out.setdefault(cls, {"agent_min": 0.0, "tokens_k": 0.0, "n": 0})
            r["agent_min"] += a
            r["tokens_k"] += t
            r["n"] += 1
    except Exception:
        pass
    return out


def _fmt(x):
    return str(int(x)) if float(x).is_integer() else ("%.2f" % x).rstrip("0")


def record(spec_dir, root=None):
    spec_dir = Path(spec_dir).resolve()
    root = Path(root) if root else spec_dir.parent.parent
    try:
        tasks = (spec_dir / "tasks.md").read_text(encoding="utf-8-sig")
    except Exception:
        return []
    agg = parse_closed_tasks(tasks)
    rows = [{"spec": spec_dir.name, "class": c, "agent_min": agg[c]["agent_min"],
             "tokens_k": agg[c]["tokens_k"]} for c in ORDER if c in agg]
    try:
        p = _path(root)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            seed = Path(__file__).resolve().parent.parent / "templates" / "calibration.toon"
            p.write_text(seed.read_text(encoding="utf-8-sig") if seed.exists() else
                         "human_factor: 3\nclasses[3]{class,agent_min,tokens_k,source}:\n"
                         "  Low,1,45,seed-004\n  Medium,2,62,seed-004\n  High,4,90,seed-004\n"
                         "runs[0]{spec,class,agent_min,tokens_k}:\n", encoding="utf-8")
        cal = load_calibration(root)
        keys = {(r["spec"], r["class"]) for r in rows}
        runs = [r for r in cal["runs"] if (r["spec"], r["class"]) not in keys] + rows
        lines = ["human_factor: %s" % _fmt(cal["human_factor"]),
                 "classes[%d]{class,agent_min,tokens_k,source}:" % len(cal["classes"])]
        lines += ["  %s,%s,%s,%s" % (k, _fmt(v["agent_min"]), _fmt(v["tokens_k"]), v["source"])
                  for k, v in cal["classes"].items()]
        lines.append("runs[%d]{spec,class,agent_min,tokens_k}:" % len(runs))
        lines += ["  %s,%s,%s,%s" % (r["spec"], r["class"], _fmt(r["agent_min"]),
                                      _fmt(r["tokens_k"])) for r in runs]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    return rows


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "record":
        print("usage: aidd_calibrate.py record <spec_dir>", file=sys.stderr)
        return 2
    for r in record(argv[1]):
        print("%s,%s,%s,%s" % (r["spec"], r["class"], _fmt(r["agent_min"]), _fmt(r["tokens_k"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
