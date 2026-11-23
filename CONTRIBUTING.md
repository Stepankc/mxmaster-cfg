# Contributing

[English](CONTRIBUTING.md) · [Русский](CONTRIBUTING.ru.md)

## Scope

This project wraps **logiops** for the MX Master lineup on Debian/Ubuntu.
Prefer thin adapters over a clean-room HID++ stack. Do not copy unlicensed
third-party LogiOps GUI code.

## Dev setup

See [docs/install.md](docs/install.md) and [docs/run.md](docs/run.md).

```bash
./run.sh
# optional tests
PYTHONPATH=src python3 -m pytest tests/
```

## Commit style

- Commit messages in **English**
- Keep Chrome/Qt assumptions compatible with the documented stack
- License headers: `GPL-3.0-or-later` where applicable

## Docs

User-facing docs are bilingual (`*.md` + `*.ru.md`). Keep cross-links at the top.
