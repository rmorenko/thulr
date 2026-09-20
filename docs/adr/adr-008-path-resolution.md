# ADR-8. Path resolution: workspace-first, XDG-fallback

- Status: Accepted
- Date: 2026-08-29
- Author: Roman Morenko (drafted with Claude)

## Context

Until this ADR the CLI hardcoded `thulr.toml` in the current working
directory and `.thulr/` next to it. That model works while thulr is
run from a Git working copy via `uv run thulr …`, but breaks the
moment the tool is distributed:

- `pipx install thulr` puts the CLI in `~/.local/bin`; the user runs
  `thulr` from any directory and gets "no thulr.toml here".
- A system install into a read-only prefix (`/usr/lib/...`) leaves
  nowhere writable for the index.
- `thulr search` in a subpackage of the project directory fails
  because CWD is not the workspace root — a usability wart compared to
  `git status`, which walks up.

Alexey raised this in PR #3 review (comment #3 on `cli.py`).

Two extremes were considered and rejected:

- **Pure workspace mode** (the status quo): a valid choice for
  `git`/`docker-compose`-style tools, but it precludes system-wide
  installation, which the roadmap already implies.
- **Pure user-scoped XDG** (one config per user, one index per user):
  breaks the multiple-workspaces-per-user pattern that motivated the
  tool — a developer wants disjoint indexes for work-monorepo,
  side-projects, and reference code.

The winner is a **hybrid**: workspace mode stays as the developer flow;
XDG paths cover system installation and from-anywhere invocation.

## Decision

1. **Path resolution is a pure module** (`thulr/paths.py`). No CLI
   concerns, no exit codes; it returns a `ConfigLocation | None` and
   the CLI decides how to complain.

1. **Four resolution modes, strict priority order:**

   1. `THULR_CONFIG` env — explicit override, wins over everything.
      A missing file under the override returns `None` (not a
      fallback): the user meant that file, silence would hide a typo.
   1. **Workspace mode** — walk from CWD up to `/` for `thulr.toml`,
      like `git` finds `.git/`. Chosen for the developer flow and to
      make subdirectory invocations work.
   1. **User mode** — `$XDG_CONFIG_HOME/thulr/config.toml`. Chosen
      for `pipx install` and other from-anywhere invocations.
   1. **System mode** — `$XDG_CONFIG_DIRS/thulr/config.toml`. Chosen
      for admin-provided defaults on shared systems.

1. **Index location follows the config's mode:**

   - Workspace/override → `.thulr/` next to the config (unchanged
     for the developer flow), isolated by directory.
   - User/system → `$XDG_DATA_HOME/thulr/<workspace-id>/`, where
     the id is `<name>-<blake2s(resolved-config-path)>` (see
     `paths.workspace_id`). The hash tail is what prevents collision
     when a user parameterizes `$XDG_CONFIG_HOME` to run several
     isolated user-mode configs that all happen to share a `name`;
     the human prefix keeps `ls ~/.local/share/thulr/` browsable.
     System prefixes are often read-only, and a shared system-wide
     config must not couple every user's index to one shared dir.

1. **Cache is separate from data.** Downloaded sentence-transformers
   models live in `$XDG_CACHE_HOME/thulr/models/`, not next to the
   index. This is per-user (not per-workspace): a MiniLM download is
   ~90 MB and the same file is reused by every workspace that picks
   the same model id, so sharing is a feature, not a bug. The
   contract is XDG-clean: `rm -rf $XDG_CACHE_HOME/thulr/` is a
   supported operation — the next run re-downloads what it needs
   without touching the index. Thulr takes control of the location
   (via `SentenceTransformer(cache_folder=...)`) instead of accepting
   HuggingFace's default `~/.cache/huggingface/hub/` so that its
   cache is namespaced and easy to clean without affecting other
   HF-based tools on the same machine.

1. **`platformdirs` is a runtime dependency.** It resolves the correct
   XDG paths on Linux, on macOS (which does not define the XDG
   variables natively but the library does the right thing), and on
   Windows (`%APPDATA%`/`%LOCALAPPDATA%`) — we get cross-platform for
   free instead of hardcoding `~/.config`.

1. **`thulr init` gains `--user` and `--force`.** Default is
   workspace-mode (unchanged UX: `thulr init myws` still writes
   `./thulr.toml`). `--user` writes `$XDG_CONFIG_HOME/thulr/ config.toml`. Both refuse to overwrite unless `--force` is passed.

## Consequences

What we owe:

- Every "config not found" message must list every path checked. A
  silent "not found" turns a UX problem into a debugging one.
- The `Config` model stays ignorant of where it came from — the
  resolver returns the location separately (`ConfigLocation`), and the
  CLI carries it through to `_build_pipeline` and `save_config`. This
  is disciplined separation of concerns; it costs one extra tuple in
  every command.
- On systems with an unusual `HOME` (containers, CI runners, some
  IDEs), tests must isolate `$HOME` and every `$XDG_*` explicitly:
  platformdirs falls back to `$HOME/.config` when `$XDG_CONFIG_HOME`
  is unset, and an unpatched HOME would leak into "hermetic" tests.

What we gain:

- `pipx install thulr` works: user runs `thulr init --user demo`,
  adds a repo, indexes, searches — no CWD dance.
- `thulr search` works from any subdirectory of the workspace.
- Read-only system install: the binary lives in `/usr/...`, state
  goes to `$HOME`. No exceptions.
- Admins can drop `/etc/xdg/thulr/config.toml` as a shared
  starting point; users override with their own file, no coordination.

Not addressed here (deliberately deferred):

- **Orphan-index cleanup.** Renaming, moving or `--force`-recreating
  a user-mode config produces a fresh `workspace-id` and leaves the
  old index dir under `$XDG_DATA_HOME/thulr/` as an orphan. Safe
  to `rm -rf` manually, but there is no `thulr prune` command yet.
  Track this if orphans accumulate in practice.
