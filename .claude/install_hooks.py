#!/usr/bin/env python3
"""見張り役（.claude/hooks/improve_gate.py）を、このコンテナの Claude Code に確実に読み込ませる。

なぜ要るか（2026-10-31 確認）: プロジェクトのスレッドでは、リポジトリの .claude/settings.json のフックは
読み込まれない（https://code.claude.com/docs/en/settings.md#settings-in-cloud-sessions）。
ユーザー設定 ~/.claude/settings.json のフックは読み込まれ、書いたその場から効く（実地テスト済み）。
そこで、ここから ~/.claude/settings.json に見張り役を書き足す。何度実行しても同じ結果になる。

使い方:
  python3 -I /home/user/works/.claude/install_hooks.py          入れる（入っていれば何もしない）
  python3 -I /home/user/works/.claude/install_hooks.py --check  入っているかだけ確かめる（無ければ終了コード1）
  python3 -I /home/user/works/.claude/install_hooks.py --print  環境の「Setup script」に貼る文を表示する
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.expanduser("~/.claude/settings.json")
MARK = "improve_gate.py"
# リポジトリが無いコンテナでは何もしない（ほかの作業を止めない）。あれば必ず見張り役を通す
CMD = ('for f in /home/user/works/.claude/hooks/improve_gate.py "$CLAUDE_PROJECT_DIR/.claude/hooks/improve_gate.py"; '
       'do [ -f "$f" ] && exec python3 -I "$f"; done; exit 0')
PRE = "Edit|Write|MultiEdit|NotebookEdit|Bash|Artifact|Agent|mcp__Claude_Docs__.*"
POST = "Artifact|Bash|Agent|mcp__hearthbot__post_message|mcp__Claude_Docs__.*"
WANT = {"PreToolUse": PRE, "PostToolUse": POST}


def load():
    try:
        return json.load(open(SETTINGS, encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        # 読めない設定は残しておき、作り直す
        os.replace(SETTINGS, SETTINGS + ".broken")
        return {}


def installed(s):
    hooks = s.get("hooks") or {}
    for ev, matcher in WANT.items():
        ok = any(g.get("matcher") == matcher and any(MARK in (h.get("command") or "") for h in g.get("hooks") or [])
                 for g in hooks.get(ev) or [])
        if not ok:
            return False
    return True


def install():
    s = load()
    if installed(s):
        print("見張り役: 入っています（" + SETTINGS + "）")
        return
    hooks = s.setdefault("hooks", {})
    for ev, matcher in WANT.items():
        groups = [g for g in hooks.get(ev) or []
                  if not any(MARK in (h.get("command") or "") for h in g.get("hooks") or [])]  # 古い形は入れ替える
        groups.append({"matcher": matcher, "hooks": [{"type": "command", "command": CMD}]})
        hooks[ev] = groups
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    tmp = SETTINGS + ".tmp"
    json.dump(s, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, SETTINGS)
    print("見張り役: 入れました（" + SETTINGS + "）。この後の Edit / Write / Bash / Artifact / Docs から効きます")


def setup_script():
    s = {"hooks": {ev: [{"matcher": m, "hooks": [{"type": "command", "command": CMD}]}] for ev, m in WANT.items()}}
    return ("mkdir -p ~/.claude\ncat > ~/.claude/settings.json <<'EOF'\n"
            + json.dumps(s, ensure_ascii=False, indent=1) + "\nEOF\n")


if __name__ == "__main__":
    if "--check" in sys.argv:
        ok = installed(load())
        print("見張り役: " + ("入っています" if ok else "入っていません。python3 -I " + os.path.abspath(__file__) + " を実行してください"))
        sys.exit(0 if ok else 1)
    if "--print" in sys.argv:
        print(setup_script(), end="")
        sys.exit(0)
    install()
