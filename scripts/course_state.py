#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


STATES = ["pending", "taught", "verified"]


def fail(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def state_path(course: Path) -> Path:
    return course / "course_state.json"


def load_state(course: Path) -> dict:
    path = state_path(course)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"course_state.json invalid or missing; run rebuild: {exc}") from exc


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def sorted_units(state: dict) -> list[dict]:
    return sorted(state.get("units", []), key=lambda u: (int(u.get("plan_order") or 0), u.get("id", "")))


def unit_by_id(state: dict, unit_id: str) -> dict:
    for unit in state.get("units", []):
        if unit.get("id") == unit_id:
            return unit
    raise ValueError(f"unknown id: {unit_id}")


def group_ids(state: dict, unit_id: str) -> list[str]:
    unit = unit_by_id(state, unit_id)
    group = unit.get("plan_group")
    if not group:
        return [unit_id]
    return [u["id"] for u in sorted_units(state) if u.get("plan_group") == group]


def group_units(state: dict, unit_id: str) -> list[dict]:
    ids = set(group_ids(state, unit_id))
    return [u for u in sorted_units(state) if u["id"] in ids]


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    match = re.search(r"\n---\s*\n", text[3:])
    if not match:
        return text
    return text[3 + match.end() :]


def chapter_title(path: Path) -> str:
    body = strip_frontmatter(path.read_text(encoding="utf-8"))
    first = None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            return heading.group(1).strip()
        if first is None:
            first = line
    return first or path.stem


def scan_chapters(course: Path) -> list[dict]:
    units = []
    seen: set[str] = set()
    order = 1
    for path in sorted((course / "book" / "chapters").glob("*.md")):
        match = re.match(r"^(\d{2})_.*\.md$", path.name)
        if not match:
            continue
        unit_id = match.group(1)
        if unit_id in seen:
            raise ValueError(f"duplicate chapter ids in book/chapters/: {unit_id}")
        seen.add(unit_id)
        units.append(
            {
                "id": unit_id,
                "file": f"book/chapters/{path.name}",
                "title": chapter_title(path),
                "state": "pending",
                "plan_order": order,
                "plan_group": None,
                "skipped": False,
                "taught_at": None,
            }
        )
        order += 1
    return units


def command_init(course: Path, force: bool) -> int:
    path = state_path(course)
    if path.exists() and not force:
        return fail("course_state.json already exists; use --force to overwrite")
    try:
        units = scan_chapters(course)
    except Exception as exc:
        return fail(str(exc))
    state = {"schema_version": 1, "course_slug": course.name, "plan_applied": False, "units": units}
    atomic_write_json(path, state)
    for unit in sorted_units(state):
        print(f"{unit['id']} {unit['title']}")
    return 0


def command_status(course: Path) -> int:
    state = load_state(course)
    active = [u for u in sorted_units(state) if not u.get("skipped")]
    skipped = [u for u in sorted_units(state) if u.get("skipped")]
    counts = Counter(u.get("state") for u in state.get("units", []))
    current = next((u for u in active if u.get("state") == "pending"), None)
    print(f"{len(state.get('units', []))} units; pending={counts['pending']} taught={counts['taught']} verified={counts['verified']}")
    print(f"current: {current['id']} {current['title']}" if current else "current: none")
    for unit in active:
        group = f" group={unit['plan_group']}" if unit.get("plan_group") else ""
        print(f"{unit['id']} [{unit['state']}]{group} {unit['title']}")
    if skipped:
        print("skipped:")
        for unit in skipped:
            print(f"{unit['id']} [{unit['state']}] {unit['title']}")
    return 0


def command_next(course: Path) -> int:
    state = load_state(course)
    seen: set[str] = set()
    for unit in sorted_units(state):
        key = unit.get("plan_group") or unit["id"]
        if key in seen:
            continue
        seen.add(key)
        members = group_units(state, unit["id"])
        if any(u.get("skipped") for u in members):
            continue
        if all(u.get("state") == "pending" for u in members):
            print(json.dumps({"ids": [u["id"] for u in members], "titles": [u["title"] for u in members]}, ensure_ascii=False))
            return 0
    return fail("nothing pending", 3)


