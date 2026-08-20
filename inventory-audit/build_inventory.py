#!/usr/bin/env python3
"""ساخت موجودی بازتولیدپذیر از یک مخزن فقط‌خواندنی."""
from __future__ import annotations

import argparse, csv, hashlib, json, mimetypes, re, subprocess, sys, zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

FIELDS = ["source_id", "relative_path", "filename", "extension", "media_type",
          "size_bytes", "sha256", "role", "readability_status", "extraction_status",
          "probable_title", "probable_author", "language", "duplicate_group",
          "issue_codes", "notes"]
TEXT_EXT = {".md", ".txt", ".py", ".yml", ".yaml", ".json", ".gitignore"}
MANAGEMENT_NAMES = {".gitignore", "README.md", "PROJECT_STATE.md", "CHAPTER05_REVIEW_README.md"}

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def run_git(root: Path) -> tuple[str, str]:
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
                            text=True, capture_output=True, check=False).stdout
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          text=True, capture_output=True, check=False).stdout.strip()
    return head, status

def decode_text(path: Path) -> tuple[str, str | None]:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16"):
        try: return data.decode(enc), None
        except UnicodeDecodeError: pass
    return "", "ENCODING_UNSUPPORTED"

def docx_text(path: Path) -> tuple[str, str | None]:
    try:
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" not in z.namelist(): return "", "DOCX_STRUCTURE_INVALID"
            root = ET.fromstring(z.read("word/document.xml"))
            paragraphs = []
            for para in (n for n in root.iter() if n.tag.endswith("}p")):
                paragraphs.append("".join(t.text or "" for t in para.iter() if t.tag.endswith("}t")))
            text = "\n".join(paragraphs)
            return text, None
    except (zipfile.BadZipFile, ET.ParseError, OSError):
        return "", "DOCX_CORRUPT"

def pdf_text(path: Path) -> tuple[str, str | None]:
    try:
        import fitz  # type: ignore
        doc = fitz.open(path)
        sample = "\n".join(page.get_text() for page in list(doc)[:5])
        doc.close()
        return sample, None
    except ImportError:
        data = path.read_bytes()
        return ("", None) if data.startswith(b"%PDF-") and b"%%EOF" in data[-4096:] else ("", "PDF_STRUCTURE_INVALID")
    except Exception:
        return "", "PDF_CORRUPT"

def language(text: str) -> str:
    fa = len(re.findall(r"[\u0600-\u06ff]", text)); en = len(re.findall(r"[A-Za-z]", text))
    if fa and en and min(fa, en) / max(fa, en) >= .08: return "فارسی و انگلیسی"
    if fa: return "فارسی"
    if en: return "انگلیسی"
    return "نامشخص"

def metadata(text: str, path: Path) -> tuple[str, str]:
    title = ""
    for line in text[:20000].splitlines():
        s = re.sub(r"^\s*#+\s*", "", line).strip()
        if s and len(s) <= 200 and not s.startswith(("---", "```", "<")):
            title = s; break
    if not title:
        stem = path.stem.replace("_", " ").replace("-", " ").strip()
        if stem and not re.fullmatch(r"(?:episode|site)?\s*\d+", stem, re.I): title = stem
    author = ""
    patterns = [r"(?im)^\s*(?:نویسنده|مولف|مؤلف)\s*[:：]\s*(.{2,100})$",
                r"(?im)^\s*(?:author|by)\s*[:：]\s*(.{2,100})$"]
    for pat in patterns:
        m = re.search(pat, text[:30000])
        if m: author = m.group(1).strip(" *#"); break
    return title, author

def role_for(rel: str, ext: str) -> str:
    p = Path(rel); low = rel.lower()
    if rel.startswith(".github/") or p.name in MANAGEMENT_NAMES or "governance/locks/" in low: return "مدیریتی"
    if ext == ".py": return "کد"
    if ext in {".json", ".yml", ".yaml"}: return "داده"
    if "report" in low or "audit" in low or "review" in low or "changes" in low or "candidate-differences" in low: return "فایل پشتیبان"
    if rel.startswith("tools/") or rel.startswith("scripts/") or p.name == "requirements.txt": return "دارایی فنی"
    if rel.startswith("final/") or rel.startswith("book/") or "original_extract" in low: return "فایل ماهوی"
    return "نیازمند بررسی"

