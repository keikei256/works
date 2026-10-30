#!/usr/bin/env python3
"""直すときの関門（逆算アプローチ）の見張り役。2026-10-30 ユーザー指示:
「改善は目標から逆算して足りないところを埋める。確実に実行される仕組みにして」

一度ユーザーに見せた制作物（Artifact で公開した・スレッドに添付した・関門導入時に登録した）を直すときは、
その作品の review/ に「逆算*.md」を、最後に見せたあとに書いておかないと、
Edit / Write / Bash / Artifact のどれで直そうとしても止める。

作品の単位: /mnt/project-files/portfolio/<名前>/ と /mnt/project-files/sales/<名前>/。
公開ページ（このリポジトリ）は /mnt/project-files/portfolio/公開ページ/ を作品フォルダとして扱う。
逆算メモの中身: 「## 目標」に一流の見本URL 2件以上、「## 差」「## 埋め方」に「- 」の行を3つ以上。前のメモの写しは不可。
見せた記録: 作品の review/関門記録.jsonl（publish.py とこの見張り役が書く）。
"""
import datetime, glob, hashlib, json, os, re, sys

PF = "/mnt/project-files"
PF_REAL = os.path.realpath(PF)
REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SITE_WORK = os.path.join(PF_REAL, "portfolio", "公開ページ")
KINDS = ("portfolio", "sales")
# 仕組みそのもの。書き換えは止めないが、仕組みの変更記録.jsonl に残して週1回の点検でユーザーに報告する
PROTECTED = [os.path.join(REPO, ".claude"),
             os.path.join(PF_REAL, "knowledge", "lp-kit", "gate.py"),
             os.path.join(PF_REAL, "knowledge", "lp-kit", "publish.py"),
             os.path.join(PF_REAL, "knowledge", "lp-kit", "audit.py"),
             os.path.join(PF_REAL, "knowledge", "lp-kit", "check.js")]


def real(p):
    if not p:
        return ""
    p = os.path.expanduser(str(p))
    if not os.path.isabs(p):
        p = os.path.join(os.getcwd(), p)
    d, b = os.path.split(os.path.abspath(p))
    while d and not os.path.exists(d) and d != "/":  # まだ無いファイルも親で解決する
        d, b2 = os.path.split(d)
        b = os.path.join(b2, b)
    return os.path.join(os.path.realpath(d), b)


def work_of(path):
    """制作物なら (作品フォルダ, review内か) を返す。制作物でなければ None"""
    r = real(path)
    if r == REPO or r.startswith(REPO + os.sep):
        rel = r[len(REPO):].lstrip(os.sep)
        if rel.startswith(".git") or rel.startswith(".claude"):
            return None
        return SITE_WORK, False
    for k in KINDS:
        base = os.path.join(PF_REAL, k) + os.sep
        if r.startswith(base):
            parts = r[len(base):].split(os.sep)
            if len(parts) < 2 or not parts[0]:
                return None  # 直下のファイル（README など）は作品ではない
            return os.path.join(PF_REAL, k, parts[0]), (len(parts) > 2 and parts[1] == "review")
    return None


