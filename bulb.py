#!/usr/bin/env python3
"""Local controller for Havells TW+RGB bulbs with Tuya Type-B data points."""
import argparse
import colorsys
import json
import os
from pathlib import Path
import re
import sys
import time

import tinytuya


class ControlError(RuntimeError):
    pass


def load_config(path, device_id=None, ip=None):
    data = json.loads(Path(path).expanduser().read_text())
    devices = data if isinstance(data, list) else [data]
    if not devices or any(not isinstance(d, dict) for d in devices):
        raise ControlError("Config must be a device object or a nonempty devices.json list")
    if device_id:
        devices = [d for d in devices if d.get("id") == device_id]
    if len(devices) != 1:
        raise ControlError("Select exactly one device using --device-id")
    cfg = dict(devices[0])
    cfg["ip"] = ip or cfg.get("ip") or "Auto"
    if not cfg.get("id") or not isinstance(cfg.get("key"), str) or len(cfg["key"]) != 16:
        raise ControlError("Device needs an id and a 16-character local key")
    cfg["version"] = float(cfg.get("version", 3.5))
    return cfg


def hsv_encode(h, s, v):
    return f"{round(h * 360):04x}{round(s * 1000):04x}{round(v * 1000):04x}"


def hsv_decode(value):
    if not isinstance(value, str) or len(value) != 12:
        raise ControlError("Unexpected bulb color encoding; expected 12-character HSV")
    try:
        return int(value[:4], 16) / 360, int(value[4:8], 16) / 1000, int(value[8:], 16) / 1000
    except ValueError as exc:
        raise ControlError("Invalid HSV color reported by bulb") from exc


class BulbController:
    """Reusable local-only API. Brightness zero means off; other settings turn on."""

    def __init__(self, config, timeout=5):
        self.device = tinytuya.Device(config["id"], config["ip"], config["key"],
                                      version=config["version"])
        self.device.set_socketTimeout(timeout)
        self.device.set_socketRetryLimit(1)

    def get_status(self):
        result = self.device.status()
        if not isinstance(result, dict) or "Error" in result or not isinstance(result.get("dps"), dict):
            raise ControlError("Cannot read bulb status; check power, LAN access, IP, key, and protocol version")
        if not {"20", "21", "22", "23", "24"}.issubset(result["dps"]):
            raise ControlError("Device does not expose the expected TW+RGB data points")
        return result

    def apply(self, values):
        result = self.device.set_multiple_values(values)
        if isinstance(result, dict) and "Error" in result:
            raise ControlError("Bulb rejected the command; check key and protocol version")
        # A write acknowledgment isn't sufficient: confirm reported state.
        for _ in range(3):
            time.sleep(0.2)
            status = self.get_status()
            if all(status["dps"].get(str(k)) == v for k, v in values.items()):
                return status
        raise ControlError("Command sent, but the bulb did not confirm the requested state")

    def set_power(self, on):
        return self.apply({"20": bool(on)})

    def set_brightness(self, percent):
        check_percent(percent)
        status = self.get_status()["dps"]
        if percent == 0:
            return self.set_power(False)
        if status["21"] == "colour":
            h, s, _ = hsv_decode(status["24"])
            return self.apply({"20": True, "24": hsv_encode(h, s, percent / 100)})
        return self.apply({"20": True, "21": "white", "22": round(percent * 10)})

    def set_color(self, hex_color, brightness=None):
        rgb = parse_color(hex_color)
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        if brightness is not None:
            check_percent(brightness)
            v = brightness / 100
        if v == 0:
            return self.set_power(False)
        return self.apply({"20": True, "21": "colour", "24": hsv_encode(h, s, v)})

    def set_white(self, temperature=None, brightness=None):
        status = self.get_status()["dps"]
        values = {"20": True, "21": "white"}
        if temperature is not None:
            check_percent(temperature)
            values["23"] = round(temperature * 10)
        if brightness is not None:
            check_percent(brightness)
            values["20"] = brightness > 0
            if brightness > 0:
                values["22"] = round(brightness * 10)
        else:
            values["22"] = status["22"]
        return self.apply(values)


def check_percent(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ValueError("Percentage must be between 0 and 100")
    if 0 < value < 1:
        raise ValueError("Nonzero brightness/temperature percentages must be at least 1")


def percentage(value):
    try:
        value = int(value)
        check_percent(value)
        return value
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use an integer percentage from 0 to 100") from exc


def parse_color(value):
    value = value.removeprefix("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Color must be six hexadecimal digits, e.g. '#ff5500'")
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError("Color must be six hexadecimal digits, e.g. '#ff5500'") from exc


def summarize(status):
    dps = status["dps"]
    h, s, v = hsv_decode(dps["24"])
    rgb = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))
    return {"power": dps["20"], "mode": dps["21"],
            "brightness_percent": round(v * 100) if dps["21"] == "colour" else dps["22"] / 10,
            "white_temperature_percent": dps["23"] / 10,
            "color": "#%02x%02x%02x" % rgb, "dps": dps}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.environ.get("HAVELLS_CONFIG", str(Path.home() / "devices.json")))
    parser.add_argument("--device-id", default=os.environ.get("HAVELLS_DEVICE_ID"))
    parser.add_argument("--ip", default=os.environ.get("HAVELLS_IP"), help="IP override; default uses config or LAN discovery")
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "on", "off", "brightness", "color", "white"):
        sub = commands.add_parser(name)
        sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        if name == "brightness":
            sub.add_argument("percent", type=percentage)
        elif name == "color":
            sub.add_argument("hex_color")
            sub.add_argument("--brightness", type=percentage)
        elif name == "white":
            sub.add_argument("--temperature", type=percentage, help="0 warm to 100 cool")
            sub.add_argument("--brightness", type=percentage)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be greater than 0 and at most 60 seconds")
    try:
        if args.command == "color":
            parse_color(args.hex_color)
        cfg = load_config(args.config, args.device_id, args.ip)
        bulb = BulbController(cfg, args.timeout)
        if args.command == "status":
            status = bulb.get_status()
        elif args.command in ("on", "off"):
            status = bulb.set_power(args.command == "on")
        elif args.command == "brightness":
            status = bulb.set_brightness(args.percent)
        elif args.command == "color":
            status = bulb.set_color(args.hex_color, args.brightness)
        else:
            status = bulb.set_white(args.temperature, args.brightness)
        output = summarize(status)
        if args.json:
            print(json.dumps(output))
        else:
            print(f"Power: {'on' if output['power'] else 'off'} | Mode: {output['mode']} | "
                  f"Brightness: {output['brightness_percent']:g}% | "
                  f"White temperature: {output['white_temperature_percent']:g}% | Color: {output['color']}")
        return 0
    except (ControlError, ValueError, OSError, KeyError, TypeError) as exc:
        # Library/device failures are sanitized above; never include config contents.
        if args.json:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
