"""Generate ``src/solaredge/types.py`` from SolarEdge's OpenAPI specifications.

The specs are kept in ``specs/`` so the types can be regenerated offline and an
API change shows up as a diff. ``--fetch`` downloads the published versions
first.

Usage::

    uv run --group codegen scripts/gen_types.py           # from specs/
    uv run --group codegen scripts/gen_types.py --fetch   # refresh specs/ first

Besides the types module this writes ``tests/_spec_responses.py``, which maps
every operation to its documented response type so the tests can check that
each client method is annotated with the right one.
"""

from __future__ import annotations

import re
import sys
import json
import keyword
import argparse
import textwrap
import subprocess
import urllib.parse
import urllib.request
from typing import Any
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "specs"
TYPES_OUT = ROOT / "src" / "solaredge" / "types.py"
RESPONSES_OUT = ROOT / "tests" / "_spec_responses.py"

# SolarEdge publishes its specs on Stoplight. Each entry is the spec file in
# specs/, the Stoplight project ID and the ID of the API node in that project.
SPECS = {
    "basic-monitoring-api.yaml": ("cHJqOjMxMjQ1NQ", "ubalc8zzxypbr"),
    "advanced-monitoring-api.yaml": ("cHJqOjMxMjQ1OQ", "7sudb71vmw1gu"),
}
STOPLIGHT_API = "https://stoplight.io/api/v1/projects"
STOPLIGHT_EXPORT = "https://api.stoplight.io/projects"

WIDTH = 88
COMMENT_WIDTH = WIDTH - len("    #: ")
SCALARS = {"integer": "int", "number": "float", "boolean": "bool", "string": "str"}


# --- fetching ----------------------------------------------------------------


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "solaredge-gen"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch() -> None:
    """Download each spec's published (default) branch into specs/."""
    SPEC_DIR.mkdir(exist_ok=True)
    for filename, (project, node) in SPECS.items():
        branches = json.loads(_get(f"{STOPLIGHT_API}/{project}/branches"))["items"]
        branch = next(b for b in branches if b["is_default"])["slug"]
        uri = json.loads(_get(f"{STOPLIGHT_API}/{project}/nodes/{node}"))["uri"]
        url = (
            f"{STOPLIGHT_EXPORT}/{project}/branches/"
            f"{urllib.parse.quote(branch, safe='')}/export{uri}"
        )
        (SPEC_DIR / filename).write_bytes(_get(url))
        print(f"fetched {filename} (branch {branch!r})")


# --- type rendering ----------------------------------------------------------


class Generator:
    """Turns OpenAPI component schemas into TypedDict source."""

    def __init__(self) -> None:
        self.schemas: dict[str, dict[str, Any]] = {}
        self.aliases: dict[str, str] = {}
        self.typed_dicts: dict[str, str] = {}

    def add_spec(self, spec: dict[str, Any]) -> None:
        """Register a spec's component schemas, refusing conflicting names."""
        for name, schema in spec["components"]["schemas"].items():
            if name in self.schemas and self.schemas[name] != schema:
                raise SystemExit(f"schema {name!r} differs between the specs")
            self.schemas[name] = schema

    def render_all(self) -> None:
        """Render every registered schema."""
        for name, schema in self.schemas.items():
            self.render_named(name, schema)

    def render_named(self, name: str, schema: dict[str, Any]) -> None:
        """Render one schema as a TypedDict, or as an alias if not an object."""
        if name in self.typed_dicts or name in self.aliases:
            return
        if schema.get("type", "object") == "object" and "properties" in schema:
            self.typed_dicts[name] = self._typed_dict(name, schema)
        else:
            self.aliases[name] = self.type_of(schema, name)

    def type_of(self, schema: dict[str, Any], context: str) -> str:
        """Return the Python type expression for a schema."""
        result = self._base_type(schema, context)
        if schema.get("nullable") and result != "Any":
            result = f"{result} | None"
        return result

    def _base_type(self, schema: dict[str, Any], context: str) -> str:  # noqa: PLR0911
        if "$ref" in schema:
            return schema["$ref"].rsplit("/", 1)[-1]
        if "allOf" in schema:
            if len(schema["allOf"]) != 1:
                raise SystemExit(f"{context}: allOf with several schemas")
            return self._base_type(schema["allOf"][0], context)
        kind = schema.get("type")
        if kind == "string" and "enum" in schema:
            return "Literal[" + ", ".join(repr(v) for v in schema["enum"]) + "]"
        if kind in SCALARS:
            return SCALARS[kind]
        if kind == "array":
            return f"list[{self.type_of(schema['items'], context)}]"
        if kind in ("object", None):
            if "properties" in schema:
                # An inline object: hoist it into its own TypedDict.
                self.render_named(context, schema)
                return context
            extra = schema.get("additionalProperties")
            if isinstance(extra, dict) and extra:
                return f"dict[str, {self.type_of(extra, context)}]"
            return "dict[str, Any]"
        raise SystemExit(f"{context}: unsupported schema {schema!r}")

    def _typed_dict(self, name: str, schema: dict[str, Any]) -> str:
        required = set(schema.get("required", []))
        fields = []
        for key, prop in schema["properties"].items():
            nested = f"{name}{key[:1].upper()}{key[1:]}"
            kind = self.type_of(prop, nested)
            if key not in required:
                kind = f"NotRequired[{kind}]"
            fields.append((key, kind, prop.get("description", "")))

        doc = _docstring(schema.get("description"), name)
        if all(k.isidentifier() and not keyword.iskeyword(k) for k, _, _ in fields):
            body = [f"class {name}(TypedDict):", *_indent(doc)]
            for key, kind, description in fields:
                body += [*_comment(description, "    "), f"    {key}: {kind}"]
            return "\n".join(body)

        # A key such as "from" needs the functional syntax. Its values are
        # evaluated at import time, so they are quoted as forward references.
        body = [f"{name} = TypedDict(", f"    {name!r},", "    {"]
        for key, kind, description in fields:
            body += [*_comment(description, "        "), f"        {key!r}: {kind!r},"]
        body += ["    },", ")", *_docstring(schema.get("description"), name, 0)]
        return "\n".join(body)

    def module(self, versions: list[str]) -> str:
        """Return the complete types module."""
        sources = "\n".join(f"- {v}" for v in versions)
        header = f'''"""TypedDicts for the SolarEdge Monitoring API's responses.

Generated by ``scripts/gen_types.py`` from:

{sources}

Do not edit by hand: change the generator or the specs in ``specs/`` and
regenerate.

These are type hints only. Responses are still plain dicts at runtime, and
fields the spec does not mark as required are ``NotRequired`` because real
responses can omit them.
"""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from typing_extensions import TypedDict, NotRequired
'''
        aliases = [f"{n}: TypeAlias = {t}" for n, t in sorted(self.aliases.items())]
        classes = [self.typed_dicts[n] for n in sorted(self.typed_dicts)]
        names = sorted([*self.aliases, *self.typed_dicts])
        exports = ["__all__ = [", *(f"    {n!r}," for n in names), "]"]
        parts = ["\n".join(aliases), *classes, "\n".join(exports)]
        return header + "\n" + "\n\n\n".join(parts) + "\n"


