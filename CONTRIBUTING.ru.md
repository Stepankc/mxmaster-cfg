# Участие в разработке

[English](CONTRIBUTING.md) · [Русский](CONTRIBUTING.ru.md)

## Область

Проект — обёртка над **logiops** для линейки MX Master на Debian/Ubuntu.
Предпочтительны тонкие адаптеры, а не clean-room HID++. Не копируйте
чужой LogiOps GUI без лицензии.

## Dev setup

См. [docs/install.ru.md](docs/install.ru.md) и [docs/run.ru.md](docs/run.ru.md).

```bash
./run.sh
# опционально
PYTHONPATH=src python3 -m pytest tests/
```

## Коммиты

- Сообщения коммитов — **на английском**
- Лицензия: `GPL-3.0-or-later` где уместно

## Документация

Пользовательские docs — двуязычные (`*.md` + `*.ru.md`) со ссылками EN↔RU сверху.
