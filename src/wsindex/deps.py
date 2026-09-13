"""Which repositories in a workspace actually depend on which.

Two sources, and the whole value is that they disagree.

**What the build files say.** `PROVIDES` and `DEPENDS_ON`, read from
manifests — a declaration by the people who wrote the repository.

**What the code does.** A name anchored in one repository and used in
another, which the link store already holds because its pairs are keyed
by name and `by_name` is a workspace query. Measured over three
workspaces, that is 1 170 clean cross-repository names with nothing
written for the purpose.

Agreement is the boring case. The disagreements are the report:

- **Undeclared.** Code uses another repository's names and no manifest
  says so. Sometimes that is a real build problem; sometimes it is two
  repositories sharing a vocabulary because one is a fork of the other,
  or because both belong to an organisation with naming conventions.
  This says which pairs to look at, not which are bugs.
- **Unused.** A dependency is declared and none of its names appear.
  Either dead weight in the manifest, or the dependency is used through
  a mechanism no name can see — a plugin registry, reflection, a
  subprocess.

Neither is an error. Both are questions nothing else in this project
could ask, because both halves have to exist before they can disagree.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from wsindex.links import LinkKind, LinkStore

MIN_NAMES = 2
"""How many shared names a pair needs before it is worth reporting.

One name in common between two repositories is the definition of a
coincidence — every workspace has a `Config` and a `Handler`. Two is not
proof either, which is why what this reports is a pair to look at."""


@dataclass(frozen=True, kw_only=True)
class Link:
    """One repository's relationship with another.

    Attributes:
        user: The repository whose code uses the names.
        owner: The repository that defines or declares them.
        names: How many distinct names they share. Not evidence of a
            dependency on its own — a fork shares hundreds.
        declared: Whether a manifest on either side says these two are
            connected. Either side, because a shared name links both
            ways while a dependency is declared once and in one
            direction.
        examples: A few of the shared names, spelled as the defining
            repository spells them — the join is on a normalised key and
            nobody types that.
    """

    user: str
    owner: str
    names: int
    declared: bool
    examples: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Report:
    """What the manifests and the code each say, and where they differ.

    Attributes:
        declared: Repo -> the workspace repos its manifests require.
        used: Every pair whose code shares names, declared or not.
        undeclared: Pairs whose code shares names with nothing declaring
            it — ordered by how many names, so the most suspicious is
            first.
        unused: Declared dependencies with no shared name at all.
        packages: How many package names the workspace publishes. Zero
            means no manifest was understood, which makes every other
            number here unreadable rather than alarming.
    """

    declared: dict[str, set[str]] = field(default_factory=dict)
    used: tuple[Link, ...] = ()
    undeclared: tuple[Link, ...] = ()
    unused: tuple[tuple[str, str], ...] = ()
    packages: int = 0


def analyse(links: LinkStore, *, repos: list[str] | None = None) -> Report:
    """Compare what the manifests declare against what the code names.

    Args:
        links: The workspace's link store, after an index run.
        repos: Restrict to these repo ids, or None for all of them.

    Returns:
        The two graphs and their disagreements.
    """
    rows = links.every(
        (
            LinkKind.PROVIDES,
            LinkKind.DEPENDS_ON,
            LinkKind.DEFINES,
            LinkKind.DECLARES,
            LinkKind.MENTIONS,
        )
    )
    wanted = set(repos) if repos else None
    provides: dict[str, set[str]] = defaultdict(set)
    needs: dict[str, set[str]] = defaultdict(set)
    anchors: dict[str, set[str]] = defaultdict(set)
    uses: dict[str, set[str]] = defaultdict(set)
    # Normalised keys join; a reader needs the spelling somebody typed.
    spelled: dict[str, str] = {}
    for kind, name, norm, repo in rows:
        if wanted is not None and repo not in wanted:
            continue
        if kind is LinkKind.PROVIDES:
            provides[name].add(repo)
        elif kind is LinkKind.DEPENDS_ON:
            needs[repo].add(name)
        elif not norm:
            continue
        elif kind is LinkKind.MENTIONS:
            uses[norm].add(repo)
        else:
            anchors[norm].add(repo)
            spelled.setdefault(norm, name)

    declared: dict[str, set[str]] = defaultdict(set)
    for repo, required in needs.items():
        for package in required:
            declared[repo] |= provides.get(package, set()) - {repo}

    shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for norm, owners in anchors.items():
        for user in uses.get(norm, set()) - owners:
            for owner in owners:
                shared[(user, owner)].add(norm)

    def connected(one: str, other: str) -> bool:
        return other in declared.get(one, set()) or one in declared.get(other, set())

    found = [
        Link(
            user=user,
            owner=owner,
            names=len(names),
            declared=connected(user, owner),
            examples=tuple(spelled.get(norm, norm) for norm in sorted(names)[:5]),
        )
        for (user, owner), names in shared.items()
        if len(names) >= MIN_NAMES
    ]
    found.sort(key=lambda link: (-link.names, link.user, link.owner))
    unused = tuple(
        sorted(
            (user, owner)
            for user, owners in declared.items()
            for owner in owners
            if not shared.get((user, owner))
        )
    )
    return Report(
        declared={repo: set(owners) for repo, owners in declared.items()},
        used=tuple(found),
        undeclared=tuple(link for link in found if not link.declared),
        unused=unused,
        packages=len(provides),
    )
