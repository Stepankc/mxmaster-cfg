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

Application Menu entry (local tree): see [desktop.md](desktop.md) —
`scripts/install-desktop.sh` points at this `run.sh` with an absolute path.

## In the GUI

1. On launch the GUI loads device status once (sliders sync from device).
   Status / battery keep polling ~every 15 s (does not overwrite your sliders).
2. **DPI / SmartShift** use sliders and apply **live** over D-Bus (debounced).
3. **Apply to cfg** writes `/etc/logid.cfg` + `systemctl restart logid` for
   gestures, remap, hi-res, thumb (+ soft USB wake if needed).
4. If `device_count: 0` after apply — GUI polls until the device returns;
   or use **Wake receiver**. Details: [reconnect.md](reconnect.md).
5. Optional flat **Re-read** under device status if you need to pull sliders
   from the device again.

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