def records(w):
    rec = os.path.join(w, "review", "関門記録.jsonl")
    if not os.path.exists(rec):
        return []
    out = []
    for l in open(rec, encoding="utf-8"):
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def section(text, head):
    m = re.search(r"^##\s*" + head + r"[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1) if m else None


def memo_problem(w):
    """逆算メモが足りなければ理由を返す。見せたことのない作品・十分なメモがあれば None"""
    rows = records(w)
    if not rows:
        return None
    last = max(datetime.datetime.fromisoformat(r["at"]).timestamp() for r in rows)
    memos = sorted(glob.glob(os.path.join(w, "review", "*逆算*.md")), key=os.path.getmtime)
    new = [f for f in memos if os.path.getmtime(f) > last]
    name = os.path.relpath(w, PF_REAL)
    head = (f"【逆算の関門】{name} は一度見せた制作物です。直す前に {name}/review/逆算_<日付>.md を書いてください。"
            "今の版をいじるのではなく、①一流の完成形（目標）を先に集めて見る ②今と並べて差を言葉にする ③差を埋める方法を決める。")
    if not new:
        return head + " 最後に見せた後の逆算メモがありません。"
    t = open(new[-1], encoding="utf-8").read()
    errs = []
    goal, gap, fill = section(t, "目標"), section(t, "差"), section(t, "埋め方")
    if goal is None or len(set(re.findall(r"https?://[^\s)|>\]]+", goal))) < 2:
        errs.append("「## 目標」に一流の見本のURLが2件以上ない")
    for n, body in (("差", gap), ("埋め方", fill)):
        if body is None or len(re.findall(r"^\s*[-・*]\s*\S", body, re.M)) < 3:
            errs.append(f"「## {n}」に「- 」の行が3つ以上ない")
    old = [f for f in memos if f not in new]
    if old and gap is not None:
        norm = lambda s: re.sub(r"\s+", "", s or "")
        for f in old:
            if norm(section(open(f, encoding="utf-8").read(), "差")) == norm(gap):
                errs.append(f"「## 差」が前のメモ {os.path.basename(f)} の写し")
    if errs:
        return head + " メモ " + os.path.basename(new[-1]) + " の不足: " + "／".join(errs)
    return None


def protected(path):
    r = real(path)
    return any(r == p or r.startswith(p + os.sep) for p in PROTECTED)


def sha(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except Exception:
        return ""


def gate_out(path):
    """publish.py が作った公開用フォルダなら、その記録を返す"""
    f = os.path.join(os.path.dirname(real(path)), ".gate.json")
    if os.path.exists(f):
        try:
            return json.load(open(f, encoding="utf-8"))
        except Exception:
            return None
    return None


URLMAP = os.path.join(PF_REAL, "knowledge", "lp-kit", "公開の対応.json")


def urlmap():
    try:
        return json.load(open(URLMAP, encoding="utf-8"))
    except Exception:
        return {}


CHANGE_LOG = os.path.join(PF_REAL, "knowledge", "lp-kit", "仕組みの変更記録.jsonl")


def log_change(p):
    try:
        with open(CHANGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                "path": real(p), "cwd": os.getcwd()}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def deny(msg):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": msg}}, ensure_ascii=False))
    sys.exit(0)


def ask(msg):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "ask",
                                             "permissionDecisionReason": msg}}, ensure_ascii=False))
    sys.exit(0)


def check_paths(paths):
    for p in paths:
        if protected(p):
            # 2026-10-30 ユーザー「確認画面を出さなくてもよい」。止めずに、書き換えたことを記録に残す（週1回の点検でユーザーに報告する）
            log_change(p)
    for p in paths:
        w = work_of(p)
        if w and not w[1]:
            m = memo_problem(w[0])
            if m:
                deny(m)


SHELL_WRITE = re.compile(r"(>|\btee\b|\bsed\b[^|;&]*\s-i|\bcp\b|\bmv\b|\brm\b|\brsync\b|\btruncate\b|\bdd\b|\binstall\b|\bln\b|"
                         r"\bpatch\b|\bgit\s+(checkout|restore|apply|reset|stash|mv|rm)\b|\bunzip\b|\btar\b|\bchmod\b|\btouch\b|\bconvert\b|\bmagick\b)")
CODE_WRITE = re.compile(r"(open\([^)]*['\"][wax+]|write_text|write_bytes|writeFile|appendFile|createWriteStream|copyFile|"
                        r"shutil\.|os\.(remove|rename|replace|unlink|makedirs|mkdir)|unlinkSync|renameSync|rmSync|\.save\(|"
                        r"screenshot\(|\.to_csv|\.dump\(|subprocess|os\.system|execSync|spawnSync|child_process)")
INTERP = re.compile(r"\b(python3?|node|perl|ruby|bash|sh|deno|bun)\b")
PATH_TOKEN = re.compile(r"(?:/mnt/(?:attach/)?project-files|(?<![\w/])project-files)/([^\s'\"`;|&)<>,]*)")


