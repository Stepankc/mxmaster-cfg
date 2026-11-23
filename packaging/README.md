# Debian / Ubuntu packaging sketch

Цель: `.deb` для семейства Debian/Ubuntu (Kubuntu как стенд разработки).

## Depends: logiops

В `debian/control`:

```
Depends: …, logiops (>= 0.3) | logiops-bolt-tbd
```

- На Kubuntu/Ubuntu 26.04 стенде Stepan’а: **logiops 0.3.5 из apt** — достаточно
  (Bolt + D-Bus). Обычный `Depends: logiops (>= 0.3)`.
- Дополнительно для MVP GUI: `policykit-1` (pkexec), `python3-pyside6.qtwidgets`.
- Helper + polkit policy **обязательны** (stock D-Bus policy — root-only).

## Сборка (позже)

```bash
# из корня будущего Debian source package:
dpkg-buildpackage -us -uc
```

Сейчас дерево — только эскиз рядом с Python-скелетом, не полноценный
`debian/` source package.

## Связанные артефакты в дереве

| Путь | Назначение |
|------|------------|
| `../udev/99-mx-master-hidraw.rules` | hidraw + uinput |
| `../systemd/NOTES.md` | system `logid` vs user units |
