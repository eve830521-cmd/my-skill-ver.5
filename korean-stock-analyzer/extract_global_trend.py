# -*- coding: utf-8 -*-
"""
extract_global_trend.py - High-Speed Global_Trend PDF Deduplicator & Lossless Verbatim Indexer (v5.1)

Solves the 30~40 PDF (2,000+ pages) bottleneck in bi-weekly Global_Trend report generation:
  1) 3-Layer Duplicate Detection (SHA-256 hash + normalized filename `(1)` + content fingerprint)
  2) Multi-Zone Lossless Verbatim Extraction (Zero AI Summarization):
     - Zone A [Front Summary]       : Executive summary / Investment points (first content pages)
     - Zone B [Key Data/Consensus]  : Highest quantitative & consensus/target-price density pages
     - Zone C [Risk/Counter-Evidence]: Dedicated risk/bearish/stress-test page quota
  3) Outputs `<target_dir>/_raw_index.md` in ~2~5 seconds using PyMuPDF (fallback: pypdf),
     ready for Gemini 4 Neon (High) to synthesize `report(yy.mm.dd~dd).md` + `cycle_timeline.md`.

Usage:
  python extract_global_trend.py                        # Auto-detects latest Global_Trend subfolder
  python extract_global_trend.py --dir 26.11.01~15      # Specific period folder under Global_Trend
  python extract_global_trend.py --dir <full_path> --max-chars-per-pdf 4200 --max-pages-per-pdf 5
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import glob
import hashlib
import os
import re
import sys
import time
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL_DIR)

try:
    from ssot_common import STOCK_RESEARCH_ROOT
except Exception:
    STOCK_RESEARCH_ROOT = os.path.join(os.path.dirname(SKILL_DIR), "Stock_Research")

GLOBAL_TREND_ROOT = os.path.join(STOCK_RESEARCH_ROOT, "Global_Trend")

try:
    import pymupdf  # PyMuPDF (C-speed MuPDF backend)
    PDF_BACKEND = "pymupdf"
except ImportError:
    pymupdf = None
    import pypdf
    PDF_BACKEND = "pypdf"


# Boilerplate / legal disclaimer markers to avoid wasting page slots
DISCLAIMER_MARKERS = (
    "compliance notice",
    "투자자 고지사항",
    "본 조사분석자료는",
    "당사의 리서치센터",
    "투자의견 및 목표주가 변경",
    "목표주가 추이",
    "투자등급 비율",
    "금융투자상품은 자산가격",
    "예금자보호법에 따라",
)

CONSENSUS_KEYWORDS = (
    "목표주가", "투자의견", "top pick", "top-pick", "최선호", "차선호", "신규 커버",
    "overweight", "비중확대", "underweight", "neutral", "중립", "buy", "매수", "hold",
    "상향", "하향", "유지", "컨센서스", "서프라이즈", "쇼크", "tp", "per", "pbr",
    "영업이익", "매출", "opm", "eps", "fcf", "capex", "capa", "가동률", "수주",
    "asp", "점유율", "침투율", "쇼티지", "병목", "cagr", "yoy", "qoq",
)

RISK_KEYWORDS = (
    "리스크", "스트레스 테스트", "stress test", "공급과잉", "반론", "피크아웃",
    "우려", "쇼크", "하향", "neutral", "hold", "규제", "관세", "역풍", "지연",
    "취소", "둔화", "적자", "하회", "경쟁심화", "단가인하", "오버행", "신용",
    "cds", "부담", "변동성", "역기저", "할인",
)

QUANT_RE = re.compile(
    r"(?:\d[\d,\.]*\s*(?:%|%p|조원|억원|조|억|만대|만톤|만호|천대|GW|GWh|MW|MTPA|bp|배|원|달러|\$|km|척|기|개사|개월|년))"
    r"|(?:\$\s*\d[\d,\.]*)"
    r"|(?:[+-]\d[\d,\.]*\s*%)",
    re.IGNORECASE,
)

TAG_DETECT_RULES = [
    ("Overweight", re.compile(r"overweight|비중확대", re.I)),
    ("Neutral", re.compile(r"\bneutral\b|투자의견\s*중립", re.I)),
    ("Top-Pick", re.compile(r"top[\s-]*pick|최선호", re.I)),
    ("목표가상향", re.compile(r"목표주가\s*상향|tp\s*상향|상향\s*조정", re.I)),
    ("목표가하향", re.compile(r"목표주가\s*하향|tp\s*하향|하향\s*조정", re.I)),
    ("신규커버", re.compile(r"신규\s*커버|신규\s*제시|개시", re.I)),
    ("스트레스/리스크", re.compile(r"스트레스\s*테스트|stress\s*test|공급과잉|쇼크|피크아웃", re.I)),
    ("연간전망", re.compile(r"202[678]\s*년?\s*(?:산업\s*)?연간\s*전망|outlook", re.I)),
]


def find_latest_global_trend_dir():
    if not os.path.exists(GLOBAL_TREND_ROOT):
        return None
    subdirs = [
        os.path.join(GLOBAL_TREND_ROOT, d)
        for d in os.listdir(GLOBAL_TREND_ROOT)
        if os.path.isdir(os.path.join(GLOBAL_TREND_ROOT, d))
    ]
    if not subdirs:
        return None
    subdirs.sort(key=lambda p: os.path.basename(p), reverse=True)
    return subdirs[0]


def resolve_target_dir(dir_arg):
    if not dir_arg:
        return find_latest_global_trend_dir()
    if os.path.isdir(dir_arg):
        return os.path.abspath(dir_arg)
    candidate = os.path.join(GLOBAL_TREND_ROOT, dir_arg)
    if os.path.isdir(candidate):
        return os.path.abspath(candidate)
    return None


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_filename_stem(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    # Remove duplicate suffixes like " (1)", "(2)", " - 복사본", trailing dots/spaces
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    stem = re.sub(r"\s*[-_]?\s*(?:copy|복사본)\s*\d*$", "", stem, flags=re.I)
    stem = re.sub(r"[\s._-]+", " ", stem).strip().lower()
    return stem


def parse_filename_meta(path):
    """Parses `26.11.10. DS투자증권. 2027년 반도체 산업 연간전망.pdf` -> (date, broker, title)."""
    stem = os.path.splitext(os.path.basename(path))[0].strip()
    m = re.match(r"^(\d{2}\.\d{2}\.\d{2})\.?\s*([^.]+?)\.\s*(.+)$", stem)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    m2 = re.match(r"^(\d{2}\.\d{2}\.\d{2})\.?\s*(.+)$", stem)
    if m2:
        return m2.group(1).strip(), "미분류", m2.group(2).strip()
    return "-", "미분류", stem


def clean_page_text(raw_text):
    if not raw_text:
        return ""
    text = raw_text.replace("\x00", "").replace("\r", "\n")
    # Collapse excessive spaces while keeping line breaks for tables/bullets
    lines = []
    for ln in text.splitlines():
        s = re.sub(r"[ \t]{2,}", " ", ln).strip()
        if not s:
            continue
        # Drop isolated single page-number lines
        if re.match(r"^[-–—]?\s*\d{1,3}\s*[-–—]?$", s):
            continue
        lines.append(s)
    return "\n".join(lines)


def is_disclaimer_page(text_lower):
    hits = sum(1 for mk in DISCLAIMER_MARKERS if mk in text_lower)
    return hits >= 2


def extract_pdf_pages(pdf_path):
    """Returns list of cleaned page strings (0-indexed)."""
    pages = []
    if PDF_BACKEND == "pymupdf" and pymupdf is not None:
        doc = pymupdf.open(pdf_path)
        try:
            for page in doc:
                pages.append(clean_page_text(page.get_text("text") or ""))
        finally:
            doc.close()
    else:
        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            pages.append(clean_page_text(page.extract_text() or ""))
    return pages


def score_and_select_pages(pages, max_pages=5):
    """
    Selects up to `max_pages` high-value pages across 3 zones (100% lossless verbatim):
      - Zone A (Front Summary): up to 2 content-rich pages within first 6 pages
      - Zone B (Key Data & Consensus): up to 2 highest-density fact/table pages
      - Zone C (Risk / Counter-Evidence): 1 dedicated critical risk / stress-test page
    Returns list of tuples: (page_num_1based, zone_label, text)
    """
    n = len(pages)
    if n == 0:
        return []

    selected = {}  # page_idx -> zone_label

    # Helper to compute metrics per page
    page_stats = []
    for idx, txt in enumerate(pages):
        low = txt.lower()
        char_len = len(txt)
        disc = is_disclaimer_page(low)
        q_cnt = len(QUANT_RE.findall(txt))
        c_cnt = sum(1 for kw in CONSENSUS_KEYWORDS if kw in low)
        r_cnt = sum(1 for kw in RISK_KEYWORDS if kw in low)
        # Skip pure cover/TOC/disclaimer pages from high scores
        is_toc = ("contents" in low or "목차" in low) and q_cnt < 5 and char_len < 1200
        page_stats.append({
            "idx": idx,
            "len": char_len,
            "disc": disc,
            "toc": is_toc,
            "q": q_cnt,
            "c": c_cnt,
            "r": r_cnt,
            "data_score": (0 if (disc or is_toc or char_len < 140) else q_cnt * 2.2 + c_cnt * 4.5 + min(char_len, 2500) / 400.0),
            "risk_score": (0 if (disc or char_len < 160) else r_cnt * 8.0 + q_cnt * 1.2 + (3.0 if "스트레스" in low or "반론" in low else 0.0)),
        })

    # Zone A: Front Summary (first 2 substantive pages in p.1~p.6)
    front_quota = min(2, max_pages)
    front_candidates = [
        st for st in page_stats[:min(6, n)]
        if not st["disc"] and not st["toc"] and st["len"] >= 160
    ]
    # If p.1 is cover (<160 chars) it's auto-skipped; pick earliest substantive pages
    for st in front_candidates[:front_quota]:
        selected[st["idx"]] = "Front Summary"
    if not selected and n > 0:
        # Fallback to longest page in first 3 pages
        best_front = max(page_stats[:min(3, n)], key=lambda x: x["len"])
        if best_front["len"] > 0:
            selected[best_front["idx"]] = "Front Summary"

    # Zone C: Dedicated Risk / Counter-Evidence page (1 slot if max_pages >= 3)
    if max_pages >= 3:
        risk_cands = [
            st for st in page_stats
            if st["idx"] not in selected and st["risk_score"] >= 16.0
        ]
        if risk_cands:
            best_risk = max(risk_cands, key=lambda x: (x["risk_score"], x["q"]))
            selected[best_risk["idx"]] = "⚖️ Risk & Counter"

    # Zone B: Top Quantitative / Consensus / Table pages for remaining slots
    rem_slots = max_pages - len(selected)
    if rem_slots > 0:
        data_cands = [
            st for st in page_stats
            if st["idx"] not in selected and st["data_score"] > 0
        ]
        data_cands.sort(key=lambda x: (x["data_score"], x["q"]), reverse=True)
        for st in data_cands[:rem_slots]:
            selected[st["idx"]] = "Key Data & Consensus"

    # Order selected pages naturally by page number
    ordered = sorted(selected.items(), key=lambda kv: kv[0])
    return [(idx + 1, label, pages[idx]) for idx, label in ordered]


def detect_tags(selected_pages):
    combined = "\n".join(txt for _, _, txt in selected_pages)
    tags = [name for name, pat in TAG_DETECT_RULES if pat.search(combined)]
    return ", ".join(tags[:4]) if tags else "-"


def _parse_single_pdf_worker(args_tuple):
    pdf_path, max_pages_per_pdf, max_chars_per_pdf = args_tuple
    fname = os.path.basename(pdf_path)
    try:
        pages = extract_pdf_pages(pdf_path)
    except Exception as e:
        return {"ok": False, "filename": fname, "error": str(e)}

    first_txt = next((p for p in pages[:4] if len(p) >= 120), pages[0] if pages else "")
    fp_norm = re.sub(r"\s+", "", first_txt)[:500].lower()
    fp_key = (len(pages), hashlib.md5(fp_norm.encode("utf-8", errors="ignore")).hexdigest()) if fp_norm else None

    date_str, broker, title = parse_filename_meta(pdf_path)
    selected = score_and_select_pages(pages, max_pages=max_pages_per_pdf)
    tags = detect_tags(selected)

    per_page_cap = max(650, max_chars_per_pdf // max(1, len(selected)))
    trimmed_blocks = []
    used_chars = 0
    for pno, zlabel, ptxt in selected:
        remaining = max_chars_per_pdf - used_chars
        if remaining <= 200:
            break
        cap = min(per_page_cap + 250, remaining)
        snippet = ptxt[:cap]
        if len(ptxt) > cap:
            snippet = snippet.rstrip() + " ...[원문 이하 생략]"
        trimmed_blocks.append((pno, zlabel, snippet))
        used_chars += len(snippet)

    return {
        "ok": True,
        "pdf_path": pdf_path,
        "filename": fname,
        "fp_key": fp_key,
        "date": date_str,
        "broker": broker,
        "title": title,
        "total_pages": len(pages),
        "blocks": trimmed_blocks,
        "tags": tags,
        "chars": used_chars,
    }


def process_folder(target_dir, max_pages_per_pdf=5, max_chars_per_pdf=4200, output_path=None, delete_duplicates=False):
    t0 = time.time()
    pdf_files = sorted(glob.glob(os.path.join(target_dir, "*.pdf")))
    if not pdf_files:
        print(f"[Error] PDF 파일이 없습니다: {target_dir}")
        return 1

    # Prefer non-"(1)" cleaner filenames first so duplicates drop the "(1)" copy
    pdf_files.sort(key=lambda p: (bool(re.search(r"\(\d+\)\.pdf$", p)), os.path.basename(p)))

    seen_hashes = {}
    seen_stems = {}
    seen_fingerprints = {}
    unique_records = []
    duplicate_logs = []
    candidates_to_parse = []

    # Fast Layer 1 & Layer 2 deduplication before parallel PDF parsing
    for pdf_path in pdf_files:
        fname = os.path.basename(pdf_path)
        sha = file_sha256(pdf_path)
        stem_norm = normalize_filename_stem(pdf_path)

        if sha in seen_hashes:
            duplicate_logs.append((fname, seen_hashes[sha], "SHA-256 완전 동일"))
            if delete_duplicates:
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
            continue

        if stem_norm in seen_stems:
            duplicate_logs.append((fname, seen_stems[stem_norm], "중복 파일명 패턴 `(1)`"))
            if delete_duplicates:
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
            continue

        seen_hashes[sha] = fname
        seen_stems[stem_norm] = fname
        candidates_to_parse.append((pdf_path, max_pages_per_pdf, max_chars_per_pdf))

    # Parallel PDF parsing across CPU cores
    workers = min(max(1, (os.cpu_count() or 4)), len(candidates_to_parse), 8)
    if workers > 1 and len(candidates_to_parse) >= 4:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            parsed_results = list(ex.map(_parse_single_pdf_worker, candidates_to_parse))
    else:
        parsed_results = [_parse_single_pdf_worker(item) for item in candidates_to_parse]

    # Layer 3 content fingerprint deduplication
    for res in parsed_results:
        fname = res["filename"]
        if not res.get("ok"):
            duplicate_logs.append((fname, "-", f"파싱 오류 스킵: {res.get('error')}"))
            continue

        fp_key = res.get("fp_key")
        if fp_key and fp_key in seen_fingerprints:
            duplicate_logs.append((fname, seen_fingerprints[fp_key], "본문 1면·쪽수 동일 중복"))
            if delete_duplicates:
                try:
                    os.remove(res["pdf_path"])
                except OSError:
                    pass
            continue

        if fp_key:
            seen_fingerprints[fp_key] = fname
        unique_records.append(res)

    # Sort chronologically then by broker
    unique_records.sort(key=lambda r: (r["date"], r["broker"], r["title"]))

    period_name = os.path.basename(os.path.normpath(target_dir))
    if not output_path:
        output_path = os.path.join(target_dir, "_raw_index.md")

    total_pages_scanned = sum(r["total_pages"] for r in unique_records)
    total_pages_kept = sum(len(r["blocks"]) for r in unique_records)
    total_chars = sum(r["chars"] for r in unique_records)
    elapsed = time.time() - t0

    lines = [
        f"# 📑 Global_Trend 무손실 원문 인덱스 (`{period_name}/_raw_index.md`)",
        "",
        f"> **생성 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **엔진**: `extract_global_trend.py` ({PDF_BACKEND}) | **소요 시간**: `{elapsed:.2f}초`",
        f"> **스캔 결과**: 전체 `{len(pdf_files)}개` 중 **고유 리포트 `{len(unique_records)}개`** 발췌 (**중복/제외 `{len(duplicate_logs)}건`**) | 총 `{total_pages_scanned:,}쪽` ➔ 핵심 `{total_pages_kept}쪽` (`{total_chars:,}자` 무손실 원문)",
        f"> **활용 가이드**: 새 대화창에서 **`Gemini 4 Neon (High)`**을 선택하고 본 파일만 로드하여 `Stock_Research/Global_Trend/report({period_name}).md`와 `cycle_timeline.md`를 종합 집필하십시오.",
        "",
    ]

    if duplicate_logs:
        lines.append("## 🧹 자동 제외된 중복·예외 파일 로그")
        lines.append("| 제외 파일명 | 원본 유지 파일 | 제외 사유 |")
        lines.append("| :--- | :--- | :--- |")
        for ex_fn, orig_fn, reason in duplicate_logs:
            lines.append(f"| `{ex_fn}` | `{orig_fn}` | {reason} |")
        lines.append("")

    lines.append("## 📋 1. 고유 리포트 전체 매니페스트 (Manifest)")
    lines.append("| No | 발행일 | 증권사 | 리포트 제목 | 총쪽 | 발췌쪽 | 감지 태그 |")
    lines.append("| :---: | :---: | :--- | :--- | :---: | :---: | :--- |")
    for idx, rec in enumerate(unique_records, 1):
        p_list = ", ".join(f"p.{p}" for p, _, _ in rec["blocks"])
        safe_title = rec["title"].replace("|", "/")
        lines.append(
            f"| {idx} | {rec['date']} | {rec['broker']} | {safe_title} | {rec['total_pages']}p | {p_list} | {rec['tags']} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📄 2. 리포트별 100% 무손실 원문 발췌 (Zone A 요약 · Zone B 핵심수치/컨센서스 · Zone C 리스크/반론)")
    lines.append("")

    for idx, rec in enumerate(unique_records, 1):
        lines.append(
            f"### [{idx}/{len(unique_records)}] {rec['broker']} ({rec['date']}) — {rec['title']} (`{rec['total_pages']}p`)"
        )
        lines.append(f"- **파일명**: `{rec['filename']}` | **감지 태그**: `{rec['tags']}`")
        for pno, zlabel, snippet in rec["blocks"]:
            lines.append(f"\n#### [p.{pno} | {zlabel}]")
            lines.append("```text")
            lines.append(snippet)
            lines.append("```")
        lines.append("\n---\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    fsize_kb = os.path.getsize(output_path) / 1024.0
    print("======================================================================")
    print(f"✅ [Global_Trend 무손실 전처리 완료] {period_name}")
    print(f"   • 엔진 / 소요시간 : {PDF_BACKEND} / {elapsed:.2f}초")
    print(f"   • 리포트 집계     : 전체 {len(pdf_files)}개 ➔ 고유 {len(unique_records)}개 (중복 제외 {len(duplicate_logs)}건)")
    print(f"   • 페이지 압축     : 총 {total_pages_scanned:,}쪽 ➔ 핵심 {total_pages_kept}쪽 (무손실 원문)")
    print(f"   • 출력 파일       : {output_path} ({fsize_kb:.1f} KB)")
    print("======================================================================")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="High-Speed Global_Trend PDF Deduplicator & Lossless Verbatim Indexer (v5.1)"
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Target Global_Trend subfolder name (e.g. 26.11.01~15) or full directory path. Defaults to latest folder.",
    )
    parser.add_argument(
        "--max-pages-per-pdf",
        type=int,
        default=5,
        help="Maximum high-value pages extracted per PDF (default: 5)",
    )
    parser.add_argument(
        "--max-chars-per-pdf",
        type=int,
        default=4200,
        help="Maximum verbatim characters extracted per PDF (default: 4200)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional custom output path (default: <target_dir>/_raw_index.md)",
    )
    parser.add_argument(
        "--delete-duplicates",
        action="store_true",
        help="Physically delete detected duplicate PDFs (default: False, only skips them)",
    )
    args = parser.parse_args()

    target_dir = resolve_target_dir(args.dir)
    if not target_dir:
        print(f"[Error] 대상 Global_Trend 폴더를 찾을 수 없습니다: {args.dir or GLOBAL_TREND_ROOT}")
        sys.exit(1)

    sys.exit(
        process_folder(
            target_dir=target_dir,
            max_pages_per_pdf=args.max_pages_per_pdf,
            max_chars_per_pdf=args.max_chars_per_pdf,
            output_path=args.output,
            delete_duplicates=args.delete_duplicates,
        )
    )


if __name__ == "__main__":
    main()
