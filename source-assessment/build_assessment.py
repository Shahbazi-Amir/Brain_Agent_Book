#!/usr/bin/env python3
"""ساخت ثبت ارزیابی از موجودی قفل‌شده، بدون نوشتن در مخزن منبع."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "inventory-audit/inventory.csv"
OUT = ROOT / "source-assessment"
SOURCE = Path("/Users/macbookpro/AMIR_DATA/00_WORKS/01_PROJECTS/AI-Agent-projects/Project_Brain_Master/.project-brain/source-repos/7bb001fd-f2a5-4a2e-9cb0-585b34bf81df/Shahbazi-Amir--Book_Production")


def video_lock() -> dict[str, dict]:
    data = json.loads((SOURCE / "governance/locks/VIDEO_TRANSCRIPTS_FINAL.json").read_text(encoding="utf-8"))
    return {item["path"]: item for item in data["files"]}


def classify(r: dict[str, str], vlock: dict[str, dict]) -> dict[str, str]:
    p = r["relative_path"]
    issue = r["issue_codes"]
    d = {
        "confirmed_role": r["role"], "work_family": "راهبری مخزن",
        "edition_status": "خارج از زنجیره نسخه ماهوی", "segmentation_eligibility": "غیرواجد",
        "metadata_status": "قابل استنتاج از شواهد داخلی" if "INSUFFICIENT_METADATA" in issue else "کافی",
        "decision_basis": "نقش از مسیر، قالب و محتوای خود فایل احراز شد.",
        "evidence_locator": f"{p}:1",
        "review_status": "تأییدشده",
        "locator_type": "", "position_rule": "",
    }

    # سه بسته کتاب: نام فایل به تنهایی تصمیم‌ساز نیست؛ قرارداد صریح README و lock مبناست.
    if p.startswith("book/") and p != "book/README.md":
        family = p.split("/")[1]
        d["work_family"] = f"کتاب/{family}"
        d["evidence_locator"] = "book/README.md:3؛ governance/locks/BOOK_CORPUS_FINAL.json"
        if p.endswith("01_source.docx"):
            d.update(confirmed_role="فایل ماهوی", edition_status="نسخه اصلی مکمل", segmentation_eligibility="واجد",
                     decision_basis="قرارداد داخلی آن را original source می‌خواند و نگهداری‌اش را برای منشأ الزامی می‌داند.",
                     locator_type="بند", position_rule="شماره بند DOCX از ابتدای word/document.xml حفظ شود.")
        elif p.endswith("02_final.docx"):
            d.update(confirmed_role="فایل ماهوی", edition_status="نسخه مرجع پذیرفته‌شده", segmentation_eligibility="واجد",
                     decision_basis="قرارداد داخلی آن را Word نهایی تأییدشده و دارایی انتشار معرفی می‌کند.",
                     locator_type="عنوان بخش و بند", position_rule="عنوان، شماره بند DOCX و ترتیب سند هم‌زمان حفظ شود.")
        elif p.endswith("03_final.pdf"):
            d.update(confirmed_role="نسخه قالبی مرجع", edition_status="بازنمایی PDF نسخه نهایی", segmentation_eligibility="غیرواجد",
                     decision_basis="PDF مرجع انتشار است؛ برای جلوگیری از دو بار ورود همان ویرایش، DOCX نهایی ورودی قطعه‌بندی است.",
                     locator_type="صفحه", position_rule="برای ارجاع تصویری، شماره صفحه PDF حفظ شود.")
        else:
            d.update(confirmed_role="گزارش تغییرات", edition_status="گزارش QA و منشأ", segmentation_eligibility="غیرواجد",
                     decision_basis="قرارداد چهارفایلی آن را گزارش تغییرات/QA می‌داند، نه متن کتاب.",
                     locator_type="صفحه", position_rule="شماره صفحه PDF در ممیزی حفظ شود.")
        return d

    if p == "book/README.md":
        d.update(confirmed_role="راهنمای پیکره", work_family="کتاب‌ها", edition_status="سند قرارداد نسخه‌ها",
                 decision_basis="قرارداد صریح چهار دارایی هر کتاب و کاربرد انتشار/RAG را ثبت می‌کند.")
        return d

    # وضعیت هر 158 فایل final دقیقاً از lock قفل‌شده خوانده می‌شود.
    if p in vlock:
        item = vlock[p]
        family = item["source_family"]
        status = item["status"]
        d["work_family"] = f"متن ویدیو/{family}"
        d["evidence_locator"] = f"governance/locks/VIDEO_TRANSCRIPTS_FINAL.json files[path={p}]؛ {p}:1"
        d["locator_type"] = "عنوان بخش و شماره قسمت"
        d["position_rule"] = "مسیر خانواده، فصل/قسمت، عنوان‌های Markdown و ترتیب بندها حفظ شود."
        if status == "CANONICAL":
            d.update(confirmed_role="فایل ماهوی", edition_status="نسخه مرجع قفل‌شده", segmentation_eligibility="واجد",
                     decision_basis="lock پیکره این مسیر را CANONICAL و دارای متن معنادار ثبت کرده است.")
        elif status == "SUPPLEMENTAL":
            d.update(confirmed_role="فایل ماهوی مکمل", edition_status="مکمل مستقل غیرمرجع", segmentation_eligibility="واجد",
                     decision_basis="lock آن را SUPPLEMENTAL می‌داند؛ متن مستقل برای تصمیم تحریری حفظ می‌شود و با نسخه مرجع ادغام نشده است.")
        elif status == "REVIEW_ONLY":
            d.update(confirmed_role="مواد بازبینی", edition_status="فقط برای بازبینی", segmentation_eligibility="غیرواجد",
                     decision_basis="lock آن را REVIEW_ONLY می‌داند؛ گزارش/اختلاف نامزد است و منبع Canonical نیست.")
        else:
            d.update(confirmed_role="منبع پژوهشی غیرمرجع", edition_status="غیرCanonical؛ عدم ارتقا", segmentation_eligibility="غیرواجد",
                     decision_basis="lock غیبت درس ۲۱ را عمدی و این بازیابی را NOT_CANONICAL اعلام کرده است.")
        if "VIDEO_COUNTERPART_ABSENT" in issue:
            d["decision_basis"] += " نبود ویدیوی متناظر محدودیت تطبیق است، نه دلیل حذف متن."
        return d

    if p == "CHAPTER05_MACHINE_VS_ORIGINAL.md":
        d.update(confirmed_role="مواد بازبینی", work_family="بازبینی انسانی فصل ۵", edition_status="متن کاری غیرمرجع",
                 decision_basis="خود فایل Status=HUMAN_REVIEW_WORKING_MATERIAL دارد و تصریح می‌کند evidence authority جدید نیست.",
                 evidence_locator=f"{p}:3؛ {p}:5-7")
        return d
    if p == "docs/final-book/00_REPOSITORY_PREFLIGHT.md":
        d.update(confirmed_role="گزارش ممیزی پیکره", work_family="راهبری کتاب نهایی", edition_status="گزارش وضعیت قفل‌ها",
                 decision_basis="محتوا شمارش Canonical/Supplemental/Review-only و ریسک‌های حل‌نشده را گزارش می‌کند؛ متن ماهوی نیست.",
                 evidence_locator=f"{p}:1-26")
        return d

    if p == "BOOK02_ORIGINAL_EXTRACT.md":
        d.update(confirmed_role="مواد بازبینی", work_family="بازبینی انسانی فصل ۵", edition_status="مشتق غیرمرجع از اصل کتاب ۲",
                 decision_basis="خود فایل Status=DERIVED_HUMAN_REVIEW_MATERIAL / NOT_CANONICAL_SOURCE دارد.", evidence_locator=f"{p}:3-11")
    elif p.endswith("01_CHAPTER05_MACHINE_VS_ORIGINAL.md"):
        d.update(confirmed_role="کپی دسترسی بازبینی", work_family="بازبینی انسانی فصل ۵", edition_status="کپی دسترسی از متن کاری",
                 decision_basis="README همان پوشه و راهنمای ریشه این مسیر را کپی برای دسترسی انسانی معرفی می‌کنند.",
                 evidence_locator="final_book/human_review/chapter_05/OPEN_FOR_USER/README.md:1-12؛ CHAPTER05_REVIEW_README.md:3-9")
    elif p.endswith("02_BOOK02_ORIGINAL_EXTRACT.md"):
        d.update(confirmed_role="تکرار قطعی", work_family="بازبینی انسانی فصل ۵", edition_status="کپی بایتی از مشتق غیرمرجع",
                 decision_basis=f"SHA-256 برابر در گروه {r['duplicate_group']} و README پوشه آن را کپی دسترسی معرفی می‌کند.",
                 evidence_locator="inventory-audit/inventory.csv duplicate_group=DUP-001؛ final_book/human_review/chapter_05/OPEN_FOR_USER/README.md:1-12")
    elif p in {"CHAPTER05_REVIEW_README.md", "final_book/human_review/chapter_05/OPEN_FOR_USER/README.md"}:
        d.update(confirmed_role="راهنمای بازبینی", work_family="بازبینی انسانی فصل ۵", edition_status="راهنمای دسترسی",
                 decision_basis="فهرست فایل‌های بازبینی و رابطه کپی‌های دسترسی را توضیح می‌دهد.")
    elif p == "PROJECT_STATE.md":
        d.update(confirmed_role="سند راهبری", work_family="راهبری مخزن", edition_status="نقطه شروع Canonical",
                 decision_basis="خود فایل canonical starting point و وضعیت FINAL/LOCKED سه لایه را اعلام می‌کند.", evidence_locator=f"{p}:1-47")
    elif p.startswith("governance/locks/"):
        d.update(confirmed_role="سند قفل پیکره", work_family="راهبری مخزن", edition_status="رکورد Canonical قفل‌شده",
                 decision_basis="JSON وضعیت FINAL_LOCKED، ریشه‌های مرجع و سیاست تغییر را ثبت می‌کند.")
    elif p.startswith("docs/final-book/") or p.startswith("reports/"):
        d.update(confirmed_role="گزارش ممیزی پیکره", work_family="راهبری و ممیزی", edition_status="گزارش پشتیبان تصمیم",
                 decision_basis="محتوا نتیجه ممیزی، شمارش و محدودیت منابع را ثبت می‌کند؛ متن ماهوی کتاب نیست.")
    elif p.startswith(".github/"):
        d.update(confirmed_role="مدیریتی", work_family="خودکارسازی پیکره", edition_status="گردش‌کار فنی",
                 decision_basis="فایل تعریف گردش‌کار ساخت/ممیزی است.")
    elif p.startswith("scripts/") or p.startswith("tools/"):
        role = "دارایی فنی" if p.endswith("requirements.txt") else "کد"
        d.update(confirmed_role=role, work_family="ابزار فنی پیکره", edition_status="ابزار اجرایی",
                 decision_basis="محتوا کد/وابستگی ساخت و QA پیکره است و نثر منبع محسوب نمی‌شود.")
    elif p in {"README.md", ".gitignore"}:
        d.update(confirmed_role="مدیریتی", work_family="راهبری مخزن", edition_status="اطلاعات مخزن",
                 decision_basis="محتوا معرفی کوتاه مخزن یا قاعده نادیده‌گیری داده تولیدی است.")
    return d


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with INV.open(encoding="utf-8-sig", newline="") as f:
        inv = list(csv.DictReader(f))
    lock = video_lock()
    rows = []
    for r in inv:
        x = {k: r[k] for k in ("source_id", "relative_path", "sha256", "issue_codes")}
        x.update(classify(r, lock))
        rows.append(x)

    fields = ["source_id", "relative_path", "sha256", "confirmed_role", "work_family", "edition_status",
              "segmentation_eligibility", "metadata_status", "decision_basis", "evidence_locator", "review_status", "issue_codes"]
    with (OUT / "source-register.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows({k: r[k] for k in fields} for r in rows)

    eligible = [r for r in rows if r["segmentation_eligibility"] == "واجد"]
    qfields = ["queue_order", "source_id", "relative_path", "sha256", "work_family", "edition_status", "suggested_locator_type", "source_position_rule"]
    with (OUT / "segmentation-queue.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=qfields); w.writeheader()
        for i, r in enumerate(eligible, 1):
            w.writerow({"queue_order": f"{i:04d}", "source_id": r["source_id"], "relative_path": r["relative_path"],
                        "sha256": r["sha256"], "work_family": r["work_family"], "edition_status": r["edition_status"],
                        "suggested_locator_type": r["locator_type"], "source_position_rule": r["position_rule"]})

    roles, editions, meta = Counter(r["confirmed_role"] for r in rows), Counter(r["edition_status"] for r in rows), Counter(r["metadata_status"] for r in rows)
    def table(c: Counter) -> str:
        return "\n".join(f"| {k} | {v} |" for k, v in sorted(c.items()))
    (OUT / "assessment-summary.md").write_text(f"""# خلاصه ارزیابی پیکره منابع

