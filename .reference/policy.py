"""Scope public coauthor exemptions without weakening an owner's private denylist."""

import re
from collections.abc import Callable, Iterable


def public_text_violations(
    text: str,
    *,
    context: str,
    private_literals: Iterable[str],
    approved_coauthor_addresses: frozenset[str],
    inspect_remaining: Callable[[str], Iterable[str]],
) -> tuple[str, ...]:
    """The caller owns other scanning rules; no general ban on public names or emails.

    The private literal check always sees the complete original text. The only
    exemption removes an exact approved address from final commit-message trailers,
    leaving the display name, other trailers and all adjacent content for inspection.
    """
    if context not in {"source", "commit-message"}:
        raise ValueError("unsupported public text context")
    private = tuple(private_literals)
    if any(type(value) is not str or not value for value in private):
        raise ValueError("private literals must be explicit nonempty strings")
    if any(value in text for value in private):
        return ("private-identifier",)
    inspected = text
    if context == "commit-message" and "\n\n" in text:
        prefix, trailer_block = text.rsplit("\n\n", 1)
        trailer_text = trailer_block.rstrip("\n")
        ending = trailer_block[len(trailer_text):]
        trailers = trailer_text.split("\n")
        if all(re.fullmatch(r"[A-Za-z][A-Za-z-]*: [^\r\n]*", line) for line in trailers):
            rewritten = []
            for line in trailers:
                match = re.fullmatch(r"Co-authored-by: ([^<>\r\n]+) <([^<>\s]+)>", line)
                if match and match.group(2) in approved_coauthor_addresses:
                    line = f"Co-authored-by: {match.group(1)} <approved-public-address>"
                rewritten.append(line)
            inspected = prefix + "\n\n" + "\n".join(rewritten) + ending
    return tuple(inspect_remaining(inspected))

