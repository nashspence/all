"""Inventory real build tables and bind the two observed native-hook exceptions."""
import argparse
from collections import Counter
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True
from policy import BuildException, check_profiles

HEADS = {
    'all': '03de186a044c9c6b365347485a6c4093ce831c79',
    'fishhat': 'f96b83dc20f059d62a4363a63c37bb0ef8c642e5',
    'riverhog': 'be483fd6d567616d5fcd355202d61f1e682efe75',
    'guavajam': '54fce07b619628a5e92be946be4b189873ddf1a0',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repos', type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for name, expected in HEADS.items():
        root = args.repos / name
        assert subprocess.check_output(['git', '--no-replace-objects', '-C', str(root), 'rev-parse', 'HEAD'], text=True, env={**os.environ, 'GIT_GRAFT_FILE': os.devnull}).strip() == expected
        assert not subprocess.check_output(['git', '--no-replace-objects', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'], text=True, env={**os.environ, 'GIT_GRAFT_FILE': os.devnull})
        tracked = subprocess.check_output(['git', '--no-replace-objects', '-C', str(root), 'ls-files'], text=True, env={**os.environ, 'GIT_GRAFT_FILE': os.devnull}).splitlines()
        projects = {path: tomllib.loads((root / path).read_text()) for path in tracked if Path(path).name == 'pyproject.toml'}
        counts = Counter(json.dumps(manifest.get('build-system'), sort_keys=True) for manifest in projects.values() if 'project' in manifest)
        exceptions = {}
        witness_files = {}
        if name == 'riverhog':
            for directory in ('packages/retained-resource', 'packages/riverhog-client'):
                hook = directory + '/hatch_build.py'
                assert hook in tracked
                witness_files[hook] = (root / hook).read_bytes()
                assert 'setuptools' in witness_files[hook].decode()
                manifest_path = directory + '/pyproject.toml'
                exceptions[manifest_path] = BuildException(projects[manifest_path]['build-system'], {hook: hashlib.sha256(witness_files[hook]).hexdigest()}, 'Current custom hook builds native extension code', 'https://github.com/nashspence/riverhog/blob/' + expected + '/' + hook, 'Equivalent native artifact qualification exists for the common backend')
        errors = check_profiles(projects, witness_files, exceptions)
        result[name] = {'commit': expected, 'distribution_count': sum(counts.values()), 'build_profiles': dict(counts), 'observed_native_hook_exceptions': sorted(exceptions), 'candidate_default_mismatch_count': len(errors)}
    assert {name: entry['distribution_count'] for name, entry in result.items()} == {'all': 1, 'fishhat': 48, 'riverhog': 91, 'guavajam': 3}
    assert result['riverhog']['candidate_default_mismatch_count'] == 89
    print(json.dumps({'comparison': result, 'limit': 'Tables and byte-bound hooks only. No backend migration, wheel/sdist build, native compilation, license or runtime qualification was performed.'}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
