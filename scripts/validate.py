#!/usr/bin/env python3
"""Validate every providers/*.json against the schema and the dataset's rules.

Run locally with `python3 scripts/validate.py`; CI runs the same thing on
every pull request. The schema catches a malformed file; the rules below
catch the things a schema cannot express but that are the whole point of this
dataset — that a value is traceable, and that a gap is declared rather than
guessed.

Exits non-zero if anything fails, and prints every problem rather than the
first, so a contributor fixes them in one pass.
"""
from __future__ import annotations

import json
import pathlib
import sys

try:
    from jsonschema import Draft7Validator
except ImportError:
    sys.exit("jsonschema is required: pip install jsonschema")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "provider.schema.json").read_text())
VALIDATOR = Draft7Validator(SCHEMA)

SECURITY_FIELDS = ("imap", "pop3", "smtp")


def servers(provider: dict):
    """Yield (label, server-dict) for every server block present."""
    for block in ("incoming", "outgoing"):
        for kind, server in (provider.get(block) or {}).items():
            yield kind, server


def check(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{path.name}: not valid JSON — {exc}"]

    # 1. Schema.
    for error in sorted(VALIDATOR.iter_errors(data), key=lambda e: e.path):
        where = "/".join(str(p) for p in error.path) or "(root)"
        problems.append(f"{path.name}: {where}: {error.message}")

    # 2. The filename is the slug. A mismatch means one of them is wrong, and
    #    tooling that reads by slug and tooling that reads by filename would
    #    then disagree.
    if data.get("slug") and path.stem != data["slug"]:
        problems.append(f"{path.name}: slug '{data['slug']}' does not match the filename")

    # A provider has to be findable by something. Most are found by the
    # domain people type; some (GoDaddy, Microsoft 365) are only ever used on
    # a customer's own domain and are found by their MX hosts instead. One of
    # the two must be present, or nothing can ever resolve to this entry.
    if not data.get("domains") and not data.get("mx_patterns"):
        problems.append(f"{path.name}: has neither `domains` nor `mx_patterns` — nothing could resolve to it")

    has_servers = any(True for _ in servers(data))

    # 3. A value with no source cannot be verified, and an unverifiable value
    #    is exactly what this dataset exists not to be. A provider that lists
    #    any server must cite where its settings came from.
    if has_servers and not data.get("sources"):
        problems.append(f"{path.name}: has server settings but an empty `sources` — every value must cite the provider's own page")

    # Structured authentication is a normalization of sourced text, not a
    # substitute for that evidence. A null value is an explicit gap.
    if data.get("auth_methods") is not None:
        authentication = data.get("authentication")
        if not isinstance(authentication, str) or not authentication.strip():
            problems.append(f"{path.name}: auth_methods requires documented authentication text")
        if not data.get("sources"):
            problems.append(f"{path.name}: auth_methods requires first-party sources")
        if data.get("client_access") is False:
            problems.append(f"{path.name}: auth_methods must be null when client_access is false")

    # 4. A guess dressed as a fact. If a server states its encryption
    #    (security is set) then security_documented must be true; if it does
    #    not (security is null) the field it left out should be declared in
    #    `undocumented` so the gap is visible rather than silent.
    undocumented = set(data.get("undocumented") or [])
    for kind, server in servers(data):
        security = server.get("security")
        documented = server.get("security_documented", False)
        if security is not None and not documented:
            problems.append(f"{path.name}: {kind} has a security value but security_documented is false — set it true, or null the value")
        if security is None and f"{kind}_security" not in undocumented and data.get("client_access", True):
            problems.append(f"{path.name}: {kind} security is null but '{kind}_security' is not listed in `undocumented` — declare the gap")

    return problems


def main() -> int:
    files = sorted((ROOT / "providers").glob("*.json"))
    if not files:
        print("No provider files found under providers/.")
        return 1

    problems: list[str] = []
    for path in files:
        problems.extend(check(path))

    if problems:
        print(f"✗ {len(problems)} problem(s) in {len(files)} file(s):\n")
        for p in problems:
            print("  " + p)
        return 1

    print(f"✓ {len(files)} provider file(s) valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
