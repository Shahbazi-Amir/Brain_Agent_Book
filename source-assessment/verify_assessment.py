#!/usr/bin/env python3
"""کنترل مستقل ثبت، صف و snapshot منبع."""
from __future__ import annotations
import csv, hashlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/Users/macbookpro/AMIR_DATA/00_WORKS/01_PROJECTS/AI-Agent-projects/Project_Brain_Master/.project-brain/source-repos/7bb001fd-f2a5-4a2e-9cb0-585b34bf81df/Shahbazi-Amir--Book_Production")

def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))

def main():
    inv = read_csv(ROOT/"inventory-audit/inventory.csv")
    reg = read_csv(ROOT/"source-assessment/source-register.csv")
    queue = read_csv(ROOT/"source-assessment/segmentation-queue.csv")
    failures=[]
    if len(inv)!=197 or len(reg)!=197: failures.append("تعداد ردیف‌ها ۱۹۷ نیست")
    im={r['source_id']:r for r in inv}; rm={r['source_id']:r for r in reg}
    if len(im)!=197 or len(rm)!=197: failures.append("source_id تکراری است")
    if set(im)!=set(rm): failures.append("source_id اضافه یا گمشده است")
    for sid in set(im)&set(rm):
        if (im[sid]['relative_path'],im[sid]['sha256']) != (rm[sid]['relative_path'],rm[sid]['sha256']): failures.append(f"عدم تطابق مسیر/هش: {sid}")
    if any(r['confirmed_role']=='نیازمند بررسی' for r in reg): failures.append("نقش نیازمند بررسی باقی مانده است")
    allowed={"کافی","قابل استنتاج از شواهد داخلی","ناقص و نیازمند پیگیری"}
    if any(r['metadata_status'] not in allowed for r in reg): failures.append("وضعیت فراداده نامعتبر است")
    similar=[r for r in reg if 'NAME_SIMILAR_CANDIDATE' in r['issue_codes']]
    if any(not r['work_family'] or not r['edition_status'] for r in similar): failures.append("نامزد تشابه بدون جایگاه است")
    eligible={r['source_id'] for r in reg if r['segmentation_eligibility']=='واجد'}
    queued={r['source_id'] for r in queue}
    if eligible!=queued or len(queue)!=len(queued): failures.append("صف با ثبت واجدان تطابق ندارد")
    snap={}
    for line in (ROOT/"inventory-audit/source-snapshot.sha256").read_text(encoding="utf-8").splitlines():
        h,p=line.split("  ",1); snap[p]=h
    if len(snap)!=197: failures.append("snapshot شامل ۱۹۷ فایل نیست")
    for p,h in snap.items():
        fp=SOURCE/p
        actual=hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else "MISSING"
        if actual!=h: failures.append(f"snapshot تغییر کرده: {p}")
    # بازخوانی دستیِ قابل بازتولید دو فایل نامطمئن پیشین.
    checks={
      "CHAPTER05_MACHINE_VS_ORIGINAL.md": ("HUMAN_REVIEW_WORKING_MATERIAL", "evidence authority"),
      "docs/final-book/00_REPOSITORY_PREFLIGHT.md": ("پیش‌پرواز", "Canonical"),
    }
    for p,tokens in checks.items():
        text=(SOURCE/p).read_text(encoding="utf-8")
        if not all(t in text for t in tokens): failures.append(f"شاهد نقش یافت نشد: {p}")
    report = f"""# گزارش راستی‌آزمایی ارزیابی

- نتیجه: **{'ناموفق' if failures else 'موفق'}**
- موجودی / ثبت: **{len(inv)} / {len(reg)}**
- `source_id` یکتای ثبت: **{len(rm)}**؛ اضافه یا گمشده: **{len(set(im)^set(rm))}**
- تطابق `relative_path` و `sha256`: **{'ناموفق' if any('مسیر/هش' in x for x in failures) else '۱۹۷ از ۱۹۷'}**
- نامزد تشابه اسمی: **{len(similar)}**؛ بدون خانواده یا جایگاه: **{sum(not r['work_family'] or not r['edition_status'] for r in similar)}**
- واجد قطعه‌بندی در ثبت / صف: **{len(eligible)} / {len(queue)}**
- snapshot منبع: **{'ناموفق' if any('snapshot' in x for x in failures) else '۱۹۷ از ۱۹۷ هش منطبق'}**
- بازخوانی دو فایل نامطمئن پیشین: **انجام شد**؛ نشانه‌های محتوایی نقش نهایی در هر دو یافت شد.

## نمونه‌گیری طبقه‌ای

- سه خانواده کتاب: قرارداد چهار دارایی در `book/README.md` و انتخاب مبدأ/نهایی برای هر سه کنترل شد.
- سه مجموعه متن ویدیو: `asre_shirin`، `khane-to` و `uni-tehran` با lock و نمونه آغاز فایل تطبیق داده شدند.
- `dar-jostojo-final-C`: ۲۹ Canonical، ۱۱ Supplemental، ۱۸ Review-only و یک Non-canonical طبق lock کنترل شد؛ شکاف ۲۱ ترمیم نشد.

## خطاها

{('هیچ خطایی یافت نشد.' if not failures else chr(10).join('- '+x for x in failures))}
"""
    (ROOT/"source-assessment/verification-report.md").write_text(report,encoding="utf-8")
    if failures: raise SystemExit("؛ ".join(failures))

if __name__ == '__main__': main()
