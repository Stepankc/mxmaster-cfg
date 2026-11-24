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

## В GUI

1. **Обновить** — `pkexec` → helper `status` (устройство, DPI, SmartShift,
   HiRes, батарея). Запрос идёт вне UI-потока.
2. Меняете DPI / SmartShift / Hi-res / remap / жесты.
3. **Применить** — пишет `/etc/logid.cfg` (бэкап `*.bak.mxmaster`) +
   `systemctl restart logid` (+ soft USB wake Bolt при необходимости).
4. Если после Apply `device_count: 0` — GUI опрашивает, пока устройство
   вернётся; или **Разбудить ресивер**. Подробнее: [reconnect.ru.md](reconnect.ru.md).
5. Строка батареи обновляется ~каждые 45 с (HID++ probe без остановки `logid`).

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
