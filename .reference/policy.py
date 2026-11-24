"""Check resolved internal imports; each repository owns discovery and allowed edges."""

from collections.abc import Iterable, Mapping


def check_import_edges(
    module_owners: Mapping[str, str],
    resolved_imports: Iterable[tuple[str, str]],
    allowed_owner_edges: Iterable[tuple[str, str]],
) -> None:
    if any(
        type(module) is not str or not module or type(owner) is not str or not owner
        for module, owner in module_owners.items()
    ):
        raise ValueError("module and owner identities must be nonempty strings")
    owners = set(module_owners.values())
    allowed = set(allowed_owner_edges)
    if any(source not in owners or target not in owners for source, target in allowed):
        raise ValueError("allowed edge refers to an undiscovered owner")
    for source, target in resolved_imports:
        if source not in module_owners or target not in module_owners:
            raise ValueError("internal import has no discovered owner")
        source_owner, target_owner = module_owners[source], module_owners[target]
        if source_owner != target_owner and (source_owner, target_owner) not in allowed:
            raise ValueError(f"forbidden dependency: {source_owner} -> {target_owner}")

