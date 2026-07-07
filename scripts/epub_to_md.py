#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""epub → 逐章 MD 匯出 v2（山崖書院預處理層：書一到手就先轉 MD，開課秒開）

用法:
  python epub_to_md.py --book path/to/book.epub [--out DIR] [--force]

輸出（預設在 epub 旁邊建 {stem}_md/）:
  {stem}_md/NN_<slug>.md   照 OPF spine 閱讀順序，一個 spine 項一個 md
  {stem}_md/INDEX.md       清單（序號/標題/角色/字元數）

v2 改版（2026-07-07，取經 sister project bookmate 的拆章法）:
- 章序改走 **OPF spine**（container.xml → OPF → spine idref 順序），不再用檔名排序
  ——檔名排序在命名不規則的 epub 會亂章序，spine 才是出版標準的閱讀順序。
- 跳過 spine linear="no" 項（出版商標記的非線性內容）。
- 角色標記：cover/nav/toc 標 [skip]、疑似前後雜項（版權/致謝/索引）標 [aux]，
  正文標 [body]——下游（書院備課）可只取 body。
- HTML 解析改結構化（HTMLParser）：段落/標題保留換行、blockquote 轉 "> "、
  表格列轉 "| a | b |"、圖片保留 alt——比 regex 全剝乾淨得多。
- OPF 解析失敗自動 fallback 回 v1 檔名排序法（寧可有產出）。

實作註記:
- 純標準庫（zipfile+xml.etree+html.parser）。
- Windows 坑：路徑一律 posix 化比對；zip 內 href 可能帶 ../ 需 normpath。
"""
from __future__ import annotations
import argparse, html, os, posixpath, re, unicodedata, zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

AUX_HINTS = re.compile(r"copyright|acknowledg|dedication|index|bibliograph|notes?$|about.?the.?author|also.?by|ad.?card|praise", re.I)
SKIP_HINTS = re.compile(r"cover|^nav$|toc|contents|titlepage|title.?page", re.I)


class _TextParser(HTMLParser):
    """結構化 HTML→文字：保段落、引文加 >、表格列轉管線、圖片留 alt。"""
    BLOCK = {"p", "div", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._tag: str | None = None
        self._buf: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self.first_heading = ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.BLOCK:
            self._flush(); self._tag = tag
        elif tag == "tr":
            self._flush(); self._row = []
        elif tag in {"td", "th"}:
            self._cell = []
        elif tag == "img":
            alt = next((v for k, v in attrs if k.lower() == "alt" and v), "").strip()
            self._flush(); self.out.append(f"[圖: {alt}]" if alt else "[圖]")
        elif tag == "br" and self._tag:
            self._buf.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.BLOCK:
            self._flush()
        elif tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell))); self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.out.append("| " + " | ".join(self._row) + " |")
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._tag:
            self._buf.append(data)

    def _flush(self):
        if not self._tag:
            self._buf = []; return
        text = _clean(" ".join(self._buf))
        if text:
            if self._tag == "blockquote":
                text = "\n".join("> " + l for l in text.splitlines())
            if self._tag.startswith("h") and not self.first_heading:
                self.first_heading = text
            self.out.append(text)
        self._tag = None; self._buf = []


def _clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", html.unescape(s)).strip()


def html_to_text(raw: str) -> tuple[str, str]:
    """回 (全文, 第一個標題)。HTMLParser 失敗就 regex fallback。"""
    try:
        p = _TextParser(); p.feed(raw); p._flush()
        return "\n\n".join(b for b in p.out if b).strip(), p.first_heading
    except Exception:
        txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
        txt = html.unescape(re.sub(r"<[^>]+>", "\n", txt))
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        return "\n".join(lines), (lines[0] if lines else "")


def slugify(text: str, fallback: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:48] or fallback)


def spine_order(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    """解 container.xml → OPF → 回傳 [(href, role)] 依 spine 閱讀順序。"""
    ns_c = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    container = ET.fromstring(z.read("META-INF/container.xml"))
    opf_path = container.find(".//c:rootfile", ns_c).attrib["full-path"]
    opf_dir = posixpath.dirname(opf_path)
    opf = ET.fromstring(z.read(opf_path))
    ns = {"o": "http://www.idpf.org/2007/opf"}
    manifest = {}
    for item in opf.find("o:manifest", ns):
        props = item.get("properties", "")
        manifest[item.get("id")] = (item.get("href"), props)
    ordered = []
    for itemref in opf.find("o:spine", ns):
        if str(itemref.get("linear", "yes")).lower() == "no":
            continue  # 出版商標非線性內容，跳過
        href, props = manifest.get(itemref.get("idref"), (None, ""))
        if not href:
            continue
        full = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
        name = posixpath.basename(full)
        if "nav" in props or SKIP_HINTS.search(name):
            role = "skip"
        elif AUX_HINTS.search(name):
            role = "aux"
        else:
            role = "body"
        ordered.append((full, role))
    return ordered


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true", help="已存在也重轉（覆寫）")
    a = ap.parse_args()

    book = Path(a.book)
    out = Path(a.out) if a.out else book.with_name(book.stem + "_md")
    if (out / "INDEX.md").exists() and not a.force:
        print(f"SKIP: {out} 已存在（--force 可重轉）"); return
    out.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(book) as z:
        mode = "spine"
        try:
            entries = spine_order(z)
            # spine href 與 zip 名對齊（大小寫/編碼差異取 namelist 實名）
            realnames = {n.lower(): n for n in z.namelist()}
            entries = [(realnames.get(h.lower(), h), r) for h, r in entries]
        except Exception as e:
            mode = f"fallback-filename-sort（OPF 解析失敗: {e}）"
            entries = [(n, "body") for n in sorted(z.namelist())
                       if n.lower().endswith((".xhtml", ".html", ".htm"))]

        rows = []
        for i, (name, role) in enumerate(entries):
            try:
                raw = z.read(name).decode("utf-8", "replace")
            except KeyError:
                rows.append((i, name, role, 0, "（zip 內找不到，略）")); continue
            body, heading = html_to_text(raw)
            title = heading or next((l for l in body.splitlines() if len(l.strip()) > 3), Path(name).stem)
            md = out / f"{i:02d}_{slugify(title, Path(name).stem)}.md"
            md.write_text(
                f"---\nseq: {i}\nsource: {name}\nrole: {role}\nchars: {len(body)}\n---\n\n{body}\n",
                encoding="utf-8")
            rows.append((i, md.name, role, len(body), title[:70]))

    n_body = sum(1 for r in rows if r[2] == "body")
    idx = [f"# {book.stem} — 逐章 MD（order={mode}）", "",
           f"共 {len(rows)} 檔｜body {n_body}｜aux/skip {len(rows)-n_body}", ""]
    idx += [f"- {fn} | [{role}] | {t} | {c} chars" for _, fn, role, c, t in rows]
    (out / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"OK: {len(rows)} files ({n_body} body) -> {out}  [order={mode}]")


if __name__ == "__main__":
    main()
