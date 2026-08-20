#!/usr/bin/env python3
import csv, hashlib, re, sys
from collections import Counter, defaultdict
from pathlib import Path

root, csv_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
with csv_path.open(encoding="utf-8-sig", newline="") as f: rows = list(csv.DictReader(f))
paths = sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts)
assert len(paths) == len(rows), (len(paths), len(rows))
assert len({r["source_id"] for r in rows}) == len(rows)
assert len({r["relative_path"] for r in rows}) == len(rows)
assert {p.relative_to(root).as_posix() for p in paths} == {r["relative_path"] for r in rows}
groups = defaultdict(list)
for r in rows:
    assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"])
    assert r["source_id"] == "SRC-" + hashlib.sha256(r["relative_path"].encode()).hexdigest()[:16]
    h = hashlib.sha256((root / r["relative_path"]).read_bytes()).hexdigest()
    assert h == r["sha256"]
    if r["duplicate_group"]: groups[r["duplicate_group"]].append(r)
for key, group in groups.items():
    assert len(group) > 1 and len({r["sha256"] for r in group}) == 1, key
summary = csv_path.with_name("inventory-summary.md").read_text(encoding="utf-8")
sections = {
    "نوع رسانه": Counter(r["media_type"] for r in rows),
    "نقش": Counter(r["role"] for r in rows),
    "وضعیت خوانایی": Counter(r["readability_status"] for r in rows),
    "وضعیت استخراج": Counter(r["extraction_status"] for r in rows),
}
for title, counts in sections.items():
    block = summary.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]
    assert f"| **جمع** | **{sum(counts.values())}** |" in block, title
    for key, value in counts.items(): assert f"| {key} | {value} |" in block, (title, key)
ext_samples = defaultdict(list)
for r in rows: ext_samples[r["extension"]].append(r)
for ext, sample in ext_samples.items():
    for r in sample[:min(3, len(sample))]:
        assert (root / r["relative_path"]).is_file()
        assert r["readability_status"] in {"خوانا", "قابل بازشدن", "ناخوانا", "خالی", "نیازمند بررسی"}
        assert r["extraction_status"] in {"موفق", "بدون متن قابل استخراج", "ناموفق", "پشتیبانی‌نشده"}
print(f"تأیید شد: {len(rows)} ردیف، مسیر و شناسه یکتا، همه هش‌ها، جمع‌های گزارش، نمونه‌های هر قالب، و {len(groups)} گروه تکرار قطعی.")
