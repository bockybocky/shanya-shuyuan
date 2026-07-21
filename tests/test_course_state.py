import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "course_state.py"


def run(course, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--course", str(course)],
        text=True,
        capture_output=True,
    )


def write_chapter(course, unit_id, title=None):
    path = course / "book" / "chapters" / f"{unit_id}_chapter{unit_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"# {title or 'Chapter ' + unit_id}\n\nbody"
    path.write_text(f"---\nseq: {int(unit_id)}\nsource: x\nchars: {len(body)}\n---\n\n{body}\n", encoding="utf-8")


def make_course(tmp_path, ids=("01", "02", "03")):
    course = tmp_path / "course"
    for unit_id in ids:
        write_chapter(course, unit_id)
    (course / "lessons").mkdir(parents=True, exist_ok=True)
    (course / "learning-records").mkdir(parents=True, exist_ok=True)
    return course


def state(course):
    return json.loads((course / "course_state.json").read_text(encoding="utf-8"))


def write_plan(tmp_path, data):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def lesson(course, name, chapters, body="ok"):
    path = course / "lessons" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<html><body data-chapters="{chapters}">{body}</body></html>', encoding="utf-8")
    return path


def record(course, name, front):
    path = course / "learning-records" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(front + "\nbody\n", encoding="utf-8")
    return path


def test_init_scans_refuses_and_force_overwrites(tmp_path):
    course = make_course(tmp_path, ("01", "02"))

    first = run(course, "init")
    assert first.returncode == 0
    assert "01 Chapter 01" in first.stdout
    assert state(course)["units"][0]["file"] == "book/chapters/01_chapter01.md"

    refused = run(course, "init")
    assert refused.returncode == 1
    assert "already exists" in refused.stderr

    write_chapter(course, "03", "Third")
    forced = run(course, "init", "--force")
    assert forced.returncode == 0
    assert [u["id"] for u in state(course)["units"]] == ["01", "02", "03"]


def test_status_next_and_merged_plan_skip(tmp_path):
    course = make_course(tmp_path, ("01", "02", "03", "04"))
    assert run(course, "init").returncode == 0
    plan = write_plan(tmp_path, {"units": [{"ids": ["02", "03"]}, {"ids": ["04"]}], "skip": ["01"]})
    assert run(course, "plan", str(plan)).returncode == 0

    nxt = run(course, "next")
    assert nxt.returncode == 0
    assert json.loads(nxt.stdout) == {"ids": ["02", "03"], "titles": ["Chapter 02", "Chapter 03"]}

    status = run(course, "status")
    assert status.returncode == 0
    assert "current: 02 Chapter 02" in status.stdout
    assert "02 [pending] group=g02 Chapter 02" in status.stdout
    assert "skipped:\n01 [pending] Chapter 01" in status.stdout


def test_plan_validation_and_replan_rules(tmp_path):
    course = make_course(tmp_path, ("01", "02", "03", "04"))
    assert run(course, "init").returncode == 0
    bad_plans = [
        {"units": [{"ids": ["01"]}], "skip": ["02"]},
        {"units": [{"ids": ["01", "01"]}, {"ids": ["02"]}, {"ids": ["03"]}, {"ids": ["04"]}], "skip": []},
        {"units": [{"ids": ["01"]}, {"ids": ["02"]}, {"ids": ["03"]}, {"ids": ["99"]}], "skip": ["04"]},
        {"units": [{"ids": ["01"]}, {"ids": ["02"]}, {"ids": ["03"]}], "skip": ["03", "04"]},
    ]
    for i, data in enumerate(bad_plans):
        result = run(course, "plan", str(write_plan(tmp_path, data)))
        assert result.returncode == 1, i
        assert "invalid plan partition" in result.stderr

    valid = write_plan(tmp_path, {"units": [{"ids": ["01"]}, {"ids": ["02"]}, {"ids": ["03"]}], "skip": ["04"]})
    assert run(course, "plan", str(valid)).returncode == 0
    lesson(course, "0001.html", "01")
    assert run(course, "mark", "01", "taught").returncode == 0
    assert run(course, "mark", "01", "verified").returncode == 0

    skip_verified = write_plan(tmp_path, {"units": [{"ids": ["02"]}, {"ids": ["03"]}, {"ids": ["04"]}], "skip": ["01"]})
    assert "cannot skip non-pending" in run(course, "plan", str(skip_verified)).stderr

    regroup_verified = write_plan(tmp_path, {"units": [{"ids": ["01", "02"]}, {"ids": ["03"]}, {"ids": ["04"]}], "skip": []})
    assert "cannot change group composition" in run(course, "plan", str(regroup_verified)).stderr

    unskip_pending = write_plan(tmp_path, {"units": [{"ids": ["01"]}, {"ids": ["04"]}, {"ids": ["02", "03"]}], "skip": []})
    assert run(course, "plan", str(unskip_pending)).returncode == 0
    data = state(course)
    assert {u["id"]: u["state"] for u in data["units"]}["01"] == "verified"
    assert unit(data, "04")["skipped"] is False


