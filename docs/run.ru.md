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

## В GUI

1. **Обновить** — `pkexec` → helper `status` (устройство, DPI, SmartShift, HiRes).
2. Меняете DPI / SmartShift / Hi-res / remap / жесты.
3. **Применить** — пишет `/etc/logid.cfg` (бэкап `*.bak.mxmaster`) +
   `systemctl restart logid` (+ soft USB wake Bolt при необходимости).

Если на Bolt `device_count: 0` — **пошевелите мышь** и снова Обновить.

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
