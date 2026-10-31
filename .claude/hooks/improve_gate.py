#!/usr/bin/env python3
"""直すときの関門（逆算アプローチ）の見張り役。2026-10-30 ユーザー指示:
「改善は目標から逆算して足りないところを埋める。確実に実行される仕組みにして」

一度ユーザーに見せた制作物（Artifact で公開した・スレッドに添付した・関門導入時に登録した）を直すときは、
その作品の review/ に「逆算*.md」を、最後に見せたあとに書いておかないと、
Edit / Write / Bash / Artifact のどれで直そうとしても止める。

作品の単位: /mnt/project-files/portfolio/<名前>/ と /mnt/project-files/sales/<名前>/。
公開ページ（このリポジトリ）は /mnt/project-files/portfolio/公開ページ/ を作品フォルダとして扱う。
逆算メモの中身: 「## 目標」に一流の見本URL 2件以上、「## 差」「## 埋め方」に「- 」の行を3つ以上。前のメモの写しは不可。
「## 調べたこと」（2026-10-31 ユーザー「逆算に必要な情報は自分で考えて集めてくる。それが無いと逆算のしようがない」）:
  差を埋めるのに足りなかった情報を、自分で考えて調べた記録。「- 」の行を2つ以上、各行に調べた先（URL・knowledge/ のファイル・
  「ユーザー提供」）とわかったこと（30字以上）。少なくとも1行は、目標の見本とは別のURLか「ユーザー提供」（手元の知識だけで済ませない）。
見せた記録: 作品の review/関門記録.jsonl（publish.py とこの見張り役が書く）。

Claude Docs（文章案・構成案など）も制作物として扱う（2026-10-31、文章案が素通りしていた穴を塞ぐ）:
- 新しい Doc は本文に「制作物: portfolio/<名前>」（sales/ も可）か「制作物: なし」を書かないと作れない。
  文章案・構成案・見出し案などの Doc を「なし」にはできない。
- 作品に結びついた Doc を作る・直すときは、その作品のファイルを直すときと同じく逆算メモが要る。
- Doc を触った後にスレッドへ返信すると「見せた」と記録する（次に直すときは、その後の逆算メモが要る）。
- 結びつきのわからない Doc は直せない。python3 -I .claude/hooks/doc_link.py <Doc id> <portfolio/名前|なし> で登録する。

読み込ませ方: プロジェクトのスレッドではリポジトリの .claude/settings.json は読まれない。
.claude/install_hooks.py が ~/.claude/settings.json に書き足す（CLAUDE.md・gate.py・環境の Setup script から呼ぶ）。
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
             os.path.join(PF_REAL, "knowledge", "lp-kit", "check.js"),
             os.path.join(PF_REAL, "knowledge", "lp-kit", "第三者判定_依頼文.md")]
JUDGE_TPL = os.path.join(PF_REAL, "knowledge", "lp-kit", "第三者判定_依頼文.md")
JUDGE_MARK = "<!-- 見張り役が記録した第三者判定 -->"


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
        if rel.startswith(".git") or rel.startswith(".claude") or rel == "CLAUDE.md":
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


def gap_detail_errs(goal, gap):
    """「差」の各行が、見本のどこと比べたか（目標のURLか「見本N」）と、中身（20字以上）を持っているか"""
    if goal is None or gap is None:
        return []
    urls = list(dict.fromkeys(re.findall(r"https?://[^\s)|>\]]+", goal)))
    bad = []
    for line in re.findall(r"^\s*[-・*]\s*(\S.*)$", gap, re.M):
        ref = any(u in line for u in urls) or any(1 <= int(n) <= len(urls) for n in re.findall(r"見本\s*(\d+)", line))
        if not ref or len(line.strip()) < 20:
            bad.append(line.strip()[:20])
    if bad:
        return ["「## 差」の各行に、比べた見本（目標のURLか「見本1」のような番号）と、どこがどう違うか（20字以上）を書く。足りない行: " + "／".join(bad)]
    return []


def research_errs(goal, research):
    """「調べたこと」に、差を埋めるために自分で集めた情報（調べた先とわかったこと）があるか"""
    if research is None:
        return ["「## 調べたこと」がない（差を埋めるのに足りない情報を自分で考えて調べ、調べた先とわかったことを書く）"]
    lines = re.findall(r"^\s*[-・*]\s*(\S.*)$", research, re.M)
    if len(lines) < 2:
        return ["「## 調べたこと」に「- 」の行が2つ以上ない"]
    goal_urls = set(re.findall(r"https?://[^\s)|>\]]+", goal or ""))
    bad, fresh = [], False
    for line in lines:
        urls = re.findall(r"https?://[^\s)|>\]]+", line)
        src = urls or "knowledge/" in line or "ユーザー提供" in line
        if not src or len(line.strip()) < 30:
            bad.append(line.strip()[:20])
        if any(u not in goal_urls for u in urls) or "ユーザー提供" in line:
            fresh = True
    errs = []
    if bad:
        errs.append("「## 調べたこと」の各行に、調べた先（URL・knowledge/ のファイル・「ユーザー提供」）とわかったこと（30字以上）を書く。足りない行: " + "／".join(bad))
    if not fresh:
        errs.append("「## 調べたこと」に、目標の見本とは別のURLか「ユーザー提供」が1行もない（手元の知識だけで済ませず、新しく調べに行く）")
    return errs


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
            "今の版をいじるのではなく、①一流の完成形（目標）を先に集めて見る ②今と並べて差を言葉にする ③差を埋めるのに足りない情報を自分で考えて調べに行く ④埋め方を決める。")
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
    errs += gap_detail_errs(goal, gap)
    research = section(t, "調べたこと")
    errs += research_errs(goal, research)
    old = [f for f in memos if f not in new]
    norm = lambda s: re.sub(r"\s+", "", s or "")
    for f in old:
        ot = open(f, encoding="utf-8").read()
        for n, body in (("差", gap), ("調べたこと", research)):
            if body is not None and norm(body) and norm(section(ot, n)) == norm(body):
                errs.append(f"「## {n}」が前のメモ {os.path.basename(f)} の写し")
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
        m = json.load(open(URLMAP, encoding="utf-8"))
    except Exception:
        return {}
    # 手で書いた形 {"https://claude.ai/artifact/..": {"work": ".."}} も読む
    for k, v in list(m.items()):
        if k.startswith("https://") and isinstance(v, dict) and v.get("work"):
            m.setdefault("url:" + k, v["work"])
    return m


def save_urlmap(m):
    try:
        cur = urlmap()  # ほかのスレッドが書いた分を消さない
        cur.update(m)
        tmp = URLMAP + ".tmp" + str(os.getpid())
        json.dump(cur, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, URLMAP)
    except Exception:
        pass


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
SITE_EXT = re.compile(r"\.(html?|css|js|mjs|png|jpe?g|webp|gif|svg|avif|ico|woff2?|json|txt|xml)$", re.I)
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
    lead = re.match(r"\s*cd\s+(['\"]?)([^\s;&|'\"]+)\1\s*(&&|;)", cmd)
    if lead:
        # 先頭の「cd 場所 &&」は、その場所で動くコマンドとして読む（作業場所が残っていても）
        try:
            os.chdir(os.path.expanduser(lead.group(2)))
        except Exception:
            pass
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
        # 「cd 場所」は移動だけで書き込み先ではない
        scan = [re.sub(r"(^|[;&|(]\s*)cd\s+[^\s;&|]+", r"\1", texts[0])] + texts[1:]
        toks = [(m.group(0), i == 0) for i, txt in enumerate(scan) for m in re.finditer(r"[^\s'\"`;|&<>]+", txt)]
        for t, in_cmd in toks:
            # 相対パスは、リポジトリにある物か、コマンドに直接書いたページの部品らしい名前だけ（スクリプト中の「a.b」などを拾わない）
            first = os.path.join(os.getcwd(), t.split("/")[0])
            rel_ok = not t.startswith(("/", "-")) and (os.path.exists(first) or (in_cmd and bool(SITE_EXT.search(t))))
            if not in_cmd and t.rstrip("/") == REPO:
                continue  # スクリプト中のリポジトリ名だけ（chdir など）は書き込み先と見なさない
            if t.startswith(REPO) or (os.path.realpath(os.getcwd()).startswith(REPO) and rel_ok):
                w = work_of(t if t.startswith("/") else os.path.join(os.getcwd(), t))
                if w and w[0] == SITE_WORK and not t.endswith(".claude") and "/.claude" not in t:
                    found.append(os.path.join(REPO, "x"))
                    break
    return found, vague


def judge_prompt_problem(prompt):
    """依頼文が決まった形どおりか（作った側の結論や言い訳を混ぜていないか）"""
    try:
        tpl = open(JUDGE_TPL, encoding="utf-8").read()
    except Exception:
        return "第三者判定の依頼文の型が見つかりません: " + JUDGE_TPL
    fixed = [l.strip() for l in tpl.splitlines() if l.strip() and "{" not in l]
    lines = [l.strip() for l in prompt.splitlines() if l.strip()]
    missing = [l for l in fixed if l not in lines]
    if missing:
        return "【関門】第三者判定の依頼文が型と違います（足りない行: " + missing[0][:30] + "）。lp-kit/第三者判定_依頼文.md の {} だけを埋めて、そのまま渡してください。"
    extra = [l for l in lines if l not in fixed and not l.startswith(("- 作品フォルダ:", "- 目指す一流の見本"))
             and not re.fullmatch(r"[-・*]?\s*https?://\S+", l)]
    if extra:
        return "【関門】第三者判定の依頼文に、型にない文が入っています（作った側の考えを渡さないため）: " + extra[0][:40]
    if len(set(re.findall(r"https?://\S+", prompt))) < 3:
        return "【関門】第三者判定の依頼文に、一流の見本URLが3件以上ありません。"
    if not re.search(r"- 作品フォルダ:\s*/mnt/\S+", prompt):
        return "【関門】第三者判定の依頼文の「- 作品フォルダ:」に作品フォルダのパスを書いてください。"
    return None


# ---- Claude Docs（文章案・構成案など）----
DECL = re.compile(r"制作物\s*[:：]\s*((?:portfolio|sales)/[^\s/、。,，)）\\\"]+|なし)")
COPY_WORDS = re.compile(r"文章案|コピー案|見出し案|構成案|キャッチ|提案文|LPの文|本文案|文案")
STATE_DIR = os.path.expanduser("~/.claude/improve_gate_state")
DOC_ID = re.compile(r"claude\.ai/(?:code/)?artifact/(?:[^\s\"'/?#]*-)?([A-Za-z0-9]{22})\b|\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b")
DOC_LINK_CMD = "python3 -I " + os.path.join(REPO, ".claude", "hooks", "doc_link.py")


def doc_ids(text):
    return list(dict.fromkeys(a or b for a, b in DOC_ID.findall(text or "")))


def norm_doc(i):
    i = str(i or "")
    found = doc_ids(i)
    return found[0] if found else i.strip()


def state(sid):
    try:
        return json.load(open(os.path.join(STATE_DIR, (sid or "x") + ".json"), encoding="utf-8"))
    except Exception:
        return {}


def save_state(sid, st):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(st, open(os.path.join(STATE_DIR, (sid or "x") + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def doc_work(m, did):
    """Doc に結びついた作品（'portfolio/..' か 'なし'）。わからなければ None"""
    return m.get("doc:" + norm_doc(did))


def doc_target(tool, ti):
    """Docs の呼び出しが書き換える Doc の id。新しく作る呼び出しは 'NEW'。書き換えないものは None"""
    name = tool.split("__")[-1]
    c = ti.get("container") or {}
    ref = ti.get("ref") or {}
    if name in ("read", "query", "guide", "export"):
        return None
    if ti.get("object") == "utterance" or ref.get("object") == "utterance":
        return None  # コメントのやり取りは本文の書き換えではない
    if name == "batch" and c.get("create"):
        return "NEW"
    if c.get("id"):
        return norm_doc(c["id"])
    if ref.get("object") == "project" and ref.get("id"):
        return norm_doc(ref["id"])  # Doc の名前の変更など
    return None


def pre_docs(data, tool, ti):
    target = doc_target(tool, ti)
    if target is None:
        return
    m = urlmap()
    sid = data.get("session_id", "")
    if target == "NEW":
        text = json.dumps(ti, ensure_ascii=False)
        d = DECL.search(text)
        if not d:
            deny("【逆算の関門】Doc を作るときは、本文のどこかに「制作物: portfolio/<作品フォルダ名>」（sales/ も可）か、"
                 "作品と関係ない Doc なら「制作物: なし」と書いてください。文章案・構成案は作品に結びつけます。")
        key = d.group(1)
        if key == "なし":
            if COPY_WORDS.search(text):
                deny("【逆算の関門】文章案・構成案・見出し案などの Doc は「制作物: なし」にできません。"
                     "「制作物: portfolio/<作品フォルダ名>」と書いて、その作品に結びつけてください。")
        else:
            w = os.path.join(PF_REAL, key)
            if not os.path.isdir(w):
                deny("【逆算の関門】「制作物: " + key + "」の作品フォルダがありません。先に /mnt/project-files/" + key + "/ を作ってください。")
            mp = memo_problem(w)
            if mp:
                deny(mp + "（Doc の文章案も、その作品を直すことに入ります）")
        st = state(sid)
        st["pending_doc"] = {"work": key, "at": datetime.datetime.now(datetime.timezone.utc).timestamp()}
        save_state(sid, st)
        return
    key = doc_work(m, target)
    if key is None:
        st = state(sid)
        p = st.get("pending_doc")
        if p and datetime.datetime.now(datetime.timezone.utc).timestamp() - p.get("at", 0) < 3600:
            key = p["work"]  # このスレッドで作ったばかりの Doc（作ったときの返事から id を読めなかった場合）
            m["doc:" + target] = key
            save_urlmap({"doc:" + target: key})
        else:
            deny("【逆算の関門】この Doc（" + target + "）がどの作品の文章かわかりません。先に "
                 + DOC_LINK_CMD + " " + target + " <portfolio/作品フォルダ名 か なし> で登録してください。"
                 "文章案・構成案は作品フォルダに結びつけます。")
    if key == "なし":
        return
    mp = memo_problem(os.path.join(PF_REAL, key))
    if mp:
        deny(mp + "（この Doc は " + key + " の文章です。Doc の書き換えも作品を直すことに入ります）")
    st = state(sid)
    st.setdefault("touched_docs", {})[target] = key
    save_state(sid, st)


def post_docs(data, tool, ti):
    target = doc_target(tool, ti)
    if target != "NEW":
        return
    sid = data.get("session_id", "")
    st = state(sid)
    p = st.get("pending_doc")
    if not p:
        return
    resp = json.dumps(data.get("tool_response", ""), ensure_ascii=False)
    ids = doc_ids(resp)
    if ids:
        save_urlmap({"doc:" + i: p["work"] for i in ids})
        if p["work"] != "なし":
            st.setdefault("touched_docs", {})[ids[0]] = p["work"]
        st.pop("pending_doc", None)
        save_state(sid, st)


def post_shown_docs(data):
    """返信したら、触った Doc の作品を「見せた」と記録する"""
    sid = data.get("session_id", "")
    st = state(sid)
    touched = st.get("touched_docs") or {}
    for did, key in touched.items():
        if key and key != "なし":
            record(os.path.join(PF_REAL, key), {"kind": "shown", "sha256": "", "file": "doc:" + did})
    if touched:
        st["touched_docs"] = {}
        save_state(sid, st)


def pre(data):
    tool, ti = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    if tool.startswith("mcp__Claude_Docs__"):
        pre_docs(data, tool, ti)
        return
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        fp = ti.get("file_path") or ti.get("notebook_path") or ""
        if "第三者判定" in os.path.basename(fp) and real(fp) != JUDGE_TPL:
            deny("【関門】第三者判定は自分では書けません。Agent ツールで別のエージェントに、/mnt/project-files/knowledge/lp-kit/第三者判定_依頼文.md の形で頼むと、見張り役が結果を review/ に記録します。")
        check_paths([fp])
    elif tool == "Agent":
        prompt = ti.get("prompt", "")
        if "【第三者判定】" in prompt:
            if ti.get("subagent_type") == "fork":
                deny("【関門】第三者判定に fork は使えません（自分の考えを引き継ぐため）。新しいエージェント（general-purpose など）に頼んでください。")
            p = judge_prompt_problem(prompt)
            if p:
                deny(p)
    elif tool == "Bash":
        cmd = ti.get("command", "")
        if "第三者判定" in cmd and (SHELL_WRITE.search(cmd) or (INTERP.search(cmd) and CODE_WRITE.search(cmd))):
            deny("【関門】第三者判定のファイルはコマンドで作ったり書き換えたりできません。Agent ツールで別のエージェントに頼んでください。")
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
        save_urlmap(m)
    elif tool == "Agent" and "【第三者判定】" in (ti.get("prompt") or ""):
        m = re.search(r"- 作品フォルダ:\s*(/\S+)", ti["prompt"])
        w = work_of(os.path.join(m.group(1).rstrip("/"), "x")) if m else None
        if not w:
            return
        r = data.get("tool_response")
        if isinstance(r, dict) and isinstance(r.get("content"), list):
            text = "\n".join(c.get("text", "") for c in r["content"] if isinstance(c, dict))
        elif isinstance(r, str):
            text = r
        else:
            text = json.dumps(r, ensure_ascii=False)
        res = re.findall(r"結果[:：]\s*(合格|不合格)", text)
        final = res[-1] if res else "不明"
        idx = os.path.join(w[0], "index.html")
        now = datetime.datetime.now(datetime.timezone.utc)
        out = os.path.join(w[0], "review", "第三者判定_" + now.strftime("%Y%m%d_%H%M%S") + ".md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(JUDGE_MARK + "\n")
            f.write("判定者: 別エージェント（" + (ti.get("subagent_type") or "general-purpose") + "）\n")
            f.write("日時: " + now.isoformat(timespec="seconds") + "\n")
            f.write("作品の版: " + (sha(idx) if os.path.exists(idx) else "") + "\n")
            f.write("最終結果: " + final + "\n\n## 依頼文\n" + ti["prompt"] + "\n\n## 判定\n" + text + "\n")
    elif tool.startswith("mcp__Claude_Docs__"):
        post_docs(data, tool, ti)
    elif tool.endswith("post_message"):
        post_shown_docs(data)
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
