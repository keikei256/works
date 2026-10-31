#!/usr/bin/env python3
"""見張り役を ~/.claude/settings.json に入れる入口。本体は /mnt/project-files/knowledge/lp-kit/見張り役/install_hooks.py。
使い方は本体と同じ（引数なし: 入れる / --check: 確かめる / --print: Setup script に貼る文）。"""
import os, sys

BODY = "/mnt/project-files/knowledge/lp-kit/見張り役/install_hooks.py"
if not os.path.exists(BODY):
    sys.exit("見張り役の本体が見つかりません: " + BODY)
os.execv(sys.executable, [sys.executable, "-I", BODY] + sys.argv[1:])