def command_plan(course: Path, plan_file: str) -> int:
    state = load_state(course)
    plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
    entries = [list(item.get("ids", [])) for item in plan.get("units", [])]
    skip = list(plan.get("skip", []))
    known = {u["id"] for u in state.get("units", [])}
    flattened = [unit_id for ids in entries for unit_id in ids] + skip
    counts = Counter(flattened)
    missing = sorted(known - set(flattened))
    unknown = sorted(set(flattened) - known)
    duplicates = sorted(unit_id for unit_id, count in counts.items() if count > 1)
    empty = [i for i, ids in enumerate(entries, start=1) if not ids]
    if missing or unknown or duplicates or empty:
        return fail(f"invalid plan partition; missing={missing} unknown={unknown} duplicates={duplicates} empty_entries={empty}")

    skip_bad = sorted(unit_id for unit_id in skip if unit_by_id(state, unit_id).get("state") != "pending")
    if skip_bad:
        return fail(f"cannot skip non-pending ids: {skip_bad}")

    new_group_for: dict[str, set[str]] = {}
    for ids in entries:
        group = set(ids)
        for unit_id in ids:
            new_group_for[unit_id] = group
    for unit_id in skip:
        new_group_for[unit_id] = {unit_id}

    changed = []
    for unit in state.get("units", []):
        if unit.get("state") == "pending":
            continue
        if set(group_ids(state, unit["id"])) != new_group_for[unit["id"]]:
            changed.append(unit["id"])
    if changed:
        return fail(f"cannot change group composition for non-pending ids: {sorted(changed)}")

    updates: dict[str, tuple[int, str | None, bool]] = {}
    for order, ids in enumerate(entries, start=1):
        group = f"g{ids[0]}" if len(ids) > 1 else None
        for unit_id in ids:
            updates[unit_id] = (order, group, False)
    order = len(entries) + 1
    for unit_id in skip:
        updates[unit_id] = (order, None, True)
        order += 1

    for unit in state["units"]:
        unit["plan_order"], unit["plan_group"], unit["skipped"] = updates[unit["id"]]
    state["plan_applied"] = True
    atomic_write_json(state_path(course), state)
    return 0


def data_chapters(html: str) -> list[str] | None:
    match = re.search(r"<body\b[^>]*\bdata-chapters=(['\"])(.*?)\1", html, re.I | re.S)
    if not match:
        return None
    return [part.strip() for part in match.group(2).split(",") if part.strip()]


def lesson_files(course: Path) -> list[Path]:
    return [Path(p) for p in sorted(glob.glob(str(course / "lessons" / "*.html")))]


def lint_failures(course: Path, state: dict, unit_id: str) -> list[str]:
    ids = group_ids(state, unit_id)
    expected = set(ids)
    failures: list[str] = []
    matches: list[Path] = []
    for lesson in lesson_files(course):
        html = lesson.read_text(encoding="utf-8")
        covered = data_chapters(html)
        # lessons without data-chapters (e.g. pre-adoption ones) don't participate
        if covered is None or not (expected & set(covered)):
            continue
        name = lesson.relative_to(course)
        if len(covered) != len(set(covered)):
            failures.append(f"duplicate data-chapters in {name}: {covered}")
        if set(covered) == expected:
            matches.append(lesson)
        else:
            failures.append(f"data-chapters mismatch in {name}: expected {ids}, got {covered}")
    if len(matches) != 1:
        failures.append(f"expected exactly one lesson with data-chapters {ids}, found {len(matches)}")
    return failures


def command_lint(course: Path, unit_id: str) -> int:
    try:
        state = load_state(course)
        failures = lint_failures(course, state, unit_id)
    except Exception as exc:
        return fail(str(exc))
    if failures:
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1
    return 0


def command_mark(course: Path, unit_id: str, new_state: str) -> int:
    if new_state not in STATES:
        return fail(f"unknown state: {new_state}")
    try:
        state = load_state(course)
        members = group_units(state, unit_id)
    except Exception as exc:
        return fail(str(exc))
    current_states = {u.get("state") for u in members}
    if len(current_states) != 1:
        return fail(f"group invariant broken: mixed states for {group_ids(state, unit_id)}")
    current = next(iter(current_states))
    if STATES.index(new_state) != STATES.index(current) + 1:
        return fail(f"illegal transition: {current} -> {new_state}")
    if new_state == "taught":
        if any(u.get("skipped") for u in members):
            return fail("cannot mark skipped unit/group taught")
        failures = lint_failures(course, state, unit_id)
        if failures:
            for item in failures:
                print(f"- {item}", file=sys.stderr)
            return 1
    timestamp = datetime.now(timezone.utc).isoformat() if new_state == "taught" else None
    for unit in members:
        unit["state"] = new_state
        if timestamp:
            unit["taught_at"] = timestamp
    atomic_write_json(state_path(course), state)
    return 0


