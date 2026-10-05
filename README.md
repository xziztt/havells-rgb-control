# Havells RGB Control

Local command-line control for Havells TW+RGB bulbs exposing Tuya Type-B data
points. Supports power, RGB color, brightness, tunable white, and JSON status.
The controller uses LAN commands, not the Tuya cloud API. Tested with protocol
3.5; this is not a universal driver for every Havells product.

## Install

Requires Python 3.10+ and a computer with network access to the bulb.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python bulb.py --help
```

## Find the device ID and obtain the key

### 1. Pair and discover

Pair the bulb with the **Tuya Smart** or **Smart Life** phone app. A Havells
branded app may also provision a Tuya device, but developer-account linking
support varies. Re-pairing may change both the local key and device ID.

Connect your computer to the same LAN as the bulb, then run:

```bash
.venv/bin/python -m tinytuya scan
```

Find the bulb's entry, for example:

```text
Address = 192.168.7.6  Device ID = YOUR_DEVICE_ID  Version = 3.5
```

Copy **Device ID**, address, and version. If you have several devices, identify
the bulb by turning it off at the wall, rescanning, and confirming which entry
disappears and returns after reconnection. Guest networks/client isolation can
prevent discovery. Your router's DHCP client list also helps identify its IP.

The device ID is the unique device identifier, not the retail model name or
Tuya Product ID. Discovery does **not** obtain the local encryption key.

### 2. Retrieve the local key

1. Sign into [Tuya's developer platform](https://iot.tuya.com/) (it may redirect
   to `platform.tuya.com`).
2. Create a cloud project using the **Smart Home** development method.
3. Select a data center serving your phone-app account's region.
4. In the project, open **Devices → Link Tuya App Account → Add App Account**.
5. Scan the linking QR code with your Tuya Smart/Smart Life app and authorize it.
6. Confirm the bulb appears in the project's device list. If linking succeeds
   but the list is empty, check the data center selection.
7. Ensure the project has the **IoT Core** and **Authorization** API services
   enabled/authorized as required by TinyTuya. Portal names and trial terms vary.
8. Run:

   ```bash
   .venv/bin/python -m tinytuya wizard
   ```

Enter the project's **Access ID/Client ID**, **Access Secret/Client Secret**,
data-center region code, and current device ID. Match the region to the project,
not just your physical location. The wizard saves `devices.json`, plus other
credential/response files, in your current directory.

This is a cloud-assisted setup step. Once the key is saved, this controller's
commands are local. Developer registration is not fundamentally necessary if
you retrieve the key another way; ordinary LAN scanning cannot retrieve it.
Internet-blocked operation, especially after reboot, depends on stock firmware
and should be tested separately.

## Configuration

The CLI accepts the wizard's `devices.json` list directly, or a single device
object. See `devices.example.json` for the shape:

```json
{
  "name": "Havells TW+RGB",
  "id": "YOUR_DEVICE_ID",
  "key": "YOUR_16_CHAR_KEY!",
  "ip": "192.168.7.6",
  "version": 3.5
}
```

Use the real key from the wizard; the placeholder above is not usable.
Keep this file external to the binary and out of Git. The repository ignores
the wizard's standard credential filenames. Protect your saved files:

```bash
chmod 600 devices.json
```

Defaults:
- Config: `~/devices.json`, overridden with `--config` or `HAVELLS_CONFIG`.
- Device: the only entry; if there are multiple, use `--device-id` or
  `HAVELLS_DEVICE_ID`.
- IP: configured `ip`, or automatic LAN discovery if absent. Override with
  `--ip` or `HAVELLS_IP`. A router DHCP reservation is useful.
- Protocol: configured `version`, default `3.5`.

Put connection options **before** the command:

```bash
.venv/bin/python bulb.py --config ./devices.json --ip 192.168.7.6 status
.venv/bin/python bulb.py --device-id YOUR_DEVICE_ID status --json
```

## Commands

```bash
.venv/bin/python bulb.py status
.venv/bin/python bulb.py status --json
.venv/bin/python bulb.py on
.venv/bin/python bulb.py off
.venv/bin/python bulb.py color '#ff5500'
.venv/bin/python bulb.py color '#ff5500' --brightness 40
.venv/bin/python bulb.py brightness 25
.venv/bin/python bulb.py white --temperature 50 --brightness 80
```

- Percentages are integers from **0 to 100**. Brightness `0` turns the bulb off.
- Nonzero brightness, color, and white commands turn the bulb on.
- `brightness` preserves hue/saturation in color mode. In white mode it adjusts
  white brightness. From scene/music modes it switches to white.
- `color` accepts six-digit RGB hex, with or without `#`. Without a brightness
  override, the RGB value determines HSV brightness. Black turns the bulb off.
- White temperature is **0 warm → 100 cool**, not Kelvin. The physical Kelvin
  endpoints have not been measured. Omitting temperature preserves the current
  white temperature; omitting brightness uses the saved white brightness.
- `on` preserves the bulb's saved mode and settings.
- JSON includes raw `dps` and normalized fields. `color` represents the stored
  color setting even when white mode is active; white temperature likewise
  represents the stored white setting in color mode. While off, brightness
  reports the saved setting rather than emitted light.

Success exits `0`; runtime errors exit `1`; invalid CLI syntax exits `2`.
With `--json`, runtime errors are JSON on stderr. argparse syntax errors use
its normal text format. Commands check reported state after writing; a timeout
may mean a command took effect but could not be confirmed, so query status.

## Build a Linux binary

Build on the target OS/architecture. PyInstaller is not a cross-compiler;
Linux builds may also depend on the build machine's glibc compatibility.

```bash
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m PyInstaller --clean --onefile --name bulb bulb.py
./dist/bulb --config "$HOME/devices.json" status --json
./dist/bulb color '#00ff00' --brightness 30
```

The executable is `dist/bulb`. Python is bundled; `devices.json` is **not**.
Keep the config outside `dist/` so clean builds don't remove it.

## AI integration / Python API

Use the CLI as a structured tool, or import the reusable controller:

```python
from bulb import BulbController, load_config, summarize

bulb = BulbController(load_config("~/devices.json", device_id="YOUR_DEVICE_ID"))
bulb.set_color("#ff5500", brightness=40)
print(summarize(bulb.get_status()))
```

Available methods: `get_status()`, `set_power(bool)`,
`set_brightness(percent)`, `set_color(hex_color, brightness=None)`, and
`set_white(temperature=None, brightness=None)`.
Methods return raw status; `summarize()` normalizes it. Keep model tool calls
limited to these functions. If using subprocess, pass an argument list instead
of constructing shell commands from model text. Serialize commands to the same
bulb to avoid competing writes.

## Data points

| DP | Meaning |
| --- | --- |
| 20 | Power |
| 21 | Mode (`white`, `colour`, etc.) |
| 22 | White brightness, 10–1000 |
| 23 | White temperature, 0–1000 |
| 24 | Color HSV: three four-digit hex fields, H 0–360, S/V 0–1000 |

## Troubleshooting

- **Connection/key errors:** check wall power, current IP, correct device entry,
  key and protocol. Re-pairing invalidates previous details.
- **Unavailable after power cycle:** check discovery and stock-firmware network
  behavior. An open TCP port alone doesn't guarantee authenticated access.
- **Competing connections:** close phone control apps and other local clients.
- **Cloud wizard errors:** check project API permissions, account linking,
  data center and IoT service entitlement/trial expiration.
- **Unexpected data points:** this controller intentionally checks the TW+RGB
  layout; a different bulb may need a different driver.
