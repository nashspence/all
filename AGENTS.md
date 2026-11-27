# Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
all-policy check . --repository nashspence/all
```

Start with the executable contract:

- [Protocol and adoption example](tests/test_protocol.py)
- [Owner inventory and current passing evidence](tests/test_audit.py)
- [CLI and library entry points](tests/test_cli.py)
- [Profile approval, refresh and suspension](tests/test_refresh.py)
- [Current authority and durable publication](tests/test_approval.py)

Profile enrollment and reinstatement operations: [refresh](docs/profile-refresh.md).

Keep scope to shared executable policy. Put behavior and examples in tests;
use prose only for intent or operations that code cannot reasonably convey.

```sh
python -m pip install --upgrade --force-reinstall 'nashspence-all @ git+https://github.com/nashspence/all.git@main'
```

For complete owner coverage, set the `ALL_REPOS_TOKEN` Actions secret to an
owner token with access to all owned repositories and read access to metadata,
contents, and Actions. Without it, the audit reports public results and fails
the inventory coverage check. Classic tokens also need `read:user` for the
inventory count. GitHub can disable inactive public-repo schedules; re-enable
them when resuming work.