def unit(data, unit_id):
    return next(u for u in data["units"] if u["id"] == unit_id)


def test_mark_chain_group_atomicity_and_lint(tmp_path):
    course = make_course(tmp_path, ("01", "02", "03"))
    assert run(course, "init").returncode == 0
    plan = write_plan(tmp_path, {"units": [{"ids": ["01", "02"]}], "skip": ["03"]})
    assert run(course, "plan", str(plan)).returncode == 0

    assert "illegal transition" in run(course, "mark", "01", "verified").stderr
    assert "unknown id" in run(course, "mark", "99", "taught").stderr
    assert "expected exactly one lesson" in run(course, "lint", "01").stderr

    mismatch = lesson(course, "bad.html", "01")
    lint_bad = run(course, "lint", "02")
    assert lint_bad.returncode == 1
    assert "data-chapters mismatch" in lint_bad.stderr
    mismatch.unlink()

    lesson(course, "merged.html", "02,01")
    taught = run(course, "mark", "02", "taught")
    assert taught.returncode == 0
    data = state(course)
    assert unit(data, "01")["state"] == unit(data, "02")["state"] == "taught"
    assert unit(data, "01")["taught_at"] == unit(data, "02")["taught_at"]

    verified = run(course, "mark", "01", "verified")
    assert verified.returncode == 0
    assert unit(state(course), "02")["state"] == "verified"

    lesson(course, "skipped.html", "03")
    skipped = run(course, "mark", "03", "taught")
    assert skipped.returncode == 1
    assert "skipped" in skipped.stderr


def test_mark_rejects_mixed_group_state(tmp_path):
    course = make_course(tmp_path, ("01", "02"))
    assert run(course, "init").returncode == 0
    plan = write_plan(tmp_path, {"units": [{"ids": ["01", "02"]}], "skip": []})
    assert run(course, "plan", str(plan)).returncode == 0
    data = state(course)
    unit(data, "01")["state"] = "taught"
    (course / "course_state.json").write_text(json.dumps(data), encoding="utf-8")

    result = run(course, "mark", "02", "taught")
    assert result.returncode == 1
    assert "group invariant broken" in result.stderr


def test_rebuild_errors_and_confirm_writes_recovered_state(tmp_path):
    dup = make_course(tmp_path / "dup", ())
    write_chapter(dup, "01")
    (dup / "book" / "chapters" / "01_other.md").write_text("# duplicate\n", encoding="utf-8")
    assert "duplicate chapter ids" in run(dup, "rebuild").stderr

    missing = make_course(tmp_path / "missing", ("01",))
    record(missing, "0001.md", "---\naction: x\n---")
    missing_result = run(missing, "rebuild")
    assert missing_result.returncode == 1
    assert "missing frontmatter chapters" in missing_result.stderr

    mixed = make_course(tmp_path / "mixed", ("01", "02"))
    lesson(mixed, "merged.html", "01,02")
    record(mixed, "0001.md", "---\nchapters: [01]\n---")
    mixed_result = run(mixed, "rebuild")
    assert mixed_result.returncode == 1
    assert "mixed inferred states" in mixed_result.stderr

    course = make_course(tmp_path / "ok", ("01", "02", "03"))
    lesson(course, "merged.html", "01,02")
    record(course, "0001.md", "---\nchapters:\n  - 01\n  - 02\n---")
    record(course, "0002.md", "---\nchapters: [03]\n---")
    old = {
        "schema_version": 1,
        "course_slug": "course",
        "plan_applied": True,
        "units": [{"id": "03", "state": "verified"}],
    }
    (course / "course_state.json").write_text(json.dumps(old), encoding="utf-8")

    preview = run(course, "rebuild")
    assert preview.returncode == 0
    assert "plan_order/skipped have no file evidence" in preview.stdout
    assert "verified has no file evidence" in preview.stdout
    assert unit(json.loads(preview.stdout[preview.stdout.index("{") :]), "03")["state"] == "taught"

    confirmed = run(course, "rebuild", "--confirm")
    assert confirmed.returncode == 0
    data = state(course)
    assert unit(data, "01")["plan_group"] == "g01"
    assert unit(data, "02")["plan_group"] == "g01"
    assert [unit(data, i)["state"] for i in ("01", "02", "03")] == ["taught", "taught", "taught"]
    assert data["plan_applied"] is False
