#!/usr/bin/env python3
"""Doc を作品に結びつける入口。本体は /mnt/project-files/knowledge/lp-kit/見張り役/doc_link.py。"""
import os, sys

BODY = "/mnt/project-files/knowledge/lp-kit/見張り役/doc_link.py"
if not os.path.exists(BODY):
    sys.exit("見張り役の本体が見つかりません: " + BODY)
os.execv(sys.executable, [sys.executable, "-I", BODY] + sys.argv[1:])
