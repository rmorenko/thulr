"""Two graphs over one workspace, and the questions they disagree about.

The manifests say what the people who wrote a repository declared; the
names say what its code actually reaches for. Neither alone is a finding
— the report is where they differ.
"""

from pathlib import Path

import pytest

from thulr.deps import analyse
from thulr.links import Link, LinkKind, LinkStore


@pytest.fixture
def links(tmp_path: Path) -> LinkStore:
    return LinkStore(tmp_path / "idx")


def add(store: LinkStore, repo: str, *entries: tuple[LinkKind, str]) -> None:
    store.add_links(
        [
            Link(src_chunk_id=f"{repo}-{n}", kind=kind, name=name, line=1)
            for n, (kind, name) in enumerate(entries)
        ],
        repo=repo,
        path="f",
    )


def test_code_using_another_repo_without_declaring_it_is_reported(links: LinkStore) -> None:
    # The finding nothing here could make before: both halves have to
    # exist before they can disagree.
    add(
        links,
        "web",
        (LinkKind.PROVIDES, "web"),
        (LinkKind.MENTIONS, "RetryPolicy"),
        (LinkKind.MENTIONS, "BackoffWindow"),
    )
    add(
        links,
        "core",
        (LinkKind.PROVIDES, "core"),
        (LinkKind.DEFINES, "RetryPolicy"),
        (LinkKind.DEFINES, "BackoffWindow"),
    )

    report = analyse(links)

    assert [(d.user, d.owner, d.names) for d in report.undeclared] == [("web", "core", 2)]
    assert report.undeclared[0].examples == ("BackoffWindow", "RetryPolicy")


def test_a_declared_dependency_makes_the_same_names_unremarkable(links: LinkStore) -> None:
    add(
        links,
        "web",
        (LinkKind.PROVIDES, "web"),
        (LinkKind.DEPENDS_ON, "core"),
        (LinkKind.MENTIONS, "RetryPolicy"),
        (LinkKind.MENTIONS, "BackoffWindow"),
    )
    add(
        links,
        "core",
        (LinkKind.PROVIDES, "core"),
        (LinkKind.DEFINES, "RetryPolicy"),
        (LinkKind.DEFINES, "BackoffWindow"),
    )

    report = analyse(links)

    assert report.undeclared == ()
    assert report.declared["web"] == {"core"}


def test_a_dependency_counts_in_either_direction(links: LinkStore) -> None:
    # A shared name links both ways; a dependency is declared once and in
    # one direction. Counting only the declared direction reported the
    # reverse of every real relationship as a finding — measured, that was
    # most of what caddyserver's report contained.
    add(
        links,
        "plugin",
        (LinkKind.PROVIDES, "plugin"),
        (LinkKind.DEPENDS_ON, "host"),
        (LinkKind.DEFINES, "PluginHook"),
        (LinkKind.DEFINES, "PluginName"),
    )
    add(
        links,
        "host",
        (LinkKind.PROVIDES, "host"),
        (LinkKind.MENTIONS, "PluginHook"),
        (LinkKind.MENTIONS, "PluginName"),
    )

    assert analyse(links).undeclared == ()


def test_one_shared_name_is_not_a_relationship(links: LinkStore) -> None:
    # Every workspace has a `Config`. One name in common is the
    # definition of a coincidence.
    add(links, "a", (LinkKind.PROVIDES, "a"), (LinkKind.MENTIONS, "ConfigLoader"))
    add(links, "b", (LinkKind.PROVIDES, "b"), (LinkKind.DEFINES, "ConfigLoader"))

    assert analyse(links).used == ()


def test_a_declared_dependency_nothing_names_is_reported(links: LinkStore) -> None:
    # Dead weight in the manifest, or a dependency reached through a
    # plugin registry or a subprocess — which no name can see.
    add(links, "web", (LinkKind.PROVIDES, "web"), (LinkKind.DEPENDS_ON, "core"))
    add(links, "core", (LinkKind.PROVIDES, "core"), (LinkKind.DEFINES, "RetryPolicy"))

    assert analyse(links).unused == (("web", "core"),)


def test_spellings_meet_and_the_defining_one_is_shown(links: LinkStore) -> None:
    # The join is on a normalised key, which nobody types. A report that
    # printed `maxretries` would be showing an internal detail.
    add(
        links,
        "web",
        (LinkKind.PROVIDES, "web"),
        (LinkKind.MENTIONS, "MaxRetries"),
        (LinkKind.MENTIONS, "ReadTimeout"),
    )
    add(
        links,
        "core",
        (LinkKind.PROVIDES, "core"),
        (LinkKind.DECLARES, "max_retries"),
        (LinkKind.DECLARES, "read_timeout"),
    )

    assert analyse(links).undeclared[0].examples == ("max_retries", "read_timeout")


def test_a_workspace_with_no_manifests_says_so(links: LinkStore) -> None:
    # Zero packages makes every other number unreadable rather than
    # alarming: nothing was declared, so nothing can be undeclared.
    add(links, "a", (LinkKind.MENTIONS, "RetryPolicy"), (LinkKind.MENTIONS, "BackoffWindow"))
    add(links, "b", (LinkKind.DEFINES, "RetryPolicy"), (LinkKind.DEFINES, "BackoffWindow"))

    report = analyse(links)

    assert report.packages == 0
    assert len(report.undeclared) == 1
