# Havells RGB Control

> **Warning:** This is a proof of concept (POC), not production-ready software.

Control Havells TW+RGB bulbs locally: power, color, brightness, and tunable white.
Requires Python 3.10+ and access to the bulb's LAN. Tested with Tuya protocol 3.5.

## 1. Install

Clone the repository, then install:

```bash
git clone https://github.com/xziztt/havells-rgb-control.git
cd havells-rgb-control
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

This installs [TinyTuya](https://github.com/jasonacox/tinytuya), the Python library
used for discovery, key retrieval, and local bulb control. No separate install is needed.

## 2. Find the device ID

Pair the bulb in **Tuya Smart** or **Smart Life**, then connect your computer to
the same network and run:

```bash
.venv/bin/python -m tinytuya scan
```

Note the bulb's **Device ID**, **IP address**, and **Version**. Scanning does not
retrieve the local key.

## 3. Link the Tuya project and get the key

1. Create an account or sign into [Tuya's developer platform](https://iot.tuya.com/)
   (it may redirect to `platform.tuya.com`).
2. Open **Cloud → Development / Project Management → Create Cloud Project**.
   Choose **Smart Home** and a data center serving your phone-app account's region.
3. Inside the project, open **Devices → Link Tuya App Account → Add App Account**
   to display a QR code.
4. Open the QR scanner in **Tuya Smart/Smart Life** (usually under **Me** or **+**),
   using the account containing your bulb. Scan the code and approve the link.
5. Refresh the project's device list and confirm the bulb appears. Under
   **Service API**, enable/authorize **IoT Core** and **Authorization** if required.
6. Run:

   ```bash
   .venv/bin/python -m tinytuya wizard
   ```

Find **Access ID/Client ID** and **Access Secret/Client Secret** on the project's
**Overview** page. Enter these in the wizard, along with the project's
**data-center region code** and the bulb's **Device ID** from the scan or device list.
The wizard saves the local key in `devices.json` in your current directory.
If no devices appear, check the project's data center. Portal labels can vary.

Keep credentials private. Re-pairing can change the key and device ID. The cloud
is used for this setup step; controller commands use the LAN.

## 4. Configure and use

Use the wizard's `devices.json` directly. It contains the device `id` and `key`;
you can add `ip` and `version` as shown in `devices.example.json`.

```bash
chmod 600 devices.json
.venv/bin/python bulb.py --config ./devices.json status --json
.venv/bin/python bulb.py --config ./devices.json on
.venv/bin/python bulb.py --config ./devices.json off
.venv/bin/python bulb.py --config ./devices.json color '#ff5500' --brightness 40
.venv/bin/python bulb.py --config ./devices.json brightness 25
.venv/bin/python bulb.py --config ./devices.json white --temperature 50 --brightness 80
```

The default config is `~/devices.json`. For multiple devices, add
`--device-id YOUR_DEVICE_ID` before the command. Override the address with
`--ip BULB_IP`; otherwise it uses the configured IP or LAN discovery.

Brightness is **0–100%**; `0` turns off. White temperature is **0 warm → 100 cool**,
not Kelvin. Add `--json` for machine-readable output.

## Build a Linux binary

```bash
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m PyInstaller --clean --onefile --name bulb bulb.py
./dist/bulb --config ./devices.json status --json
```

The executable is `dist/bulb`. Build on the target OS/architecture; keep your
credential file external to the binary and out of Git.