def _first_paragraph(text: str) -> str:
    return " ".join(text.strip().split("\n\n")[0].split())


def _docstring(description: str | None, name: str, indent: int = 4) -> list[str]:
    """Render a docstring whose first line is a one-line summary sentence."""
    text = _first_paragraph(description or "")
    text = text.replace('"""', "'''").replace("\\", "\\\\")
    if text and not text.endswith((".", "!", "?")):
        text += "."
    summary, _, rest = text.partition(". ")
    if rest:
        summary += "."
    if not summary or len(summary) + indent + 6 > WIDTH:
        summary, rest = f"The ``{name}`` schema.", text
    if not rest:
        return [f'"""{summary}"""']
    return [f'"""{summary}', "", *textwrap.wrap(rest, WIDTH - indent), '"""']


def _indent(lines: list[str]) -> list[str]:
    return [f"    {line}" if line else "" for line in lines]


def _comment(description: str, indent: str) -> list[str]:
    text = _first_paragraph(description)
    if not text:
        return []
    width = WIDTH - len(indent) - 3
    return [f"{indent}#: {line}" for line in textwrap.wrap(text, width)]


# --- operation → response type -----------------------------------------------


def _pascal(text: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", text))


def responses(spec: dict[str, Any], generator: Generator) -> dict[tuple, str]:
    """Map (HTTP method, path template) to the success response's type."""
    result = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            ok = next(r for code, r in operation["responses"].items() if code < "300")
            schema = ok.get("content", {}).get("application/json", {}).get("schema")
            name = _pascal(operation.get("operationId") or operation["summary"])
            kind = "None" if schema is None else generator.type_of(schema, name)
            template = re.sub(r"\{serialNumbers?\}", "{sn}", path)
            result[(method.upper(), template)] = kind
    return result


def main() -> None:
    """Generate the types module and the test mapping."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--fetch", action="store_true", help="download the published specs first"
    )
    if parser.parse_args().fetch:
        fetch()

    generator = Generator()
    specs = [yaml.safe_load((SPEC_DIR / f).read_text()) for f in SPECS]
    for spec in specs:
        generator.add_spec(spec)
    generator.render_all()
    mapping: dict[tuple, str] = {}
    for spec in specs:
        mapping.update(responses(spec, generator))
    versions = [f"{s['info']['title']} {s['info']['version']}" for s in specs]

    TYPES_OUT.write_text(generator.module(versions))
    lines = [
        '"""Each operation\'s documented success response type.',
        "",
        "Generated by scripts/gen_types.py. Do not edit by hand.",
        '"""',
        "",
        "SPEC_RESPONSES = {",
        *(f"    {k!r}: {v!r}," for k, v in sorted(mapping.items())),
        "}",
    ]
    RESPONSES_OUT.write_text("\n".join(lines) + "\n")

    outputs = [str(TYPES_OUT), str(RESPONSES_OUT)]
    subprocess.run(["ruff", "format", "--quiet", *outputs], check=True)
    subprocess.run(["ruff", "check", "--fix", "--quiet", *outputs], check=True)
    print(
        f"wrote {len(generator.typed_dicts)} TypedDicts, {len(generator.aliases)} "
        f"aliases and {len(mapping)} operation types",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
