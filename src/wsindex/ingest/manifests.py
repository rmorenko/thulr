"""What a repository calls itself, and what it says it needs.

Every other link here is found in source text. This one is found in the
file a build tool reads, which makes it the only edge in the store that
is a *declaration* by the people who wrote the repository rather than an
inference about their code. That is why it is worth reading separately:
it is the one thing that can tell a name two repositories share from a
dependency two repositories have.

The use it was built for. Name-keyed joins already cross repository
boundaries — measured, 1 170 clean names over three workspaces — but the
share of them that is coincidence grows with the corpus: 4% on a
six-repo Go workspace, 8% on TypeScript, **14%** on a 13 000-name C# one,
where the same name is defined in two repositories and nothing can say
which was meant. A declared dependency settles it.

And the inverse is worth having on its own: a repository whose code uses
another's names while its manifest declares no such dependency is a real
build problem, and nothing in this project could see it before.

Read from the repository root rather than from indexed chunks, because
the walker indexes `package.json` and not `go.mod`, and which manifests
a language happens to register is not a thing this should depend on.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

MAX_BYTES = 512 * 1024
"""A manifest larger than this is not a manifest. `package-lock.json`
runs to megabytes and lists the transitive world, which is noise: what
matters is what a repository *declares*, not what it resolves to."""

_GO_MODULE = re.compile(r"^module\s+(\S+)", re.MULTILINE)
_GO_REQUIRE_ONE = re.compile(r"^require\s+(\S+)\s+v", re.MULTILINE)
_GO_REQUIRE_BLOCK = re.compile(r"^require\s*\((.*?)^\)", re.MULTILINE | re.DOTALL)
_GO_IN_BLOCK = re.compile(r"^\s*(\S+)\s+v", re.MULTILINE)
_CS_PACKAGE = re.compile(r'<PackageReference\s+Include="([^"]+)"')
_CS_PROJECT = re.compile(r'<ProjectReference\s+Include="([^"]+)"')
_GEM_NAME = re.compile(r"""\.name\s*=\s*["']([^"']+)["']""")
_GEM_DEP = re.compile(
    r"""^\s*(?:gem|\w+\.add(?:_\w+)?_dependency)\s+["']([^"']+)["']""", re.MULTILINE
)
_POM_ARTIFACT = re.compile(r"<artifactId>([^<]+)</artifactId>")


@dataclass(frozen=True)
class Manifest:
    """What one repository's build files say about it.

    Attributes:
        provides: Names this repository publishes itself under. Usually
            one; a monorepo of packages has several.
        depends: Names it declares it needs. Direct dependencies only —
            a lock file's transitive closure says nothing about intent.
    """

    provides: set[str] = field(default_factory=set)
    depends: set[str] = field(default_factory=set)


def _read(path: Path) -> str | None:
    """A manifest's text, or None if it is missing, huge or unreadable."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _go(text: str, into: Manifest) -> None:
    """`go.mod`: one `module`, then `require` singly or in a block."""
    into.provides.update(_GO_MODULE.findall(text))
    into.depends.update(_GO_REQUIRE_ONE.findall(text))
    for block in _GO_REQUIRE_BLOCK.findall(text):
        into.depends.update(_GO_IN_BLOCK.findall(block))


def _package_json(text: str, into: Manifest) -> None:
    """npm, and the three places it spells "needs"."""
    try:
        data = json.loads(text)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    name = data.get("name")
    if isinstance(name, str):
        into.provides.add(name)
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(section)
        if isinstance(block, dict):
            into.depends.update(str(key) for key in block)


