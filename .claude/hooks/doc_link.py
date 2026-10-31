#!/usr/bin/env python3
"""Claude Docs の Doc が、どの作品の文章かを登録する（見張り役 improve_gate.py が使う）。
使い方: python3 -I /home/user/works/.claude/hooks/doc_link.py <Doc のリンクか id> <portfolio/作品フォルダ名 | sales/作品フォルダ名 | なし>
- 文章案・構成案・見出し案の Doc は必ず作品に結びつける（「なし」は作品と関係ない Doc だけ）
- 登録は knowledge/lp-kit/公開の対応.json に入り、仕組みの変更記録.jsonl に残る（週1回の点検でユーザーに報告する）
"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import improve_gate as g

if len(sys.argv) != 3:
    sys.exit(__doc__)
did, key = g.norm_doc(sys.argv[1]), sys.argv[2].strip().strip("/")
if key != "なし":
    if not key.startswith(("portfolio/", "sales/")) or key.count("/") != 1 or not os.path.isdir(os.path.join(g.PF_REAL, key)):
        sys.exit("作品フォルダが見つかりません: /mnt/project-files/" + key + "/（portfolio/名前 か sales/名前 で書く）")
old = g.urlmap().get("doc:" + did)
if old and old != key:
    sys.exit("この Doc はもう " + old + " に結びついています。変えるときはユーザーに理由を伝えてから 公開の対応.json を直してください。")
g.save_urlmap({"doc:" + did: key})
with open(g.CHANGE_LOG, "a", encoding="utf-8") as f:
    f.write(json.dumps({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                        "path": "doc:" + did, "doc_link": key}, ensure_ascii=False) + "\n")
print("登録しました: Doc " + did + " → " + key)
