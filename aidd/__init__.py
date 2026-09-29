"""AIDD — a methodology for working with AI coding agents.

This package is the CLI distribution channel: `pip install -e .` from the
repo root gives you the `aidd` command. It's a thin dispatcher over the
stdlib-only scripts in skill/scripts/ — no logic lives twice. The Claude
Code skill itself (SKILL.md + hooks) is a separate distribution channel
(see ../skill/) for when an AI agent, not a human at a terminal, is driving.
"""

__version__ = "0.1.0"