def script_texts(cmd):
    """コマンドが実行するスクリプトファイルの中身（そこに書かれたパスも調べる）"""
    out = []
    # 実行されるスクリプトだけ（rm や cp の対象になっているだけのファイルは読まない）
    for tok in re.findall(r"\b(?:python3?|node|perl|ruby|bash|sh|deno|bun)\s+(?:-\S+\s+)*([^\s'\"`;|&<>]+\.(?:py|js|mjs|cjs|sh))\b", cmd):
        try:
            p = real(tok)
            if os.path.isfile(p) and os.path.getsize(p) < 2_000_000:
                out.append(open(p, encoding="utf-8", errors="ignore").read())
        except Exception:
            pass
    return out


def bash_paths(cmd):
    """書き込むおそれのあるコマンドに出てくる、制作物と仕組みのパスを集める"""
    texts = [cmd] + script_texts(cmd)
    alltext = "\n".join(texts)
    writes = bool(SHELL_WRITE.search(cmd)) or (bool(INTERP.search(cmd)) and bool(CODE_WRITE.search(alltext)))
    if not writes:
        return [], False
    found, vague = [], False
    for m in PATH_TOKEN.finditer(alltext):
        rest = m.group(1)
        top = rest.split("/")[0]
        if top in KINDS:
            parts = [x for x in rest.split("/") if x]
            if len(parts) < 2:
                vague = True
                continue
            if len(parts) == 2:
                rest = rest.rstrip("/") + "/x"  # 作品フォルダそのもの
        found.append(os.path.join(PF_REAL, rest))
    if re.search(r"\.claude/(settings|hooks)", alltext):
        found.append(os.path.join(REPO, ".claude", "x"))
    cwdw = work_of(os.path.join(os.getcwd(), "x"))
    if cwdw and not cwdw[1] and cwdw[0] != SITE_WORK:
        found.append(os.path.join(cwdw[0], "x"))
    # 公開ページ（このリポジトリ）を直す形。git の記録だけの操作は除く
    in_repo = bool(re.search(re.escape(REPO) + r"|(^|[\s;&|'\"])works/", alltext)) or os.path.realpath(os.getcwd()).startswith(REPO)
    only_git = re.fullmatch(r"(\s*(cd [^;&|]+|git\s+(status|log|diff|fetch|pull|push|add|commit|branch|show|remote|config)[^;&|]*)\s*(&&|;|\|\|)?)+", cmd)
    if in_repo and not only_git:
        for m in re.finditer(r"[^\s'\"`;|&<>]+", alltext):
            t = m.group(0)
            rel_ok = not t.startswith(("/", "-")) and ("/" in t or "." in t or os.path.exists(os.path.join(os.getcwd(), t)))
            if t.startswith(REPO) or (os.path.realpath(os.getcwd()).startswith(REPO) and rel_ok):
                w = work_of(t if t.startswith("/") else os.path.join(os.getcwd(), t))
                if w and w[0] == SITE_WORK and not t.endswith(".claude") and "/.claude" not in t:
                    found.append(os.path.join(REPO, "x"))
                    break
    return found, vague


