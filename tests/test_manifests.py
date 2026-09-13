"""What a repository declares about itself, read from its build files.

The one edge in the store that is a statement by the people who wrote
the code rather than an inference about it — which is what lets it tell
a name two repositories happen to share from a dependency they actually
have.
"""

from pathlib import Path

from wsindex.ingest.manifests import read_manifests


def test_a_go_module_names_itself_and_what_it_requires(tmp_path: Path) -> None:
    # Both spellings of `require`, because go.mod uses the block form for
    # more than one and the bare form for exactly one.
    (tmp_path / "go.mod").write_text(
        "module github.com/caddyserver/caddy/v2\n\n"
        "require github.com/caddyserver/certmagic v0.20.0\n\n"
        "require (\n\tgo.uber.org/zap v1.27.0\n\tgithub.com/google/uuid v1.6.0\n)\n"
    )

    found = read_manifests(tmp_path)

    assert found.provides == {"github.com/caddyserver/caddy/v2"}
    assert found.depends == {
        "github.com/caddyserver/certmagic",
        "go.uber.org/zap",
        "github.com/google/uuid",
    }


def test_npm_dev_and_peer_dependencies_all_count(tmp_path: Path) -> None:
    # A build-time dependency is still a declaration that this repository
    # may legitimately name that package.
    (tmp_path / "package.json").write_text(
        '{"name": "gql.tada", "dependencies": {"@0no-co/graphql.web": "1"},'
        ' "devDependencies": {"vitest": "2"}, "peerDependencies": {"typescript": "5"}}'
    )

    found = read_manifests(tmp_path)

    assert found.provides == {"gql.tada"}
    assert found.depends == {"@0no-co/graphql.web", "vitest", "typescript"}


def test_a_python_dependency_is_read_without_its_version_range(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "wsindex"\ndependencies = ["httpx>=0.28,<1", "typer"]\n'
    )

    found = read_manifests(tmp_path)

    assert found.provides == {"wsindex"}
    assert found.depends == {"httpx", "typer"}


def test_a_project_reference_is_named_by_its_file(tmp_path: Path) -> None:
    # MSBuild points at a path; the project it means is that file's stem,
    # which is also how the referenced project names itself.
    project = tmp_path / "src" / "ILSpy"
    project.mkdir(parents=True)
    (project / "ILSpy.csproj").write_text(
        "<Project><ItemGroup>"
        '<ProjectReference Include="..\\\\AvalonEdit\\\\AvalonEdit.csproj" />'
        '<PackageReference Include="Newtonsoft.Json" Version="13.0" />'
        "</ItemGroup></Project>"
    )

    found = read_manifests(tmp_path)

    assert found.provides == {"ILSpy"}
    assert found.depends == {"AvalonEdit", "Newtonsoft.Json"}


def test_a_repository_never_depends_on_itself(tmp_path: Path) -> None:
    # A monorepo's packages reference each other, and an edge from a
    # repository to itself answers no question anybody asks.
    (tmp_path / "package.json").write_text('{"name": "a", "dependencies": {"a": "1", "b": "2"}}')

    assert read_manifests(tmp_path).depends == {"b"}


def test_a_lock_file_sized_manifest_is_not_read(tmp_path: Path) -> None:
    # `package-lock.json` is megabytes of the transitive world. What a
    # repository *declares* is the fact worth having; what it resolves to
    # is noise that would swamp every other name in the store.
    (tmp_path / "package.json").write_text(
        '{"name": "big", "dependencies": {"x": "' + "9" * 600_000 + '"}}'
    )

    assert read_manifests(tmp_path) == read_manifests(tmp_path / "nothing")


def test_a_repository_with_no_manifest_is_not_an_error(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello")

    found = read_manifests(tmp_path)

    assert not found.provides and not found.depends