def _toml(text: str, into: Manifest) -> None:
    """Cargo and pyproject, which agree on enough to read together."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return
    for section in ("package", "project", "tool"):
        block = data.get(section)
        if isinstance(block, dict) and isinstance(block.get("name"), str):
            into.provides.add(block["name"])
    cargo = data.get("dependencies")
    if isinstance(cargo, dict):
        into.depends.update(str(key) for key in cargo)
    project = data.get("project")
    if isinstance(project, dict):
        listed = project.get("dependencies")
        if isinstance(listed, list):
            # `httpx>=0.28,<1` — the name is everything before the first
            # comparison, bracket or space.
            into.depends.update(re.split(r"[<>=!~\[\s;]", str(item))[0] for item in listed)


def _csproj(path: Path, text: str, into: Manifest) -> None:
    """MSBuild. A project's own name is its filename, by convention."""
    into.provides.add(path.stem)
    # A package is named; a project is *pointed at*. Taking the stem of
    # both turned `Newtonsoft.Json` into `Newtonsoft`, which matches
    # nothing and looks like a real dependency while doing it.
    into.depends.update(_CS_PACKAGE.findall(text))
    for reference in _CS_PROJECT.findall(text):
        into.depends.add(Path(reference.replace("\\", "/")).stem)


def _ruby(text: str, into: Manifest) -> None:
    """Gemfile and gemspec, which share enough syntax to share a reader."""
    into.provides.update(_GEM_NAME.findall(text))
    into.depends.update(_GEM_DEP.findall(text))


def _pom(text: str, into: Manifest) -> None:
    """Maven. The first artifactId is the project's own; the rest are
    dependencies, which is what the document order means and is cheaper
    than an XML parse for a fact this shallow."""
    found = _POM_ARTIFACT.findall(text)
    if found:
        into.provides.add(found[0])
        into.depends.update(found[1:])


_BY_NAME = {
    "go.mod": _go,
    "package.json": _package_json,
    "cargo.toml": _toml,
    "pyproject.toml": _toml,
    "gemfile": _ruby,
    "pom.xml": _pom,
}
"""Manifests recognised by filename, lowercased."""

_BY_SUFFIX = (".csproj", ".gemspec")
"""And by extension, where the filename carries the project instead.

A tuple rather than a dispatch table because the two readers disagree
about their arguments — a `.csproj` names itself by its path — and a
dict of mixed signatures is a dict nothing can type."""

DEPTH = 3
"""How far below the root to look.

Not one: a C# solution keeps `src/Foo/Foo.csproj`, a JavaScript monorepo
`packages/*/package.json`. Not unbounded either — below this it is
`node_modules` and vendored trees, which declare other people's
dependencies, not this repository's."""

_SKIP = {"node_modules", "vendor", ".git", "target", "dist", "build", "third_party"}


def read_manifests(root: Path) -> Manifest:
    """Every declaration the build files in one repository make.

    Args:
        root: The repository's working tree.

    Returns:
        What it provides and what it depends on, both possibly empty —
        a repository with no manifest is normal, not an error.
    """
    found = Manifest()
    for path in _candidates(root):
        _read_one(path, found)
    # A repository never depends on itself, whatever a monorepo's
    # packages say about each other.
    found.depends.difference_update(found.provides)
    return found


def _candidates(root: Path) -> Iterator[Path]:
    """Files shallow enough to be a manifest, in depth order.

    Breadth rather than `rglob`: a manifest lives at the top of a
    package, and walking a whole monorepo to find one at depth nine
    costs far more than it ever returns.
    """
    for depth in range(DEPTH + 1):
        for path in root.glob("/".join(["*"] * depth) if depth else "*"):
            if path.is_file() and not _SKIP & set(path.parts):
                yield path


def _read_one(path: Path, found: Manifest) -> None:
    """Add one file's declarations, if it is a manifest at all.

    Named readers win over suffix ones: `package.json` is matched by
    name and never reaches the suffix table, which is what keeps a
    `.json` fixture somewhere in the tree from being read as a manifest.
    """
    reader = _BY_NAME.get(path.name.lower())
    if reader is not None:
        text = _read(path)
        if text is not None:
            reader(text, found)
        return
    suffix = path.suffix.lower()
    if suffix not in _BY_SUFFIX:
        return
    text = _read(path)
    if text is None:
        return
    if suffix == ".csproj":
        _csproj(path, text, found)
    else:
        _ruby(text, found)
