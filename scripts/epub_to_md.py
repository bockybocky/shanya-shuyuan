#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""epub → 逐章 MD 匯出（山崖書院預處理層：書一到手就先轉 MD，開課秒開）

用法:
  python epub_to_md.py --book path/to/book_bilingual.epub [--out DIR]

輸出（預設在 epub 旁邊建 {stem}_md/）:
  {stem}_md/NN_<原檔名>.md   逐內容檔一個 md（含 front matter: 序號/來源檔/字元數）
  {stem}_md/INDEX.md         清單（檔名/首行標題/字元數）

實作註記:
- 純標準庫（zipfile+re+html），不吃 bs4 —— 實測乾淨。
- 不猜「哪些是正文章節」：全部 xhtml/html 內容檔都出（封面/版權頁很小無害），
  由下游（山崖書院備課）自行挑章。寧全勿漏。
- Windows 坑：glob/zip 路徑分隔符不齊 → 一律用 basename 比對與 posix path。
"""
from __future__ import annotations
import argparse, html, re, zipfile
from pathlib import Path


def strip_html(raw: str) -> str:
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", "\n", txt)
    txt = html.unescape(txt)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    book = Path(a.book)
    out = Path(a.out) if a.out else book.with_name(book.stem + "_md")
    out.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(book) as z:
        names = sorted(
            n for n in z.namelist()
            if n.lower().endswith((".xhtml", ".html", ".htm"))
        )
        index_rows = []
        for i, name in enumerate(names):
            raw = z.read(name).decode("utf-8", "replace")
            body = strip_html(raw)
            base = Path(name).stem
            md_path = out / f"{i:02d}_{base}.md"
            title = next((l for l in body.splitlines()[:10] if len(l) > 3), base)
            md_path.write_text(
                f"---\nseq: {i}\nsource: {name}\nchars: {len(body)}\n---\n\n{body}\n",
                encoding="utf-8",
            )
            index_rows.append(f"- {md_path.name} | {title[:70]} | {len(body)} chars")
        (out / "INDEX.md").write_text(
            f"# {book.stem} — 逐章 MD\n\n" + "\n".join(index_rows) + "\n",
            encoding="utf-8",
        )
    print(f"OK: {len(names)} files -> {out}")


if __name__ == "__main__":
    main()
