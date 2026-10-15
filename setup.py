"""Bundle skill/ and adapters/ into the wheel as aidd/_data/{skill,adapters}.

The layout under _data/ mirrors the repo root on purpose, so scripts that locate `adapters/`
relative to `skill/` behave the same in a checkout and in a wheel install. Project metadata
lives in pyproject.toml; this file only adds the copy step.
"""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

BUNDLED = ("skill", "adapters")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.bak", "*.spill", ".pytest_cache")


class BuildPyWithData(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        dest_root = Path(self.build_lib) / "aidd" / "_data"
        for name in BUNDLED:
            src = root / name
            if not src.is_dir():
                raise SystemExit(f"cannot bundle {name}/: {src} not found (build from the repo root)")
            dest = dest_root / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=IGNORE)


setup(cmdclass={"build_py": BuildPyWithData})
