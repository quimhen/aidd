"""Prepare a runtime-bound, multi-installation AIDD release without applying it."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import aidd_selective_update as updater


def _git(repo, *args, allow_missing=False):
    result = subprocess.run(['git', *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode and not allow_missing:
        raise ValueError('git could not inspect the requested baseline')
    return result.stdout if result.returncode == 0 else None


def inventory(repo, baseline):
    tracked = _git(repo, 'diff', '--no-renames', '--name-only', '-z', baseline, '--', 'skill', 'adapters/dot-aidd', 'aidd')
    untracked = _git(repo, 'ls-files', '-z', '--others', '--exclude-standard', '--', 'skill', 'adapters/dot-aidd', 'aidd')
    names = {os.fsdecode(name) for name in (tracked + untracked).split(b'\0') if name}
    skill, adapter = set(), set()
    for name in names:
        if name.startswith('skill/'):
            relative, output = name[len('skill/'):], skill
        elif name.startswith('adapters/dot-aidd/'):
            relative, output = name[len('adapters/dot-aidd/'):], adapter
        elif name.startswith('aidd/'):
            if name != 'aidd/cli.py':
                raise ValueError('unsupported changed package file: ' + name)
            if not (repo / name).is_file():
                raise ValueError('release does not delete package files: ' + name)
            continue
        else:
            continue
        updater._relative(relative)  # Never silently omit a changed distributed file.
        if not (repo / name).is_file():
            raise ValueError('release does not delete distributed files: ' + name)
        output.add(relative)
    # A distributed counterpart is included even if only one side was marked
    # changed; a mismatch stops the plan instead of installing a mixed version.
    for relative in (skill | adapter) - {'SKILL.md'}:
        left, right = repo / 'skill' / relative, repo / 'adapters/dot-aidd' / relative
        if left.is_file() and right.is_file():
            if left.read_bytes().replace(b'\r\n', b'\n') != right.read_bytes().replace(b'\r\n', b'\n'):
                raise ValueError('skill/adapter versions differ: ' + relative)
            skill.add(relative)
            adapter.add(relative)
    return sorted(skill), sorted(adapter)


_IMPACT_LINE = (b'- Use `aidd impact <spec> --changed --base <commit>` to identify affected tasks and units using Git and declared dependencies; an unverified base is diagnostic, not historical audit proof. Use `aidd verify <spec> --tasks T-01,T-02` to run the relevant verification-table commands once; its evidence is partial and does not close the spec. Never scan files line by line merely to identify changes.')


def _resolve_impact_conflict(data, original, source):
    """Resolve only the known empty-local/incoming-impact insertion."""
    lines = data.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith(b'<<<<<<< ')]
    if len(starts) != 1:
        raise ValueError('profile SKILL.md merge failed or conflicts; review required')
    i = starts[0]
    if (i < 2 or lines[i-2].strip() != b'## Verification and approval economy (user preference)'
            or lines[i-1].strip() or i + 4 >= len(lines)
            or lines[i+1].strip() != b'======='
            or lines[i+2].strip() != _IMPACT_LINE
            or not lines[i+3].startswith(b'>>>>>>> ')
            or not lines[i+4].startswith(b'- Reuse valid execution evidence')
            or _IMPACT_LINE in original or source.count(_IMPACT_LINE) != 1
            or any(line.startswith((b'<<<<<<< ', b'=======', b'>>>>>>> '))
                   for line in lines[i+4:])):
        raise ValueError('profile SKILL.md merge failed or conflicts; review required')
    return b''.join(lines[:i] + [lines[i+2]] + lines[i+4:])


def _stage_profile_skill(source, current, baseline, stage):
    """Three-way merge in staging; abort conflicts and bind the current bytes."""
    before = updater._digest(current)
    original = current.read_bytes()
    if updater._digest(current) != before:
        raise ValueError('profile SKILL.md changed during staging')
    stage.mkdir()
    (stage / 'source').mkdir()
    (stage / 'baseline').mkdir()
    staged = stage / 'source' / 'SKILL.md'
    staged.write_bytes(original)
    (stage / 'baseline' / 'SKILL.md').write_bytes(original)
    result = subprocess.run(['git', 'merge-file', str(staged), str(baseline), str(source)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 1:
        staged.write_bytes(_resolve_impact_conflict(staged.read_bytes(), original, source.read_bytes()))
    elif result.returncode:
        raise ValueError('profile SKILL.md merge failed or conflicts; review required')
    return updater.make_plan(stage / 'source', current.parent, ['SKILL.md'], stage / 'baseline', bind_runtime=True)


def _check_path_launcher():
    launcher = shutil.which('aidd')
    if not launcher:
        raise ValueError('aidd executable not found on PATH')
    expected_dir = Path(sysconfig.get_path('scripts')).resolve(strict=True)
    if Path(launcher).resolve(strict=True).parent != expected_dir:
        raise ValueError('aidd on PATH belongs to a different scripts directory')
    return str(Path(launcher).resolve(strict=True))


def _baseline(repo, revision, source, names, directory):
    directory.mkdir()
    for name in names:
        relative = (source / name).relative_to(repo).as_posix()
        data = _git(repo, 'show', revision + ':' + relative, allow_missing=True)
        if data is not None:
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def prepare(repo, project, profiles, codex_config, output, baseline, expected_python, expected_prefix):
    repo, project = updater._root(repo), updater._root(project)
    profiles = [updater._root(item) for item in profiles]
    if not profiles or len({os.path.normcase(str(p)) for p in profiles}) != len(profiles):
        raise ValueError('at least one distinct profile is required')
    if not os.path.samefile(sys.executable, expected_python):
        raise ValueError('run the planner using the selected Python interpreter')
    launcher = _check_path_launcher()
    actual_prefix = None if sys.pycache_prefix is None else os.path.normcase(os.path.realpath(sys.pycache_prefix))
    wanted_prefix = None if expected_prefix == 'none' else os.path.normcase(os.path.realpath(expected_prefix))
    if actual_prefix != wanted_prefix:
        raise ValueError('configured Python bytecode prefix does not match this runtime')
    if os.name == 'nt' and actual_prefix is not None:
        raise ValueError('Windows release with a cache prefix cannot safely enumerate path aliases')
    revision = _git(repo, 'rev-parse', '--verify', baseline + '^{commit}').decode('ascii').strip()
    skill_files, adapter_files = inventory(repo, revision)
    if 'SKILL.md' not in skill_files:
        skill_files.append('SKILL.md')
        skill_files.sort()
    source_skill, source_adapter, source_cli = repo / 'skill', repo / 'adapters' / 'dot-aidd', repo / 'aidd'
    site = Path(sysconfig.get_path('purelib')).resolve(strict=True)
    package = updater._root(site / 'aidd')
    distributions = [p for p in site.iterdir() if p.name.lower().startswith('aidd_cli-') and p.name.lower().endswith('.dist-info')]
    if len(distributions) != 1:
        raise ValueError('aidd-cli distribution is missing or ambiguous')
    dist_info = updater._root(distributions[0])
    updater._unique_distribution(site, dist_info)
    codex = updater._root(codex_config) if codex_config is not None else None
    if codex is not None:
        required_profile = updater._root(Path.home() / '.claude' / 'skills' / 'aidd')
        if required_profile not in profiles or 'hooks/codex_subagent.py' not in skill_files:
            raise ValueError('Codex hooks require the Claude profile and its hook in this transaction')
    targets = [*profiles, updater._root(project / '.aidd'), package, dist_info]
    if codex is not None:
        targets.append(codex)
    output = Path(output).absolute()
    updater._no_links(output)
    output = output.resolve(strict=False)
    for target in [repo, *targets]:
        try:
            common = os.path.commonpath((os.path.normcase(str(output)), os.path.normcase(str(target))))
        except ValueError:
            continue
        if common == os.path.normcase(str(target)):
            raise ValueError('output must be outside all source and installation roots')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    base = output / 'baseline'
    base.mkdir()
    _baseline(repo, revision, source_skill, skill_files, base / 'skill')
    _baseline(repo, revision, source_adapter, adapter_files, base / 'adapter')
    _baseline(repo, revision, source_cli, ['cli.py'], base / 'cli')
    plans = []
    profile_files = [name for name in skill_files if name != 'SKILL.md']
    for profile in profiles:
        if profile_files:
            plans.append(updater.make_plan(source_skill, profile, profile_files, base / 'skill', bind_runtime=True))
        if 'SKILL.md' in skill_files:
            plans.append(_stage_profile_skill(source_skill / 'SKILL.md', profile / 'SKILL.md',
                         base / 'skill' / 'SKILL.md', output / ('profile-skill-' + str(len(plans)))))
    if adapter_files:
        plans.append(updater.make_plan(source_adapter, project / '.aidd', adapter_files, base / 'adapter', bind_runtime=True))
    plans.extend(updater.prepare_package_plan(package, dist_info, source_cli, base / 'cli',
        source_skill, base / 'skill', source_adapter, base / 'adapter', output / 'package',
        True, skill_files, adapter_files))
    if codex is not None:
        plans.append(updater.prepare_codex_hooks_plan(codex, output / 'hooks'))
    # Check the specific caches for the bound interpreter; apply rechecks.
    for plan in plans:
        for item in plan['files']:
            if item['path'].endswith('.py'):
                updater._python_cache_timestamps(Path(plan['target']) / item['path'])
    updater._atomic_write(output / 'release-plans.json', json.dumps(plans, indent=2).encode('utf-8'), 0o600)
    summary = {'baseline_commit': revision, 'runtime': updater._runtime_identity(),
               'skill_files': skill_files, 'adapter_files': adapter_files,
               'profile_skill_md': 'three-way merged when changed', 'path_launcher': launcher,
               'codex_hooks_planned': codex is not None,
               'codex_trust_changed': False, 'targets_modified': False, 'plans': len(plans)}
    updater._atomic_write(output / 'summary.json', json.dumps(summary, indent=2).encode('utf-8'), 0o600)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--profile', type=Path, action='append', required=True)
    parser.add_argument('--codex-config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--expected-cache-prefix', required=True, help='literal none or the configured prefix path')
    args = parser.parse_args(argv)
    try:
        result = prepare(args.repo, args.project, args.profile, args.codex_config, args.output,
                         args.baseline, args.runtime, args.expected_cache_prefix)
        print(json.dumps(result, indent=2))
        print('Prepared only; Codex lifecycle hooks require separate host trust review.')
    except (ValueError, OSError, UnicodeError) as exc:
        print('Refused:', exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