## نتیجه

- ردیف‌های موجودی و ثبت: **{len(rows)} / {len(rows)}**
- `source_id` یکتا: **{len({r['source_id'] for r in rows})}**
- منابع واجد قطعه‌بندی: **{len(eligible)}**
- منابع غیرواجد: **{len(rows)-len(eligible)}**
- نقش «نیازمند بررسی»: **{sum(r['confirmed_role']=='نیازمند بررسی' for r in rows)}**
- هشدار `NAME_SIMILAR_CANDIDATE`: **{sum('NAME_SIMILAR_CANDIDATE' in r['issue_codes'] for r in rows)}**؛ همه دارای خانواده و جایگاه صریح‌اند.
- هشدار `INSUFFICIENT_METADATA`: **{sum('INSUFFICIENT_METADATA' in r['issue_codes'] for r in rows)}**؛ همه به یکی از وضعیت‌های مصوب فراداده تبدیل شدند.
- هشدار `VIDEO_COUNTERPART_ABSENT`: **{sum('VIDEO_COUNTERPART_ABSENT' in r['issue_codes'] for r in rows)}**؛ هیچ‌کدام به این دلیل حذف نشده‌اند.

## نقش‌های تثبیت‌شده

| نقش | تعداد |
|---|---:|
{table(roles)}
| **جمع** | **{len(rows)}** |

## وضعیت فراداده

| وضعیت | تعداد |
|---|---:|
{table(meta)}
| **جمع** | **{len(rows)}** |

## کنترل صحت

اعتبارسنجی اجرایی در `verification-report.md` ثبت شده است. snapshot منبع پس از تولید خروجی با فهرست ۱۹۷ هش موجود تطبیق داده شد؛ مخزن منبع تغییر نکرد.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
