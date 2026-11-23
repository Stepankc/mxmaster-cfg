# Run

[English](run.md) · [Русский](run.ru.md)

## One-click launcher

```bash
cd /path/to/mxmaster-cfg
./run.sh
```

`run.sh` sets `PYTHONPATH` to `src/` and starts `python3 -m mxmaster_cfg`.

Equivalent:

```bash
PYTHONPATH=src python3 -m mxmaster_cfg
```

## In the GUI

1. **Refresh** — `pkexec` → helper `status` (device, DPI, SmartShift, HiRes).
2. Change DPI / SmartShift / Hi-res / remap / gestures.
3. **Apply** — writes `/etc/logid.cfg` (backup `*.bak.mxmaster`) +
   `systemctl restart logid` (+ soft USB wake for Bolt if needed).

If status shows `device_count: 0` on Bolt, **move the mouse**, then Refresh again.

## Dry-run cfg without applying

```bash
PYTHONPATH=src python3 -m mxmaster_cfg.adapter.logiops_cfg \
  --profile examples/profiles/mx-master-3s-default.yaml \
  --out /tmp/logid.cfg
```

## Screenshots

- MVP DPI slice: `media/mvp-slice/main-window.png`
- SmartShift + gestures: `media/smartshift-gestures/main-window.png`
- Hi-res scroll: `media/hires-scroll/main-window.png`
