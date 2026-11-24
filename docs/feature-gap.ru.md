# Разрыв функций: Options+ / MX Master vs mxmaster-cfg

[English](feature-gap.md) · [Русский](feature-gap.ru.md)

Чеклист возможностей Logitech Options+ / MX Master против того, что
**mxmaster-cfg** даёт на Linux (logiops **0.3.5** + helper). Статусы:

| Статус | Смысл |
|--------|-------|
| **done** | Есть в GUI (live D-Bus и/или Apply → cfg) |
| **partial** | Часть поведения Options+; с оговорками |
| **missing** | В приложении ещё нет; часто доступно через logiops/Solaar/вручную |
| **impossible** | На Linux с текущим стеком недоступно или бессмысленно |

Референс: **MX Master 3S** на **Logi Bolt** (Kubuntu). Отличия семейства — ниже.

---

## Указатель / сенсор

| Функция | Статус | Заметки |
|---------|--------|---------|
| DPI чтение/запись | **done** | Live `SetDPI` + cfg `dpi:` |
| Шаг / диапазон DPI | **partial** | Слайдер 200–8000 / 50; устройство может clamp |
| DPI Shift / dual DPI | **missing** | Нет UI «DPI пока зажато» |
| CycleDPI на кнопке/жесте | **partial** | Пресет Left / remap CycleDPI |
| Тонкая настройка сенсора | **impossible** | Через IPC logiops не отдаётся |

## MagSpeed / SmartShift

| Функция | Статус | Заметки |
|---------|--------|---------|
| SmartShift вкл/выкл | **done** | Учёт tri-state (`mode` 2/1/0) |
| Порог SmartShift | **done** | Live + cfg |
| Torque / сила трещотки | **partial** | Слайдер есть; на 3S **TorqueSupport=false** → не пишем |
| Всегда ratchet / всегда free-spin | **partial** | Приблизительно on/off + крайний threshold |
| SmartShift Enhanced `0x2111` | **missing** | Новые устройства; не подключено |

## Основное колесо

| Функция | Статус | Заметки |
|---------|--------|---------|
| Hi-res (`0x2121` hires) | **done** | Чекбокс → cfg / SetHires |
| Инверсия вертикали | **done** | `invert` |
| Divert колеса в демон | **done** | `target` |
| **Скорость скролла** как в Options+ | **partial** | **Нет** HID++ «строк на щелчок». Ближайшее: divert + слайдер `axis_multiplier` ([scroll-speed.ru.md](scroll-speed.ru.md)). Иначе KDE/libinput |
| Ощущение smooth / ratchet | **partial** | SmartShift + hires + quirks ОС; Bolt часто только low-res |
| UI состояния трещотки | **missing** | В бэкенде HID++ есть `GetRatchetState`; в GUI нет |
| Произвольные up/down actions | **partial** | Путь скорости = Axis; свободный Keypress up/down в GUI нет |

## Боковое колесо (`0x2150`)

| Функция | Статус | Заметки |
|---------|--------|---------|
| Divert / invert | **done** | |
| Горизонтальный скролл (ОС) | **done** | По умолчанию без divert |
| Пресеты left/right / громкость | **partial** | Комбо; не свободный редактор |
| Tap | **partial** | Только пресеты |
| Touch / proxy | **missing** | Writer умеет; GUI нет |
| Haptic | **impossible** | Нет в схеме logiops 0.3.5 |

## Кнопки / ремэп

| CID (spike 3S) | Роль | Статус |
|----------------|------|--------|
| `0x50` / middle | СКМ | **missing** | Обычно middle ОС |
| `0x52` | доп. | **missing** | Remappable на spike; нет ряда в GUI |
| `0x53` | Back | **partial** | Комбо Forward/Back только меняет F/B |
| `0x56` | Forward | **partial** | То же |
| `0xc3` | Gesture | **partial** | Сетка пресетов |
| `0xc4` | Mode / SmartShift | **partial** | ToggleSmartShift в примерах; не полный picker |
| `0xd7` | доп. | **missing** | Remappable; нет GUI |
| OnInterval / Axis / RawXY жесты | **missing** | Только OnRelease пресеты |
| Чувствительность жеста | **missing** | |

## Батарея / питание

| Функция | Статус | Заметки |
|---------|--------|---------|
| % батареи | **done** | HID++ `0x1004` (+ UPower/sysfs) |
| Зарядка | **partial** | Если probe отдаёт |
| Уведомление о разряде | **missing** | Только опрос в GUI |
| Power insights / cloud | **impossible** / **missing** | |

## Связь

| Функция | Статус | Заметки |
|---------|--------|---------|
| Logi Bolt | **partial** | Работает; после restart часто нужен motion / soft USB wake |
| Bluetooth | **partial** | logiops умеет; меньше smoke |
| UI канала Easy-Switch | **missing** | Только физический переключатель |
| Pairing Bolt | **missing** | Solaar / logitechctl; вне MVP |
| ChangeHost | **missing** | Тип в схеме есть; GUI нет |

## Flow / десктоп

| Функция | Статус | Заметки |
|---------|--------|---------|
| Logitech Flow | **impossible** | Проприетарно; нет Linux Options+ Flow |
| Actions Ring (MX Master 4) | **impossible** / **missing** | Железо + Options+; Linux-эксперименты вне scope |
| App-specific профили | **missing** | Явно **вне MVP** (только именованные на диске) |
| Cloud / аккаунт Logi | **impossible** | |

## Прошивка / прочее

| Функция | Статус | Заметки |
|---------|--------|---------|
| Обновление прошивки | **impossible** | Не через logiops |
| Onboard-профили UI | **missing** | Приложение пишет `/etc/logid.cfg` |
| Конфликт Solaar/OpenLogi | **done** | Кнопка проверки |

## Отличия 3 / 3S / 4

| Тема | MX Master 3 | MX Master 3S | MX Master 4 |
|------|-------------|--------------|-------------|
| Клики / сенсор | — | Тише / обновления | + Ring |
| BT product id (пример) | класс `b023` | `b034` | Новые PID — проверить |
| Torque SmartShift | Часто нет в IPC | TorqueSupport=false на spike | Проверить устройство |
| Actions Ring | Нет | Нет | Да (Options+); дыра на Linux |
| Имя в logiops | `"MX Master 3"` | `"MX Master 3S"` | Нужен `device.name` |
| Hi-res на Bolt | Лимиты ядра/Bolt | То же (BT лучше для hi-res) | Проверить |

Имя в cfg должно совпадать со строкой discovery logiops.

## Главные дыры (на потом)

1. **Полный редактор действий по всем CID**
2. **App-aware профили** (post-MVP)
3. **Bluetooth smoke + Easy-Switch/host UI**
4. **Thumb touch/proxy + свободный редактор**
5. **SmartShift Enhanced / torque** где поддерживается
6. **Flow / Actions Ring / прошивка** — в основном **impossible**

## Ближайший аналог скорости скролла Options+

Divert + Axis `scroll_multiplier` — [scroll-speed.ru.md](scroll-speed.ru.md).
Без divert: **Скорость прокрутки** в KDE / libinput.
