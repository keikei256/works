#!/usr/bin/env python3
"""逆算の見張り役の入口。本体は /mnt/project-files/knowledge/lp-kit/見張り役/improve_gate.py
（プロジェクトの共有フォルダはどのスレッドにもあり、リポジトリが付いていないスレッドでも動くため。2026-10-31）。"""
import os, sys

BODY = "/mnt/project-files/knowledge/lp-kit/見張り役/improve_gate.py"
if os.path.exists(BODY):
    os.execv(sys.executable, [sys.executable, "-I", BODY] + sys.argv[1:])
