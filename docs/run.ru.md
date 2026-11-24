# Запуск

[English](run.md) · [Русский](run.ru.md)

## One-click

```bash
cd /path/to/mxmaster-cfg
./run.sh
```

`run.sh` выставляет `PYTHONPATH=src/` и запускает `python3 -m mxmaster_cfg`.

Эквивалент:

```bash
PYTHONPATH=src python3 -m mxmaster_cfg
```

Ярлык в меню приложений (локальное дерево): [desktop.ru.md](desktop.ru.md) —
`scripts/install-desktop.sh` указывает на этот `run.sh` абсолютным путём.

## Привилегированный helper / пароль

Статус, live DPI/SmartShift, Apply и wake идут через `pkexec` →
`mxmaster-cfg-helper`. После `scripts/install-helper.sh` (или `.deb`) активная
локальная сессия `sudo`/`admin` **не** получает диалог пароля на каждый опрос
раз в 15 с — см. [install.ru.md](install.ru.md#как-работает-аутентификация).

Если пароль всё ещё спрашивают каждые несколько минут — переустановите helper
(чтобы появился `10-mxmaster-cfg.rules`) и один раз выйдите/войдите.

## В GUI

1. При запуске GUI сам читает устройство (слайдеры подтягиваются один раз).
   Статус / батарея дальше опрашиваются ~каждые 15 с (слайдеры не затираются).
2. **DPI / SmartShift** — слайдеры, live по D-Bus (с короткой задержкой).
3. **Применить в cfg** пишет `/etc/logid.cfg` + restart `logid` для жестов,
   remap, hi-res, thumb (+ soft USB wake при необходимости).
4. Если после Apply `device_count: 0` — GUI опрашивает, пока устройство
   вернётся; или **Разбудить ресивер**. Подробнее: [reconnect.ru.md](reconnect.ru.md).
5. Плоская кнопка **Перечитать** в блоке устройства — только если нужно снова
   подтянуть слайдеры с устройства.

## Dry-run cfg без применения

```bash
PYTHONPATH=src python3 -m mxmaster_cfg.adapter.logiops_cfg \
  --profile examples/profiles/mx-master-3s-default.yaml \
  --out /tmp/logid.cfg
```

## Скриншоты

- MVP DPI: `media/mvp-slice/main-window.png`
- SmartShift + жесты: `media/smartshift-gestures/main-window.png`
- Hi-res scroll: `media/hires-scroll/main-window.png`