def make_row(root: Path, path: Path) -> dict:
    rel = path.relative_to(root).as_posix(); ext = path.suffix.lower() or (path.name if path.name.startswith(".") else "")
    size = path.stat().st_size; issues = []; text = ""; error = None
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if ext in TEXT_EXT:
        text, error = decode_text(path); media = "text/markdown" if ext == ".md" else media
    elif ext == ".docx":
        text, error = docx_text(path); media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == ".pdf":
        text, error = pdf_text(path); media = "application/pdf"
    else: error = "FORMAT_UNSUPPORTED"
    if size == 0: issues.append("EMPTY_FILE")
    if error: issues.append(error)
    supported = ext in TEXT_EXT | {".docx", ".pdf"}
    if error and error != "FORMAT_UNSUPPORTED": readable, extraction = "ناخوانا", "ناموفق"
    elif not supported: readable, extraction = "نیازمند بررسی", "پشتیبانی‌نشده"
    elif text.strip(): readable, extraction = "خوانا", "موفق"
    elif ext == ".pdf" and not error: readable, extraction = "قابل بازشدن", "بدون متن قابل استخراج"
    elif size == 0: readable, extraction = "خالی", "ناموفق"
    else: readable, extraction = "قابل بازشدن", "بدون متن قابل استخراج"
    if ext == ".pdf" and not text.strip() and not error: issues.append("OCR_OR_HUMAN_REVIEW_NEEDED")
    title, author = metadata(text, path)
    if not title or not author: issues.append("INSUFFICIENT_METADATA")
    notes = []
    if title: notes.append("عنوان احتمالی از نخستین سطر معنادار یا نام فایل گرفته شده است.")
    if not author: notes.append("مؤلف به‌طور صریح در نمونه متن شناسایی نشد.")
    if ext == ".md" and ("episode-" in path.name.lower() or "transcript" in rel.lower()):
        notes.append("این فایل متن ویدیو تلقی شد؛ فایل ویدیویی متناظر در موجودی مخزن یافت نشد.")
        issues.append("VIDEO_COUNTERPART_ABSENT")
    return {"source_id": "SRC-" + hashlib.sha256(rel.encode()).hexdigest()[:16], "relative_path": rel,
            "filename": path.name, "extension": ext, "media_type": media, "size_bytes": size,
            "sha256": digest(path), "role": role_for(rel, ext), "readability_status": readable,
            "extraction_status": extraction, "probable_title": title, "probable_author": author,
            "language": language(text), "duplicate_group": "", "issue_codes": ";".join(sorted(set(issues))),
            "notes": " ".join(notes)}

