<div align="center">

# 🏔️ shanya-shuyuan (Cliffside Academy)

### Turn any book into a course that knows you

**Test-first reading ・ Life mirroring ・ Two-minute open**

[繁體中文](README.md) ・ **English**

> 📖 This project primarily serves Chinese-speaking readers; the default README is in Traditional Chinese.

</div>

---

> This is a Claude Code / Codex **skill**, not an app. The agent is the runtime and HTML is the textbook — we think this is what reading should look like in the agent era.

## ✨ Why an academy, not another summarizer?

- **🎯 Test-first reading** — Each lesson opens with 3 intuition questions (answerable without reading). The lesson text is then generated *around your wrong answers*; what you already know gets compressed. Retrieval practice beats re-reading.
- **🪞 Two-column life mirror** — Left column faithfully preserves the book (quotes, stories, frameworks). Right column maps every idea onto *your actual life*, under strict anti-fabrication rules: any claim about your life that can't be traced to your own files gets deleted; irrelevant chapters are called out honestly, never forced.
- **⚡ Open a book in ≤2 minutes** — Quiz generation only needs the TOC + introduction. While you answer, the system prepares the full course in the background (chapter capsules, personal hooks, reordered syllabus). You never wait.
- **🎬 Action-driven** — Each chapter ends with one small, verifiable action (ideally hooked to your real todo list). The next lesson starts by checking it.
- **🔒 Privacy gate** — Your context pack, the right column, and learning records never leave your machine. Only the book itself goes to (optional) NotebookLM for capsules and audio.

## 🚀 Quick start

```bash
git clone https://github.com/bockybocky/shanya-shuyuan.git ~/.claude/skills/shanya-shuyuan
# Then tell your agent: "Open <book.epub> as a course"
# Continue with "next lesson" / "course progress"
```

Requires Claude Code (or a compatible agent runtime) and Python 3.10+ (stdlib-only extraction script). Optional: NotebookLM.

## 🧩 Design

- Full design evolution: [`references/design-journey.md`](references/design-journey.md) (in Chinese — including how "11 minutes to open a book, the student already left" became the ≤2-minute hard rule)
- Extraction tool: [`scripts/epub_to_md.py`](scripts/epub_to_md.py) (epub → per-chapter markdown, stdlib-only, seconds, zero LLM)
- Standing on the shoulders of: [Matt Pocock's teach skill](https://github.com/mattpocock/skills) (pedagogy + progress memory) × [Garry Tan's gbrain book-mirror](https://github.com/garrytan/gbrain) (life mirroring + anti-fabrication discipline)

## ⚠️ Notes

- Use books you legally own. This tool contains no downloading functionality.
- The mirror is only as good as your personal context files — honest notes make a sharp mirror.

## 👥 Authors

[@bockybocky](https://github.com/bockybocky) — design & initial implementation ・ [@fredchu](https://github.com/fredchu) — co-developer

## License

[MIT](LICENSE)
