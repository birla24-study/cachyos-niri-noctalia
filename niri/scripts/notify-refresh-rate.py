#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import sys
import time

running = True

def handle_signal(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def send_notification(summary, body):
    # Try Noctalia IPC first
    try:
        res = subprocess.run(
            ["noctalia", "msg", "notification-show", summary, body],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return
    except Exception:
        pass

    # Fallback to standard notify-send
    try:
        subprocess.run(
            ["notify-send", "-a", "Noctalia", "-i", "video-display", summary, body],
            check=False,
            timeout=5,
        )
    except Exception:
        pass

def get_outputs():
    try:
        res = subprocess.run(
            ["niri", "msg", "-j", "outputs"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    return {}

def check_outputs(last_states):
    outputs = get_outputs()
    if not outputs:
        return

    for name, info in outputs.items():
        curr_idx = info.get("current_mode")
        modes = info.get("modes", [])
        if curr_idx is not None and curr_idx < len(modes):
            mode = modes[curr_idx]
            w = mode.get("width")
            h = mode.get("height")
            refresh = mode.get("refresh_rate", 0) / 1000.0
            is_75hz = (w == 1280 and h == 1024 and 74.0 <= refresh <= 76.5)

            prev_state = last_states.get(name)
            last_states[name] = is_75hz

            # Trigger notification only when 75Hz at 1280x1024 is newly detected/selected
            if is_75hz and prev_state is not True:
                model = info.get("model") or info.get("make") or name
                send_notification(
                    "Display Configuration",
                    f"{model} ({name}) auto-selected 75 Hz (1280x1024 @ {refresh:.2f} Hz)"
                )

def main():
    # Allow display server and noctalia to stabilize on startup
    time.sleep(1.5)

    last_states = {}
    check_outputs(last_states)

    while running:
        try:
            proc = subprocess.Popen(
                ["niri", "msg", "-j", "event-stream"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            while running:
                line = proc.stdout.readline()
                if not line:
                    break
                check_outputs(last_states)
            proc.terminate()
            proc.wait()
        except Exception:
            pass

        if running:
            time.sleep(2)

if __name__ == "__main__":
    main()
