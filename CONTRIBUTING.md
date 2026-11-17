# Contributing to PyCraft

Two people work on PyCraft, each with a coding agent. These rules keep `main` playable and stop
the work from drifting apart on long-lived branches.

## Branches

- **`main` is always playable.** Everything else starts from it and comes back to it.
- **One short branch per change**, cut from an up-to-date `main`: `feature/<name>`, `fix/<name>`,
  `docs/<name>`. Keep it to a few days; if it lasts longer, merge `main` into it often.
- **Merge through a pull request**, even when you merge it yourself: the other person sees what
  changed, and the tests run on it. Then delete the branch.
- **Never push to someone else's branch**, and never force-push to `main`.
- A retired branch is kept as a tag, `archive/<name>`, before it is deleted, so nothing is lost
  (`git switch -c <name> archive/<name>` brings it back).
- Moving or renaming many files conflicts with every branch in progress: announce it first, and
  do it when no one has unmerged work.

## Before a pull request

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m pycraft
```

The tests must pass, and the game must start and play: walk, fly, break and place a block, open
the menus. Say in the pull request what you checked, and what you could not.

## Commits

- A short subject in the imperative ("Add a slider for the field of view"), then what changed and
  why, and how it was checked.
- One change per commit when you can; don't mix a move of files with changes to their content.

## Content

- **No file from Mojang** in the repository: texture packs are read from where the player keeps
  them, never copied here (see `docs/roadmap.md`).
- Designs and plans of a roadmap item go in `docs/superpowers/specs/` and
  `docs/superpowers/plans/`; how the engine works goes in `docs/technique.md`; what a player sees
  goes in `README.md`.
