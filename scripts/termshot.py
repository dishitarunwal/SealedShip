#!/usr/bin/env python3
"""Run a shell command and save its output as a terminal-style PNG screenshot.

Usage: termshot.py <out.png> <title> <command>
The command runs through bash in the project root; its output is printed and
rendered. The exit code of the command is preserved.
"""
import datetime
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 22)
FONT_B = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 22, index=1)
BG, BAR, FG, PROMPT, DIM = "#1e1f29", "#2d2f3d", "#e6e6e6", "#50fa7b", "#8b8fa7"
ACCEPT, REJECT = "#50fa7b", "#ff5c57"
MAX_COLS, MAX_LINES = 150, 70


def colour(line):
    up = line.upper()
    if "REJECT" in up or "DENIED" in up or "ERROR" in up or "FAIL" in up or "FORBIDDEN" in up:
        return REJECT
    if "ACCEPT" in up or "VERIFIED OK" in up or " PASS" in up or "CREATED" in up.split("#")[0]:
        return ACCEPT
    return FG


def wrap(text):
    out = []
    text = "".join(c for c in text if ord(c) < 0x2E00)  # drop emoji Menlo cannot draw
    for raw in text.expandtabs(4).splitlines() or [""]:
        while len(raw) > MAX_COLS:
            out.append(raw[:MAX_COLS])
            raw = "  " + raw[MAX_COLS:]
        out.append(raw)
    if len(out) > MAX_LINES:
        out = out[: MAX_LINES - 1] + [f"... ({len(out) - MAX_LINES + 1} more lines truncated)"]
    return out


def render(out_png, title, command, output, code):
    ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    cmd_lines = wrap("$ " + command)
    lines = wrap(output.rstrip("\n"))
    char_w = FONT.getbbox("M")[2]
    line_h = 30
    width = max(1100, min(MAX_COLS, max(len(l) for l in cmd_lines + lines + [title])) * char_w + 60)
    height = 70 + line_h * (len(cmd_lines) + len(lines) + 3) + 20
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 46], fill=BAR)
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([18 + i * 28, 15, 34 + i * 28, 31], fill=c)
    d.text((120, 11), f"TrustDeploy — {title}", font=FONT_B, fill=FG)
    y = 64
    for l in cmd_lines:
        d.text((30, y), l, font=FONT_B, fill=PROMPT)
        y += line_h
    for l in lines:
        d.text((30, y), l, font=FONT, fill=colour(l))
        y += line_h
    y += line_h // 2
    d.text((30, y), f"[exit code {code}]  captured {ts}  host: local macOS", font=FONT, fill=DIM)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)


def main():
    out_png, title, command = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    proc = subprocess.run(["bash", "-c", command], cwd=ROOT, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    print(output, end="")
    render(out_png, title, command, output, proc.returncode)
    print(f"[screenshot saved: {out_png}]")
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