def pre(data):
    tool, ti = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        check_paths([ti.get("file_path") or ti.get("notebook_path")])
    elif tool == "Bash":
        cmd = ti.get("command", "")
        # publish.py と check.js は中で gate.py が逆算メモを確かめるので通す
        if re.fullmatch(r"\s*(cd [^;&|]+(&&|;)\s*)?(python3?\s+(-I\s+)?\S*(publish|gate|audit)\.py[^;&|]*|node\s+\S*check\.js[^;&|]*)\s*", cmd):
            return
        paths, vague = bash_paths(cmd)
        if vague and not paths:
            # どの作品かが読めない書き込み。作品フォルダをはっきり書いてもらう
            deny("【逆算の関門】portfolio/ か sales/ に書き込むコマンドですが、どの作品かが読めません。作品フォルダまでのパスを書いてください。")
        check_paths(paths)
    elif tool == "Artifact":
        if ti.get("action", "publish") != "publish" or ti.get("asset"):
            return
        srcs = []
        if ti.get("file_path"):
            srcs.append(ti["file_path"])
        files = ti.get("files") or {}
        if isinstance(files, dict):
            for v in files.values():
                if isinstance(v, str):
                    srcs.append(v)
                elif isinstance(v, dict) and v.get("from"):
                    srcs.append(v["from"])
        elif isinstance(files, list):
            srcs += [f.get("path") for f in files if isinstance(f, dict) and f.get("path")]
        if ti.get("root"):
            srcs = [os.path.join(ti["root"], s) if not os.path.isabs(s) else s for s in srcs]
        m = urlmap()
        for s in srcs:
            w = work_of(s)
            if w and not w[1] and s.endswith(".html") and os.path.exists(os.path.join(w[0], "index.html")) \
                    and real(s) == real(os.path.join(w[0], "index.html")):
                deny("【関門】LPを作品フォルダから直接公開しないでください。python3 -I /mnt/project-files/knowledge/lp-kit/publish.py <index.html> <scratchpadの出力フォルダ> で作ったフォルダから公開します。")
            g = gate_out(s)
            if g and s.endswith("index.html") and g.get("sha256") and sha(real(s)) != g["sha256"]:
                deny("【関門】publish.py で作った後に公開用フォルダが書き換えられています。作品フォルダを直して publish.py からやり直してください。")
            if g and s.endswith("index.html") and g.get("sha256") == sha(real(s)):
                continue  # publish.py の中の gate.py が逆算メモを確かめ済み
            # 前に見せた作品を、別の場所のファイルから出し直す場合
            key = m.get("file:" + real(s)) or (g or {}).get("work")
            if key and not w:
                w = (os.path.join(PF_REAL, key), False)
            if w and not w[1]:
                last = records(w[0])
                if not (last and sha(real(s)) in [r.get("sha256") for r in last]) or ti.get("edits"):
                    mp = memo_problem(w[0])
                    if mp:
                        deny(mp)
        if ti.get("url") and m.get("url:" + ti["url"]):
            w = os.path.join(PF_REAL, m["url:" + ti["url"]])
            if not any(sha(real(s)) in [r.get("sha256") for r in records(w)] for s in srcs) or ti.get("edits"):
                mp = memo_problem(w)
                if mp:
                    deny(mp)


def record(w, entry):
    os.makedirs(os.path.join(w, "review"), exist_ok=True)
    entry = dict(entry, at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"))
    with open(os.path.join(w, "review", "関門記録.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def post(data):
    """見せたことを記録する（次に直すときは、この後に書いた逆算メモが要る）"""
    tool, ti = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    resp = json.dumps(data.get("tool_response", ""), ensure_ascii=False)
    if tool == "Artifact" and ti.get("action", "publish") == "publish" and not ti.get("asset"):
        if re.search(r"refus|rejected|error|失敗", resp[:400], re.I) and "claude.ai" not in resp:
            return
        srcs = [ti["file_path"]] if ti.get("file_path") else []
        if isinstance(ti.get("files"), dict):
            srcs += [v if isinstance(v, str) else v.get("from", "") for v in ti["files"].values() if isinstance(v, (str, dict))]
        urls = re.findall(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9_-]+", resp) + ([ti["url"]] if ti.get("url") else [])
        m = urlmap()
        for s in srcs:
            g = gate_out(s)
            w = work_of(s)
            key = (os.path.relpath(w[0], PF_REAL) if w and not w[1] else None) or (g or {}).get("work") or m.get("file:" + real(s))
            if not key:
                continue
            record(os.path.join(PF_REAL, key), {"kind": "shown", "sha256": sha(real(s)), "file": real(s), "url": urls[0] if urls else ""})
            m["file:" + real(s)] = key
            for u in urls:
                m["url:" + u] = key
        try:
            json.dump(m, open(URLMAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
    elif tool.endswith("post_message"):
        for o in ti.get("attached_outputs") or []:
            if isinstance(o, dict) and o.get("kind") == "file":
                w = work_of(o.get("ref", ""))
                if w and not w[1]:
                    record(w[0], {"kind": "shown", "sha256": sha(real(o["ref"])), "file": real(o["ref"])})
    elif tool == "Bash" and re.search(r"\bgit\s+push\b", (ti.get("command") or "")) and os.path.realpath(os.getcwd()).startswith(REPO):
        record(SITE_WORK, {"kind": "shown", "sha256": "", "file": "git push"})


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    try:
        if data.get("cwd"):
            os.chdir(data["cwd"])
    except Exception:
        pass
    if data.get("hook_event_name") == "PostToolUse":
        try:
            post(data)
        except Exception:
            pass
    else:
        pre(data)


if __name__ == "__main__":
    main()