def record_chapters(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} missing frontmatter chapters")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError(f"{path} missing frontmatter chapters")
    front = text[3:end].splitlines()
    for i, line in enumerate(front):
        if re.match(r"^chapters:\s*\[", line):
            inside = line.split("[", 1)[1].rsplit("]", 1)[0]
            chapters = [p.strip().strip("'\"") for p in inside.split(",") if p.strip()]
            if not chapters:
                raise ValueError(f"{path} missing frontmatter chapters")
            return chapters
        if line.strip() == "chapters:":
            chapters: list[str] = []
            for child in front[i + 1 :]:
                if not child.startswith((" ", "\t")):
                    break
                match = re.search(r"-\s*['\"]?([0-9]{2})['\"]?", child)
                if match:
                    chapters.append(match.group(1))
            if not chapters:
                raise ValueError(f"{path} missing frontmatter chapters")
            return chapters
    raise ValueError(f"{path} missing frontmatter chapters")


def proposed_state(course: Path) -> dict:
    units = scan_chapters(course)
    ids = {u["id"] for u in units}
    by_id = {u["id"]: u for u in units}
    lesson_groups: list[list[str]] = []
    seen_group_for: dict[str, set[str]] = {}
    taught: set[str] = set()
    for lesson in lesson_files(course):
        covered = data_chapters(lesson.read_text(encoding="utf-8")) or []
        unknown = sorted(set(covered) - ids)
        if unknown:
            raise ValueError(f"{lesson} references unknown chapters: {unknown}")
        if len(covered) != len(set(covered)):
            raise ValueError(f"{lesson} has duplicate data-chapters: {covered}")
        covered_set = set(covered)
        for unit_id in covered:
            old = seen_group_for.get(unit_id)
            if old and old != covered_set:
                raise ValueError(f"inconsistent lesson groups for {unit_id}: {sorted(old)} vs {covered}")
            seen_group_for[unit_id] = covered_set
        taught.update(covered)
        if len(covered) > 1:
            lesson_groups.append(covered)

    records: list[tuple[Path, list[str]]] = []
    for record in sorted((course / "learning-records").glob("*.md")):
        chapters = record_chapters(record)
        unknown = sorted(set(chapters) - ids)
        if unknown:
            raise ValueError(f"{record} references unknown chapters: {unknown}")
        records.append((record, chapters))
        taught.update(chapters)

    for group in lesson_groups:
        group_set = set(group)
        for record, chapters in records:
            chapter_set = set(chapters)
            if group_set & chapter_set and group_set != chapter_set:
                raise ValueError(f"mixed inferred states for merged group {group}; partial record {record}: {chapters}")
        for unit_id in group:
            by_id[unit_id]["plan_group"] = f"g{group[0]}"

    for unit_id in taught:
        by_id[unit_id]["state"] = "taught"

    return {"schema_version": 1, "course_slug": course.name, "plan_applied": False, "units": units}


def old_verified_ids(course: Path) -> list[str]:
    try:
        old = json.loads(state_path(course).read_text(encoding="utf-8"))
    except Exception:
        return []
    return sorted(u["id"] for u in old.get("units", []) if u.get("state") == "verified")


def command_rebuild(course: Path, confirm: bool) -> int:
    try:
        state = proposed_state(course)
    except Exception as exc:
        return fail(str(exc))
    notices = ["notice: plan_order/skipped have no file evidence; using original order and skipped=false"]
    verified = old_verified_ids(course)
    if verified:
        notices.append(f"notice: verified has no file evidence; recovered as taught: {verified}")
    else:
        notices.append("notice: verified has no file evidence; recovered course can only prove taught")
    for notice in notices:
        print(notice)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    if confirm:
        atomic_write_json(state_path(course), state)
    return 0


def main(argv: list[str] | None = None) -> int:
    course_parent = argparse.ArgumentParser(add_help=False)
    course_parent.add_argument("--course", default=argparse.SUPPRESS)
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", default=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", parents=[course_parent])
    p_init.add_argument("--force", action="store_true")
    sub.add_parser("status", parents=[course_parent])
    sub.add_parser("next", parents=[course_parent])
    p_plan = sub.add_parser("plan", parents=[course_parent])
    p_plan.add_argument("plan_file")
    p_mark = sub.add_parser("mark", parents=[course_parent])
    p_mark.add_argument("id")
    p_mark.add_argument("state")
    p_lint = sub.add_parser("lint", parents=[course_parent])
    p_lint.add_argument("id")
    p_rebuild = sub.add_parser("rebuild", parents=[course_parent])
    p_rebuild.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if not hasattr(args, "course"):
        return fail("--course is required")
    course = Path(args.course)
    try:
        if args.command == "init":
            return command_init(course, args.force)
        if args.command == "status":
            return command_status(course)
        if args.command == "next":
            return command_next(course)
        if args.command == "plan":
            return command_plan(course, args.plan_file)
        if args.command == "mark":
            return command_mark(course, args.id, args.state)
        if args.command == "lint":
            return command_lint(course, args.id)
        if args.command == "rebuild":
            return command_rebuild(course, args.confirm)
    except Exception as exc:
        return fail(str(exc))
    return fail("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
