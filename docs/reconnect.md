# Reconnect after apply (Bolt)

[English](reconnect.md) · [Русский](reconnect.ru.md)

After **Apply** (or profile → device), the helper writes `/etc/logid.cfg`,
restarts `logid`, and may soft-wake the Logi Bolt USB receiver (`046d:c548`).

If `device_count` is still **0**:

1. The GUI starts a background poll (~2 s, up to ~60 s) without freezing the UI.
2. Move the mouse (Easy-Switch on the Bolt channel) — often enough.
3. Or press **Wake receiver** (`wake-receiver` helper) for another soft USB reset,
   then the same poll continues.

When the device reappears, the status line is cleared/updated and the form
refreshes. Device/battery status keeps polling about every **15 s** (slider
positions are left alone). DPI / SmartShift sliders push live over D-Bus.

Helper calls run in a plain Python thread; results are applied on the GUI
thread via a queue + `QTimer` (not `QThread`+`Signal→lambda`, which can
update widgets off-thread and SIGSEGV under PySide6 / Python 3.14).
