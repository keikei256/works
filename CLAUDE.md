# 最初に必ずやること（どのスレッドでも、ほかの作業より先に）

```
python3 -I /home/user/works/.claude/install_hooks.py
```

「見張り役: 入れました」か「見張り役: 入っています」と出れば完了。

なぜ: 逆算の見張り役（`.claude/hooks/improve_gate.py`）は、一度見せた制作物（`/mnt/project-files/portfolio/`・`sales/`・この公開ページ・作品に結びついた Claude Docs の文章案）を、逆算メモ（`review/逆算_<日付>.md`）なしに直そうとすると止める仕組み。
プロジェクトのスレッドではリポジトリの `.claude/settings.json` のフックが読み込まれないため、上のコマンドで `~/.claude/settings.json` に入れないと見張り役は動かない（2026-10-31 確認）。

- 見張り役に止められたら、言われたとおり逆算メモを先に書く。見張り役を外す・迂回する書き方を探さない。
- 新しい Claude Docs を作るときは、本文に「制作物: portfolio/<作品フォルダ名>」か「制作物: なし」を書く（文章案・構成案は必ず作品に結びつける）。
- 公開は `/mnt/project-files/knowledge/lp-kit/publish.py` 経由のみ。中の `gate.py` も、見張り役が入っていなければ入れ直す。