def table(counter: Counter) -> str:
    lines = ["| مقدار | تعداد |", "|---|---:|"]
    lines += [f"| {k or 'ثبت‌نشده'} | {v} |" for k, v in sorted(counter.items(), key=lambda x: (-x[1], x[0]))]
    lines.append(f"| **جمع** | **{sum(counter.values())}** |")
    return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(description="تهیه موجودی ممیزی‌پذیر مخزن منبع")
    ap.add_argument("source_root", type=Path); ap.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args(); root = args.source_root.resolve(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    before_head, before_status = run_git(root)
    paths = sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts)
    rows = [make_row(root, p) for p in paths]
    by_hash = defaultdict(list)
    for row in rows: by_hash[row["sha256"]].append(row)
    dup_no = 0
    for sha, group in sorted(by_hash.items()):
        if len(group) > 1:
            dup_no += 1; dg = f"DUP-{dup_no:03d}"
            for i, row in enumerate(sorted(group, key=lambda r: r["relative_path"])):
                row["duplicate_group"] = dg
                if i: row["role"] = "نسخه تکراری"
                row["notes"] += " همسانی بایتی با اعضای گروه تکرار به کمک SHA-256 اثبات شد."
    by_name = defaultdict(list)
    for row in rows: by_name[row["filename"].casefold()].append(row)
    for group in by_name.values():
        if len(group) > 1 and len({r["sha256"] for r in group}) > 1:
            for row in group:
                codes = set(filter(None, row["issue_codes"].split(";"))); codes.add("NAME_SIMILAR_CANDIDATE")
                row["issue_codes"] = ";".join(sorted(codes)); row["notes"] += " نام مشابه فقط نامزد بررسی تکرار است و همسانی بایتی ندارد."
    with (out / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    with (out / "source-snapshot.sha256").open("w", encoding="utf-8") as f:
        for r in rows: f.write(f'{r["sha256"]}  {r["relative_path"]}\n')
    issue_counts = Counter(code for r in rows for code in r["issue_codes"].split(";") if code)
    summary = f"""# خلاصه موجودی مخزن منبع

این گزارش به‌صورت ماشینی از `inventory.csv` ساخته شده است. قاعده پیمایش: همه فایل‌های زیر ریشه منبع، به‌جز محتوای داخلی `.git/`. تعداد کل: **{len(rows)} فایل**.

## نوع رسانه

{table(Counter(r['media_type'] for r in rows))}

## نقش

{table(Counter(r['role'] for r in rows))}

## وضعیت خوانایی

{table(Counter(r['readability_status'] for r in rows))}

## وضعیت استخراج

{table(Counter(r['extraction_status'] for r in rows))}

## نوع مشکل

هر فایل ممکن است بیش از یک کد مشکل داشته باشد؛ بنابراین جمع این جدول لزوماً برابر تعداد فایل‌ها نیست.

{table(issue_counts)}

## تکرارهای قطعی

تعداد گروه‌های همسان بایتی: **{dup_no}**. عضویت فقط با برابری کامل `sha256` تعیین شده است.
"""
    (out / "inventory-summary.md").write_text(summary, encoding="utf-8")
    problematic = [r for r in rows if r["issue_codes"]]
    issue_lines = ["# گزارش مشکلات ورودی", "", f"در {len(problematic)} فایل دست‌کم یک مسئله ثبت شده است. کدها تشخیصی‌اند و موارد نامطمئن برای بازبینی نگه داشته شده‌اند.", "",
                   "| source_id | مسیر | کدها | وضعیت استخراج |", "|---|---|---|---|"]
    issue_lines += [f"| {r['source_id']} | `{r['relative_path']}` | {r['issue_codes']} | {r['extraction_status']} |" for r in problematic]
    (out / "input-issues.md").write_text("\n".join(issue_lines) + "\n", encoding="utf-8")
    after_head, after_status = run_git(root)
    evidence = f"""# شواهد عدم تغییر مخزن منبع

- ریشه بررسی‌شده: `{root}`
- قاعده پیمایش: همه فایل‌ها به‌جز فایل‌های داخلی `.git/`
- تعداد فایل در آغاز/پایان اجرای موجودی: {len(paths)}
- Git HEAD پیش از اجرا: `{before_head}`
- Git HEAD پس از اجرا: `{after_head}`
- وضعیت Git پیش از اجرا: {"پاک" if not before_status else "دارای تغییر از پیش موجود"}
- وضعیت Git پس از اجرا: {"پاک" if not after_status else "دارای تغییر"}
- برابری وضعیت پیش و پس: {"بله" if before_status == after_status and before_head == after_head else "خیر"}
- فهرست کامل هش‌ها: `source-snapshot.sha256`

## فرمان بازتولید

```bash
python3 inventory-audit/build_inventory.py '{root}' --output inventory-audit
python3 inventory-audit/verify_inventory.py '{root}' inventory-audit/inventory.csv
```
"""
    (out / "source-integrity.md").write_text(evidence, encoding="utf-8")
    print(f"موجودی {len(rows)} فایل در {out} ساخته شد.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
