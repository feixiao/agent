#!/usr/bin/env python3
"""重新生成实验 6-5 使用的小型合成 WAV 用例（espeak 离线 TTS）。

四个用例：两道算术题（79/42 的期望答案）+ 同句快/慢语速各一条，
覆盖「内容」与「韵律」两个维度。需要系统安装 espeak。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

UTTERANCES = {
    "boxes-79.wav": (145, 50, "A shop has twelve boxes with eight pencils in each box. It gives away seventeen pencils. How many pencils remain?"),
    "tickets-42.wav": (145, 50, "A theater sold eighteen tickets in the morning and twenty four tickets in the afternoon. How many tickets did it sell altogether?"),
    "pace-fast.wav": (260, 60, "Please send the report before lunch."),
    "pace-slow.wav": (85, 40, "Please send the report before lunch."),
}


def main() -> int:
    espeak = shutil.which("espeak")
    if not espeak:
        raise SystemExit("espeak is required to regenerate fixtures (Ubuntu: apt install espeak)")
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for filename, (speed, pitch, text) in UTTERANCES.items():
        output = FIXTURES / filename
        subprocess.run(
            [espeak, "-v", "en-us", "-s", str(speed), "-p", str(pitch), "-w", str(output), text],
            check=True,
        )
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
