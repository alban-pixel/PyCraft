# Notes for coding agents

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first: it holds the rules for branches, pull requests,
commits and what may go in the repository. In short:

- Work on a short branch cut from `main` (`feature/…`, `fix/…`, `docs/…`); never push to `main`
  directly, to someone else's branch, or with `--force`.
- The game is in `pycraft-gpu/` (Pyxel for the window, `moderngl` for the 3D). Run it with
  `python main.py` from that folder, and the tests with `python -m pytest tests`.
- Before saying a change is done: the tests pass, and the game starts and plays.
- Don't move or rename many files without the owner's go-ahead: it conflicts with work in progress.
- Never add files from Mojang (textures, sounds, models).
- Specs and plans of roadmap items: `docs/superpowers/`. Engine notes: `docs/technique.md`.
