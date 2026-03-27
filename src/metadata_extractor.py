# metadata_extractor.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Dict, List, Optional
import os
import re
import logging
import difflib
import json
import unicodedata
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

try:
    from .post_processing import get_post_processor
except ImportError:
    from post_processing import get_post_processor

logger = logging.getLogger(__name__)


# Load Global Reference DB
_GLOBAL_REF_DB = {
    "doc_types": {},
    "issuers": {},
    "ocr_corrections": {}
}

def _load_global_ref_db():
    global _GLOBAL_REF_DB
    try:
        ref_path = Path(__file__).parent / "resources" / "reference_db.json"
        if ref_path.exists():
            with open(ref_path, "r", encoding="utf-8") as f:
                _GLOBAL_REF_DB = json.load(f)
            logger.info(f"Loaded Global Reference DB from {ref_path}")
        else:
            logger.warning(f"Global Reference DB not found at {ref_path}")
    except Exception as e:
        logger.error(f"Failed to load Global Reference DB: {e}")

_load_global_ref_db()

# For backward compatibility and internal use
ABBR_TO_TYPE = _GLOBAL_REF_DB.get("doc_types", {})



# ===== SPEC V3 HELPER FUNCTIONS (module-level, không ảnh hưởng interface hiện tại) =====

def _normalize_lines(text: str, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None) -> List[str]:
    """Chuẩn hoá OCR text thành danh sách dòng, dùng cho extract_metadata.

    - Gộp khoảng trắng thừa
    - Chuẩn hoá dấu gạch
    - Sửa một số lỗi OCR phổ biến
    - Tối ưu tốc độ: Chỉ dùng SymSpell cho 50 dòng đầu
    """
    if not text:
        return []
        
    # Chuẩn hoá linebreak trước
    raw_lines = [l.rstrip("\r") for l in text.splitlines()]

    # If bold_lines/uppercase_titles are not provided but text has markdown, we can reconstruct them
    if bold_lines is None: bold_lines = set()
    if uppercase_titles is None: uppercase_titles = set()

    normalized = []
    current_block = "UNKNOWN"
    for idx, l in enumerate(raw_lines):
        # Identify block markers
        if l.startswith("[BLOCK: "):
            current_block = l.strip("[]")
            normalized.append(l)
            continue
            
        # Optimization: Only apply intensive spell correction to the first 50 lines
        # where metadata is most likely to be found. 
        use_symspell = (idx < 50)
        
        nl = normalize_line(l, bold_lines=bold_lines, uppercase_titles=uppercase_titles, use_symspell=use_symspell)
        if nl:
            normalized.append(nl)
    return normalized

def normalize_line(s: str, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None, use_symspell: bool = True) -> str:
    """Helper to normalize a single line."""
    post_processor = get_post_processor()
    
    # Detect and strip Markdown
    is_md_bold = False
    is_md_heading = False
    
    # Check for Heading #
    if s.startswith("# "):
        is_md_heading = True
        s = s[2:].strip()
    
    # Check for Bold **
    if s.startswith("**") and s.endswith("**"):
        is_md_bold = True
        s = s[2:-2].strip()
    elif "**" in s:
        is_md_bold = True
        s = s.replace("**", "").strip()

    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    
    # Sửa lỗi chính tả cơ bản bằng SymSpell nếu enabled
    if use_symspell and post_processor.use_symspell:
        s = post_processor.correct_text(s)
        
    # Apply OCR corrections from DB
    corrections = _GLOBAL_REF_DB.get("ocr_corrections", {})
    for err, corr in corrections.items():
        if err in s:
            s = s.replace(err, corr)

    # Các fix OCR nhẹ, không quá mạnh tay
    s = re.sub(r"\bNgay\b", "Ngày", s, flags=re.IGNORECASE)
    s = re.sub(r"\bthang\b", "tháng", s, flags=re.IGNORECASE)
    
    # Filter out common noise lines
    low = s.lower()
    if re.search(r"\b(admin|scanned by|watermark|logo)\b", low):
        return ""
    if re.search(r"\b(page|trang)\b\s*\d+", low):
        return ""
        
    clean_s = s.strip()
    if clean_s:
        if is_md_bold and bold_lines is not None:
            bold_lines.add(' '.join(clean_s.split()))
        if is_md_heading and uppercase_titles is not None:
            uppercase_titles.add(' '.join(clean_s.split()))
    
    return clean_s


def _is_quoc_hieu_or_tieu_ngu(line: str) -> bool:
    if not line:
        return False
    up = line.upper()
    
    # Priority: National Motto keywords with flexible spacing (Accented & Unaccented OCR)
    # C\u1ed8NG H\u00d2A X\u00c3 H\u1ed8I CH\u1ee6 NGH\u1ecaA VI\u1ec6T NAM
    pat_ch = r"C\s*[\u1ed8O]\s*N\s*G\s+H\s*[\u1ed2O]\s*A\b"
    pat_xh = r"X\s*[\u00c3A]\s+H\s*[\u1ed8O]\s*I\b"
    pat_vn = r"V\s*I\s*[\u1ec6E]\s*T\s+N\s*A\s*M\b"
    
    # \u0110\u1ed8C L\u1eacP - T\u1ef0 DO - H\u1ea0NH PH\u00daC
    pat_dl = r"[\u0110D]\s*[\u1ed8O]\s*C\s+L\s*[\u1eacA]\s*P\b"
    pat_td = r"T\s*[\u1ef0U]\s+D\s*O\b"
    pat_hp = r"H\s*[\u1ea0A]\s*N\s*H\s+P\s*H\s*[\u00daU]\s*C\b"

    # Match components
    ch = re.search(pat_ch, up)
    xh = re.search(pat_xh, up)
    vn = re.search(pat_vn, up)
    dl = re.search(pat_dl, up)
    td = re.search(pat_td, up)
    hp = re.search(pat_hp, up)

    if (ch and xh) or (ch and vn) or (xh and vn):
        return True
    if (dl and td) or (dl and hp) or (td and hp):
        return True
        
    # Standard tokens for exact/fallback
    tokens = [
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "ĐỘC LẬP - TỰ DO - HẠNH PHÚC",
        "ĐẢNG CỘNG SẢN VIỆT NAM",
        "DANG CONG SAN VIET NAM",
        "VIỆT NAM DÂN CHỦ CỘNG HÒA",
    ]
    
    return any(tok in up for tok in tokens)


def _detect_uppercase_block(lines: List[str], max_lines: int = 4) -> List[str]:
    """Tìm block các dòng upper-case đầu văn bản (thường là cơ quan ban hành, loại văn bản)."""
    block = []
    for line in lines[:max_lines]:
        s = line.strip()
        if not s:
            break
        letters = [c for c in s if c.isalpha()]
        if not letters:
            break
        if all(c.upper() == c for c in letters):
            block.append(s)
        else:
            break
    return block


def _is_valid_issuer_line(line: str) -> bool:
    """SPEC V3.6 Issuer validation.
    
    A valid issuer line MUST satisfy ALL of:
    1. Fully uppercase (A-Z, Á-Ỵ, including Vietnamese accents)
    2. Does NOT begin with a number
    3. Does NOT contain date components: "ngày", "tháng", "năm", or digit+/ patterns
    4. Does NOT match known document types: "NGHỊ QUYẾT", "QUYẾT ĐỊNH", "KẾT LUẬN", etc.
    5. Does NOT match quốc hiệu/tiêu ngữ
    """
    if not line:
        return False
    
    s_strip = line.strip()
    if not s_strip:
        return False
    
    # Check if it's quốc hiệu or tiêu ngữ
    if _is_quoc_hieu_or_tieu_ngu(s_strip):
        return False
    
    # Extract only alphabetic characters for case checking
    letters = [c for c in s_strip if c.isalpha()]
    if not letters:
        return False
    
    # 1. Must be fully uppercase (A-Z, Á-Ỵ with Vietnamese diacritics)
    if not all(c.upper() == c for c in letters):
        return False
    
    # 2. Must NOT begin with a digit
    if s_strip[0].isdigit():
        return False
    
    s_upper = s_strip.upper()
    
    # 3. Must NOT contain date components or digit+/ patterns
    date_keywords = [
        "NGÀY", "NGAY",
        "THÁNG", "THANG",
        "NĂM", "NAM"
    ]
    for kw in date_keywords:
        if kw in s_upper:
            return False
    
    # Check for digit+/ pattern (like dates: 01/12/2025)
    if re.search(r"\d+/\d", s_strip):
        return False
    
    # 4. Must NOT match known document types
    doc_types = [
        "NGHỊ QUYẾT", "NGHI QUYET",
        "QUYẾT ĐỊNH", "QUYET DINH", "QĐ", "QD",
        "KẾT LUẬN", "KET LUAN",
        "THÔNG BÁO", "THONG BAO",
        "TỜ TRÌNH", "TO TRINH",
        "CÔNG VĂN", "CONG VAN",
        "BÁO CÁO", "BAO CAO",
        "KẾ HOẠCH", "KE HOACH",
        "CHỈ THỊ", "CHI THI",
        "HƯỚNG DẪN", "HUONG DAN"
    ]
    for dt in doc_types:
        if dt in s_upper:
            return False
    
    return True


def _extract_agency(lines: List[str], doc_type: str = "", bold_lines: Optional[set] = None, doc_type_index: int = -1, uppercase_titles: Optional[set] = None) -> str:
    """SPEC V3.7 Issuer extraction with Markdown-Anchored Zoning.

    Priority:
    1. Contiguous blocks identified as BOLD or HEADINGS (Markdown anchors)
    2. Contiguous blocks of UPPERCASE text
    3. Blocks containing strong institution keywords
    Zone Limit: First 15 lines.
    """
    if not lines:
        return ""

    # Keywords for confidence scoring (not discovery)
    strong_keywords = [
        "ĐẢNG ỦY", "DANG UY", "ĐẢNG BỘ", "DANG BO", "TỈNH ỦY", "TINH UY", "HUYỆN ỦY", "HUYEN UY", "THÀNH ỦY",
        "SỞ", "SO", "BAN", "PHÒNG", "PHONG", "TRƯỜNG", "TRUONG", "VĂN PHÒNG", "VAN PHONG",
        "UBND", "ỦY BAN NHÂN DÂN", "UY BAN NHAN DAN",
        "HĐND", "HỘI ĐỒNG NHÂN DÂN", "HOI DONG NHAN DAN", "HỘI ĐỒNG", "HOI DONG",
        "BỘ", "BO", "TỔNG CỤC", "TONG CUC", "CỤC", "CUC",
        "VIỆN", "VIEN", "TRUNG TÂM", "TRUNG TAM",
        "CHI CỤC", "CHI CUC", "HỘI", "HOI", "ĐOÀN", "DOAN",
        "KHỐI", "KHOI", "CHÍNH PHỦ", "CHINH PHU"
    ]
    
    limit = min(len(lines), 20) # slightly larger limit to account for markers
    valid_lines = []
    current_block = "UNKNOWN"

    for i in range(limit):
        s = lines[i].strip()
        if not s: continue
        
        # Track block
        if s.startswith("[BLOCK: "):
            current_block = s.strip("[]")
            continue

        # Stop at Doc Number markers
        if re.search(r"^[Ss](?:ố|Ố)\s*:", s) or re.match(r"^(S\d|Se|SE)\b", s):
            # Exception: if we are in HEADER_LEFT, we might still have agency parts
            if current_block != "BLOCK: HEADER_LEFT":
                break

        # Stop if we reached Doc Type
        if doc_type_index >= 0 and i >= doc_type_index:
            break
            
        s_up = s.upper()
        
        # USER REQUEST: Agency is often on the left, Motto on the right.
        # If we have block markers, we can trust them more!
        if current_block == "BLOCK: HEADER_RIGHT":
            continue # Skip common motto block
            
        # If we DON'T have block markers (native text), fallback to motto splitting
        if current_block == "UNKNOWN":
            motto_keywords = [
                "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "ĐỘC LẬP - TỰ DO - HẠNH PHÚC",
                "ĐẢNG CỘNG SẢN VIỆT NAM", "DANG CONG SAN VIET NAM",
                "ĐẢNG BỘ", "DANG BO", # Sometimes part of motto block
            ]
            found_motto = False
            for mkw in motto_keywords:
                if mkw in s_up:
                    if s_up.startswith(mkw):
                        found_motto = True
                        break
                    parts = re.split(rf"\b{re.escape(mkw)}\b", s, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        s = parts[0].strip()
                        if not s or len(re.sub(r"[^\w]", "", s)) < 2:
                            found_motto = True
                            break
                        s_up = s.upper()
            if found_motto and not s.strip(): continue

        # Normalization for matching style sets
        norm = ' '.join(s.split())
        is_bold = bool(bold_lines and norm in bold_lines)
        is_heading = bool(uppercase_titles and norm in uppercase_titles)
        
        # Heuristic for "Uppercase" line check
        letters = [c for c in s if c.isalpha()]
        is_upper = all(c.isupper() for c in letters) if letters else False
        
        # Exclude Quốc hiệu / Tiêu ngữ
        if _is_quoc_hieu_or_tieu_ngu(s):
            continue
            
        # Optional: Split if line contains both Agency and Motto (common in tight headers)
        # Search for separators like multiple spaces, long dashes, or specific motto starts
        parts = re.split(r"\s{2,}|[—–-]{2,}", s)
        if len(parts) > 1:
            # If any part looks like motto, just use the first part that looks like agency
            for p_idx, part in enumerate(parts):
                if _is_quoc_hieu_or_tieu_ngu(part):
                    if p_idx > 0:
                        s = " ".join(parts[:p_idx]).strip()
                    break
        
        # We only consider lines that are Bold, Heading, or mostly Uppercase
        if is_bold or is_heading or is_upper or current_block == "BLOCK: HEADER_LEFT":
            valid_lines.append({
                'idx': i,
                'text': s,
                'is_bold': is_bold,
                'is_heading': is_heading,
                'is_upper': is_upper,
                'block': current_block
            })

    if not valid_lines:
        # FALLBACK: Quét 5 dòng đầu tìm dòng ALL CAPS chứa keyword cơ quan (Hữu ích khi OCR không có Bold)
        for i, line in enumerate(lines[:5]):
            s = line.strip()
            if not s:
                continue
            s_up = s.upper()
            # Bỏ qua dòng Quốc hiệu / Tiêu ngữ
            if any(k in s_up for k in ["C\u1ed8NG H\u00d2A", "CONG HOA", "\u0110\u1ed8C L\u1eacP", "DOC LAP"]):
                continue

            # N\u1ebfu d\u00f2ng l\u00e0 ALL CAPS v\u00e0 ch\u1ee9a keyword c\u01a1 quan th\u00ec ch\u1ea5p nh\u1eadn ngay
            if any(re.search(rf"\b{k}\b", s_up) for k in strong_keywords):
                letters = [c for c in s if c.isalpha()]
                if letters and all(c.isupper() for c in letters) and len(s) > 3:
                    return s
        return ""

    # Group into contiguous blocks
    blocks = []
    current_block = [valid_lines[0]]
    for i in range(1, len(valid_lines)):
        if valid_lines[i]['idx'] <= current_block[-1]['idx'] + 2:
            current_block.append(valid_lines[i])
        else:
            blocks.append(current_block)
            current_block = [valid_lines[i]]
    blocks.append(current_block)

    best_agency = ""
    max_score = -1

    for block in blocks:
        # Explicit types to satisfy linter with generator hygiene
        # Casting helps when the linter is confused by dict inference
        block_texts: List[str] = [str(item['text']) for item in block]
        block_indices: List[int] = [int(item['idx']) for item in block]
        block_bolds: List[bool] = [bool(item['is_bold']) for item in block]
        block_headings: List[bool] = [bool(item['is_heading']) for item in block]
        block_uppers: List[bool] = [bool(item['is_upper']) for item in block]
        
        full_text = " ".join(block_texts)
        full_text_up = full_text.upper()
        
        # Scoring logic shifted to Zoning & Markdown Anchors
        score = 0
        
        # 1. Zone/Position Bonus (Earlier is better)
        score += (20 - block_indices[0]) * 2
        
        # 2. Markdown Anchors (Major priority)
        if any(block_bolds): score += 30
        if any(block_headings): score += 20
        
        # 3. Block Priority (Geometric segmentation)
        if any(item['block'] == "BLOCK: HEADER_LEFT" for item in block):
            score += 50
            
        # 4. Keyword Validation (Confidence boost)
        if any(re.search(rf"\b{k}\b", full_text_up) for k in strong_keywords):
            score += 25
            
        # 5. Consistency: All Caps block
        if all(block_uppers):
            score += 15
        
        if score > max_score:
            max_score = score
            best_agency = full_text

    # OCR cleanup
    if best_agency:
        best_agency = re.sub(r"\bPH\s+Ủ\b", "PHỦ", best_agency, flags=re.IGNORECASE)
        best_agency = re.sub(r"\bN\s+ƯỚC\b", "NƯỚC", best_agency, flags=re.IGNORECASE)
        best_agency = re.sub(r"\bC\s+H\s+Ủ\b", "CHỦ", best_agency, flags=re.IGNORECASE)
        
    return best_agency.strip()


def _extract_number_and_symbol(lines: List[str]) -> tuple[str, str]:
    r"""Trích số văn bản và ký hiệu từ dòng bắt đầu với 'Số' / 'SỐ'.
    
    Chi tiết:
    - Chỉ trích từ dòng BẮT ĐẦU với "Số" hoặc "SỐ" (case-insensitive)
    - Bỏ qua các số trong phần thân văn bản
    - Pattern: Số\s*:?\s*<num>\s*[-–]?\s*<symbol>
    - Trả về số trước dấu gạch, ký hiệu sau dấu gạch
    
    Ví dụ:
      "Số: 01" → ("01", "")
      "Số: 01/NQ-ĐUK" → ("01", "NQ-ĐUK")
      "Số 01 - NQ/ĐUK" → ("01", "NQ/ĐUK")
      "Số: 123 - QĐ-UBND" → ("123", "QĐ-UBND")
    """
    # Tìm dòng bắt đầu với "Số" hoặc "SỐ" (case-insensitive: Sô, sô, SÔ, sÔ)
    so_line = None
    # OPTIMIZATION: Thường số hiệu nằm ở phần đầu, dưới cơ quan ban hành.
    # Chỉ kiểm tra 15 dòng đầu để tránh lấy nhầm số ở thân văn bản.
    for line in lines[:15]: 
        stripped = line.strip()
        # Tránh các dòng chứa từ khóa gây nhiễu thường gặp trong thân văn bản
        if re.search(r"(số\s+tiền|số\s+lượng|số\s+trang|số\s+tờ|số\s+hồ\s+sơ|số\s+thứ\s+tự|số\s+vụ|số\s+người|số\s+liên)", stripped, flags=re.IGNORECASE):
            continue
            
        # Match "Số" or "SỐ" strictly at the start (ignoring some leading noise)
        # Một dòng số hiệu văn bản chuẩn thường bắt đầu bằng "Số:" hoặc "Số" và rất ngắn,
        # hoặc chứa các ký hiệu như "/" hoặc "-".
        if re.match(r"^[^\w]*[Ss](?:ố|Ố)\b", stripped):
            # Kiểm tra cấu trúc:
            # 1. Có chứa dấu "/" (phổ biến nhất: Số: 01/NQ-...)
            # 2. Có chứa dấu "-" sau phần số
            # 3. Hoặc dòng rất ngắn (dưới 30 ký tự) - trường hợp chỉ có Số: 01
            has_digit = bool(re.search(r"\d", stripped))
            is_fragment = len(stripped) < 35
            has_separators = "/" in stripped or "-" in stripped
            
            if has_digit and (is_fragment or has_separators):
                # Đảm bảo không phải là một câu dài (thân văn bản)
                # Nếu có quá nhiều chữ cái thường liên tiếp, có thể là câu.
                # Dòng số hiệu thường chủ yếu là HOA, số và ký tự đặc biệt.
                lower_count = sum(1 for c in stripped if c.islower())
                if lower_count < 15 or is_fragment:
                    so_line = stripped
                    break
    
    if not so_line:
        return "", ""
    
    # Pattern: "Số" + optional colon/space + number + optional (hyphen/slash + symbol)
    # Stop capturing at "Hà Nội", "thành phố", date keywords, or end of line.
    # Group 1: Number
    # Group 2: Symbol part (raw)
    
    # Improved regex: Stop at whitespace followed by common location/date starters
    # e.g. "Số: 01/CP-KTTH Hà Nội, ngày..." -> stop before " Hà Nội"
    # Also stop at National Motto if it appears on same line (e.g. "Số: ... CỘNG HÒA...")
    # Add more locations like TP, Tỉnh, Huyện, and Party Preamble
    stop_patterns = r"(?=\s+(Hà\s+Nội|Tp\.|T\.p|Thành\s+phố|Tỉnh|Huyện|ngày|tháng|năm|[A-Z][a-zà-ỹ]+,|C\s*Ộ\s*N\s*G\s+H\s*Ò\s*A|Đ\s*Ả\s*N\s*G\s+C\s*Ộ\s*N\s*G\s+S\s*Ả\s*N|Đ\s*Ộ\s*C\s+L\s*Ậ\s*P))"
    # Extended stopper to be more robust against OCR noise
    pattern = r"[Ss](?:ố|Ố|Ô|6|0|8)\s*:?\s*(\d{1,10})([^\n]*?)" + stop_patterns
    # Try the stopper regex first
    m = re.search(pattern, so_line, flags=re.IGNORECASE)
    
    # If no stopper match, try matching until end of line but exclude common noise
    if not m:
         pattern_simple = r"[Ss](?:ố|Ố)\s*:?\s*(\d{1,5})(.*)"
         m = re.search(pattern_simple, so_line)
    
    if m:
        num = m.group(1).strip()
        raw_symbol = m.group(2).strip() if len(m.groups()) > 1 else ""
        
        # User Request: Refine Symbol Extraction
        # 1. Clean National Motto if captured (Greedy match fix)
        # e.g. "NQ/ĐUĐẤNG CỘNG SÁN VIỆT NAM" -> "NQ/ĐU"
        # Expanded to catch Party Motto variants better
        motto_pat = r"(Đ\s*Ả\s*N\s*G\s+C\s*Ộ\s*N\s*G|Đ\s*Ấ\s*N\s*G\s+C\s*Ộ\s*N\s*G|C\s*Ộ\s*N\s*G\s+H\s*Ò\s*A|C\s*Ô\s*N\s*G\s+H\s*Ò\s*A|D\s*A\s*N\s+C\s*H\s*I\s*N\s*H|D\s*Â\s*N\s+C\s*H\s*Í\s*N\s*H)"
        stop_motto = re.search(motto_pat, raw_symbol.upper())
        if stop_motto:
            raw_symbol = raw_symbol[:stop_motto.start()].strip()

        # 2. Clean leading punctuation/noise from symbol (-, /, space, *, (, {)
        symbol = re.sub(r"^[-–/.,\s\*\(\{\[]+", "", raw_symbol)
        
        # 3. Clean trailing noise (often OCR artifacts like * or chars after opening bracket if unmatched)
        # 3a. Strict cut-off for common adjacent identifiers that lack spacing (Bug Fix)
        # e.g. "QĐ/TUĐẢNG..." -> "QĐ/TU"
        # Regex to find start of "ĐẢNG", "CỘNG", "VIỆT", "HÀ NỘI", "TỈNH", "THÀNH" attached to symbol
        # We allow these if preceded by a separator like - or /
        adj_noise = re.search(r"(?<![-/])(ĐẢNG|DANG|CỘNG|CONG|VIỆT|VIET|HÀ\s*NỘI|HA\s*NOI|TỈNH|TINH|THÀNH|THANH|UBND|HĐND|BAN)", symbol.upper())
        if adj_noise:
            # If match is at the very beginning, maybe the symbol IS invalid? 
            # But assume it's attached at end.
            if adj_noise.start() > 1:
                symbol = symbol[:adj_noise.start()].strip()
            # If it starts with it, it's likely not a symbol but a motto line mistakenly captured?
            # e.g. "CỘNG HÒA..." captured as symbol.
            # Logic below (len check) might handle it, but let's be safe.
        
        # 3b. Strip trailing special chars
        if '(' in symbol:
             symbol = symbol.split('(')[0].strip()
        if '*' in symbol:
             symbol = symbol.split('*')[0].strip()
        
        # 3c. Cut off if multiple spaces followed by uppercase (likely location)
        # e.g. "NQ/TW    Hà Nội"
        symbol = re.split(r"\s{2,}[A-Z]", symbol)[0].strip()

        # Strip trailing dots, commas, dashes
        symbol = symbol.strip(".,;-–*")

        # USER REQUEST: Ensure symbol is continuous and doesn't contain noise
        # 1. Truncate at double spaces (likely start of location/date on same line)
        if "  " in symbol:
            symbol = symbol.split("  ")[0].strip()
        
        # 2. Heuristic: Symbol should mainly consist of Uppercase, digits, and separators (/, -, .)
        # If we see a sequence of lowercase words (except common lowercase abbreviations like 'v/v' if it was part of it)
        # we might have over-extracted into the summary or location.
        # But 'v/v' is usually at start or end. 
        # Let's check for lowercase words longer than 2 chars that aren't common.
        words = symbol.split()
        if len(words) > 1:
            for i, w in enumerate(words):
                if i == 0: continue # allow first part to be doc type like 'NQ'
                # If a word is mostly lowercase and not a known abbreviation, truncate before it
                clean_w = re.sub(r"[^a-zA-Zà-ỹÀ-Ỹ]", "", w)
                # Truncate if lowercase and length > 2 OR if it's specifically 'về' 
                if clean_w.islower() and (len(clean_w) > 2 or clean_w == "về"):
                    # Likely start of "về việc..." or a name
                    symbol = " ".join(words[:i]).strip()
                    break

        return num, symbol
    
    # Fallback: chỉ lấy số nếu không có ký hiệu
    num_match = re.search(r"[Ss](?:ố|Ố)\s*:?\s*(\d{1,5})", so_line)
    if num_match:
        return num_match.group(1).strip(), ""
    
    return "", ""


def _extract_date_v3(lines: List[str]) -> str:
    # Scan line-by-line so we can ignore dates that appear in "Căn cứ" sections
    patterns = [
        # Standard & Fuzzy Tones: ngày/ngay/ngảy... thảng/tháng... năm/nam...
        re.compile(r"(ng\S*y)\s*(\d{1,2})\s*(th\S*ng)\s*(\d{1,2})\s*(n\S*m)\s*(\d{4})", flags=re.IGNORECASE),
        re.compile(r"(ng\S*y)\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", flags=re.IGNORECASE),
        re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", flags=re.IGNORECASE),
        # Dot separator: 12.03.2026
        re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", flags=re.IGNORECASE),
        # Hyphen separator: 12-03-2026
        re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})", flags=re.IGNORECASE),
        # Wide/Spaced OCR patterns: "n ăm", "th áng"
        re.compile(r"(n\s*g\s*[\wà-ỹ]+\s*y)\s*(\d{1,2})\s*(t\s*h\s*[\wà-ỹ]+\s*n\s*g)\s*(\d{1,2})\s*(n\s*[\wà-ỹ]+\s*m)\s*(\d{4})", flags=re.IGNORECASE),
    ]

    for idx, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        # Skip if this line (or previous) is part of a 'Căn cứ' section
        prev = lines[idx-1] if idx-1 >= 0 else ""
        if re.search(r"\b(CĂN\s+?CỨ|CAN\s+CU)\b", s.upper()) or re.search(r"\b(CĂN\s+?CỨ|CAN\s+CU)\b", prev.upper() if prev else ""):
            continue
        
        # Additional check: skip strictly "CÔNG BÁO" header lines which also contain dates
        if "CÔNG BÁO" in s.upper() or "CONG BAO" in s.upper():
            continue

        for pat in patterns:
            m = pat.search(s)
            if m:
                if len(m.groups()) == 6:
                    d = int(m.group(2))
                    mth = int(m.group(4))
                    yr = int(m.group(6))
                elif len(m.groups()) == 4:
                    # pattern (ngày DD/MM/YYYY)
                    d = int(m.group(2))
                    mth = int(m.group(3))
                    yr = int(m.group(4))
                elif len(m.groups()) == 3:
                    d = int(m.group(1))
                    mth = int(m.group(2))
                    yr = int(m.group(3))
                else:
                    continue
                
                # Basic validation
                if 1 <= d <= 31 and 1 <= mth <= 12 and 1900 <= yr <= 2100:
                    return f"{d:02d}/{mth:02d}/{yr}"
    
    # Fallback: Scan last 15 lines if not found in top (sometimes date is at bottom)
    if len(lines) > 30:
        tail = lines[-15:]
        for line in tail:
            s = line.strip()
            if not s: continue
            for pat in patterns:
                m = pat.search(s)
                if m:
                    # Capture logic (same as above)
                    try:
                        if len(m.groups()) == 6:
                            d, mth, yr = int(m.group(2)), int(m.group(4)), int(m.group(6))
                        elif len(m.groups()) == 4:
                            d, mth, yr = int(m.group(2)), int(m.group(3)), int(m.group(4))
                        elif len(m.groups()) == 3:
                            d, mth, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        else: continue
                        if 1 <= d <= 31 and 1 <= mth <= 12 and 1900 <= yr <= 2100:
                            return f"{d:02d}/{mth:02d}/{yr}"
                    except: continue
                    
    return ""


def _extract_doc_type(lines: List[str], uppercase_titles: Optional[set] = None, bold_lines: Optional[set] = None) -> tuple[str, int]:
    """Loại văn bản: dòng in HOA, ở khoảng đầu văn bản. Trả về (type, index)."""
    keywords = [
        "NGHỊ QUYẾT", "NGHI QUYET",
        "NGHỊ ĐỊNH", "NGHI DINH",
        "QUYẾT ĐỊNH", "QUYET DINH",
        "CHỈ THỊ", "CHI THI",
        "QUY CHẾ", "QUY CHE",
        "QUY ĐỊNH", "QUY DINH",
        "NỘI QUY", "NOI QUY",
        "QUY TRÌNH", "QUY TRINH",
        "HƯỚNG DẪN", "HUONG DAN",
        "KẾ HOẠCH", "KE HOACH",
        "ĐỀ ÁN", "DE AN",
        "ĐỀ NGHỊ", "DE NGHI",
        "ĐỀ XUẤT", "DE XUAT",
        "THÔNG BÁO", "THONG BAO",
        "BÁO CÁO", "BAO CAO",
        "TỜ TRÌNH", "TO TRINH",
        "CÔNG VĂN", "CONG VAN",
        "GIẤY MỜI", "GIAY MOI",
        "GIẤY GIỚI THIỆU", "GIAY GIOI THIEU",
        "GIẤY ĐI ĐƯỜNG", "GIAY DI DUONG",
        "BIÊN BẢN", "BIEN BAN",
        "PHIẾU BÁO", "PHIEU BAO",
        "PHIẾU GỬI", "PHIEU GUI",
        "PHIẾU CHUYỂN", "PHIEU CHUYEN",
        "PHIẾU TRÌNH", "PHIEU TRINH",
        "CHƯƠNG TRÌNH", "CHUONG TRINH",
        "THÔNG TƯ", "THONG TU",
        "KẾT LUẬN", "KET LUAN",
    ]
    
    # User Hint: 2-letter abbreviations mapping
    ABBR_MAP = {
        "NQ": "NGHỊ QUYẾT",
        "NĐ": "NGHỊ ĐỊNH",
        "QĐ": "QUYẾT ĐỊNH",
        "CT": "CHỈ THỊ",
        "BC": "BÁO CÁO",
        "KH": "KẾ HOẠCH",
        "TB": "THÔNG BÁO",
        "TT": "THÔNG TƯ",
        "CV": "CÔNG VĂN",
        "TTr": "TỜ TRÌNH",
        "PA": "PHƯƠNG ÁN",
        "ĐA": "ĐỀ ÁN",
        "HD": "HƯỚNG DẪN",
        "KL": "KẾT LUẬN",
        "BB": "BIÊN BẢN",
    }
    # We scan up to 30 lines for document type
    
    def is_excluded_line(line_upper: str) -> bool:
        # Preamble start phrases
        if re.match(r"^(THỰC\s+HIỆN|THUC\s+HIEN|CĂN\s+CỨ|CAN\s+CU|TRÍCH\s+YẾU|TRICH\s+YEU)", line_upper):
            return True
        # Exclude lines STARTING with "Của...", "Về việc..."
        if re.match(r"^(C\u1ee6A|CUA|V\u1ec0\s+VI\u1ec6C|VE\s+VIEC|V/V)", line_upper):
            return True
        # Exclude "Số:..." lines (Doc Number)
        if re.match(r"^(SỐ|SO)\s*[:\.]", line_upper):
            return True
        # Exclude OCR noise for "Số" (S6, Se, SE, S0)
        # e.g. "S6: 02...", "Se: 15..."
        if re.match(r"^(S\d|SE|SE\s*[:\.])", line_upper):
            return True
        # Exclude "V/v" lines (handle quotes like " V/v or “V/v)
        # remove non-alphanumeric prefix
        clean_up = re.sub(r"^[^A-Z0-9]+", "", line_upper)
        if clean_up.startswith("V/V"):
            return True
        # Exclude Signer Title keywords
        if re.match(r"^(B\u00cd\s+TH\u01b0|BI\s+THU|CH\u1ee6\s+T\u1ecaCH|CHU\s+TICH|TM\.|TL\.|KT\.)", line_upper):
            return True
        if re.match(r"^(B\u1ed8\s+TR\u01af\u1eebNG|BO\s+TRUONG|T\u1ed4NG\s+|TONG\s+|C\u1ee4C\s+TR\u01af\u1eebNG|CUC\s+TRUONG|TH\u1ee6\s+TR\u01af\u1eebNG|THU\s+TRUONG|GI\u00c1M\s+\u0110\u1ed0C|GIAM\s+DOC)", line_upper):
            return True
        if "V\u0102N B\u1ea2N PH\u00c1P LU\u1eacT" in line_upper or "VAN BAN PHAP LUAT" in line_upper:
            return True
        if "V\u0102N B\u1ea2N KH\u00c1C" in line_upper or "VAN BAN KHAC" in line_upper:
            return True
        if "\u0110\u1ea2NG" in line_upper or "DANG" in line_upper or "DOANH NGHI\u1ec6P" in line_upper or "DOANH NGHIEP" in line_upper:
            return True
        if re.search(r"CH\u00cdNH\s+PH\s*[\u1ee6U]", line_upper):
            return True
        return False
    # SPEC V4.1: Chỉ chấp nhận dòng bold nếu bắt đầu bằng keyword thể loại đã biết.
    # Không trả về bừa bãi bất kỳ dòng bold uppercase nào (tránh lấy trích yếu nội dung làm thể loại).
    if bold_lines:
        # Normalize bold_lines set
        bold_lines_norm = {unicodedata.normalize('NFC', b.strip().upper()) for b in bold_lines}
        for i, line in enumerate(lines[:30]):
            clean_line = line.strip()
            if not clean_line: continue
            
            norm = unicodedata.normalize('NFC', ' '.join(clean_line.split()).upper())
            if norm in bold_lines_norm:
                # Loại trừ các dòng không hợp lệ
                if is_excluded_line(norm):
                    continue

                # Ưu tiên 1: Chữ viết tắt (NQ, QĐ, KH, ...)
                possible_abbr = norm.split()[0]
                if possible_abbr in ABBR_MAP:
                    return ABBR_MAP[possible_abbr], i
                
                # Ưu tiên 2: Bắt đầu bằng keyword thể loại đã biết
                for k in keywords:
                    k_up = unicodedata.normalize('NFC', k.upper())
                    if norm.startswith(k_up):
                        # Ranh giới: ký tự tiếp theo phải là khoảng trắng, dấu : hoặc hết dòng
                        if len(norm) == len(k_up) or norm[len(k_up)] in ' :-.':
                            return k, i

                # KHÔNG trả về bừa bãi dòng bold uppercase không khớp keyword nào.
                # (Tránh lấy trích yếu như "VỀ VIỆC PHÊ DUYỆT..." làm thể loại văn bản)

    # Pass 2: Keyword matching (Standard logic)
    # Search in first 30 lines
    for i, line in enumerate(lines[:30]):
        s = line.strip()
        if not s or _is_quoc_hieu_or_tieu_ngu(s):
            continue
        up = s.upper()
        up_norm = unicodedata.normalize('NFC', up)
        
        # Check exclusions
        if is_excluded_line(up):
            continue

        for k in keywords:
            k_norm = unicodedata.normalize('NFC', k.upper())
            # Check if line STARTS with keyword
            if up_norm.startswith(k_norm):
                # Check if boundary (Next char must be space/colon or end)
                if len(up_norm) == len(k_norm) or up_norm[len(k_norm)] in " :.-":
                    # IMPROVEMENT: Only return the keyword part if the line contains more than 3 words
                    # to prevent absorbing the title into the category field.
                    words = s.split()
                    if len(words) > 3:
                        return k, i
                    
                    if bold_lines:
                        norm = unicodedata.normalize('NFC', ' '.join(s.split()).upper())
                        bold_lines_norm = {unicodedata.normalize('NFC', b.strip().upper()) for b in bold_lines}
                        if norm in bold_lines_norm and s.isupper():
                            return s.strip(), i
                    return s[:len(k)].strip(), i
                    
    return "", -1


def _is_summary_exclude_line(s: str, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None) -> bool:
    """SPEC V4.0 Summary line validation with Markdown-Anchored Zoning.
    
    Rejects lines that:
    1. Start with administrative preamble: Thực hiện, Căn cứ, date keywords (Ngày, tháng, năm)
    2. Start with legal/structural markers: Điều, I-, II-, III-, numbered sections (1., etc.)
    3. Start with signature/footer markers: TM., TL., KT., Nơi nhận
    4. Start with special characters (except apostrophe within words)
    - Patterns like <UPPERCASE><digits> with optional dash/slash (e.g. CV-12, NQ/05, QD 110)
    - Số <digits>, SO <digits>
    """
    if not s:
        return True
    
    # Normalization for style check
    norm = ' '.join(s.split())
    is_bold = bool(bold_lines and norm in bold_lines)
    is_heading = bool(uppercase_titles and norm in uppercase_titles)
    
    # If it is a bold heading but short, it might be a section title, keep it excluded
    if is_heading and not is_bold and len(s) < 100:
        return True

    s_strip = s.strip()
    s_up = s_strip.upper()

    # === 1. Forbidden start patterns (administrative preamble) ===
    forbidden_preamble = [
        r"^(THUC|THỰC)\s+(HIEN|HIỆN)",
        r"^-?\s*(CAN|CĂN)\s+(CU|CỨ)",
        r"^(NGAY|NGÀY)\b",
        r"^(DIEU|ĐIỀU)\b",
        r"^(CHUONG|CHƯƠNG)\s+\d",
        r"^(PHAN|PHẦN)\s+\d",
        r"^-?\s*\d+\.\s+", # Numbered list like "1. ", "2. "
        r"^I-\s",
        r"^II-\s",
        r"^III-\s",
        r"^TM\.\s",
        r"^TL\.\s",
        r"^KT\.\s",
        r"^(NOI|NƠI)\s+(NHAN|NHẬN)",
        r"^BAN\s+(HANH|HÀNH)\s+(KEM|KÈM)", # Only exclude "Ban hành kèm theo", allow "Ban hành Quy chế..."
    ]
    for pat in forbidden_preamble:
        if re.search(pat, s_up):
            return True

    # Exclude only explicit 'V/v' style subject markers (like 'V/v', 'V/ V')
    if re.match(r"^V[\/.\\\s]?V\b", s_up) or s_up.startswith("V/"):
        return True

    # === 2. Date keywords ===
    # OLD: if re.search(date_keywords_re, s_up): return True
    # NEW: Only exclude if it looks like a Date Line (starts with date or location+date)
    # e.g. "Hà nội, ngày...", "Ngày 10/10..."
    # Allow: "Báo cáo tháng 8", "Kế hoạch năm 2020"
    if re.match(r"^(NGAY|NGÀY|THANG|THÁNG|NAM|NĂM)\b", s_up):
        return True
    
    # Check for Location prefix "Hà Nội, ngày..." or "Tp.HCM, ngày..."
    if re.search(r"(HÀ\s+NỘI|TP\.?|THÀNH\s+PHỐ).*(NGAY|NGÀY)", s_up):
        return True

    # === 3. Special character check ===
    # User Request: "trích yếu nội dung văn bản không bao giờ khởi đầu bằng ký tự đặc biệt 
    # (trừ " " đối với công văn và các nội dung nằm ngay dưới ký hiệu văn bản)"
    # Note: " " (quotes) logic handled by allowing `"` or `“` or `”`.
    
    # We disallow lines starting with -, +, *, etc.
    # Regex: Start with non-alphanumeric, NOT including quotes.
    # Allowed start chars: A-Z, 0-9, and quotes (" ' “ ”)
    # Disallowed: - – — • + * / @ # % & = _ ~ ^ < > | \ ( [ { ? ! : ;
    
    special_char_start = re.match(r"^[-–—•+*/@#%&=_~^<>|\\(\[\{?!:;]", s_strip)
    if special_char_start:
        return True

    # === 4. Numbered/lettered sections ===
    if re.match(r"^\s*(\d+\.|[IVXLCDM]+\.)", s_up):
        return True

    # === 5. Document codes and symbols (SPEC V3.5 NEW) ===
    
    # Pattern: Số <digits> or SO <digits>
    if re.match(r"^(SO|SỐ)\b", s_up):
        return True
    # Pattern: OCR noise for Số (S6, Se, SE)
    if re.match(r"^(S\d|SE)\b", s_up):
        return True
    
    # Pattern: Document codes followed by digit(s), with optional dash/slash/space
    # Examples: CV-12, CV/05, CV 15, NQ-01, QD 110, KH-15, TT/20, 01/NQ, 05-KH
    doc_code_digit_patterns = [
        r"^(CV|CONG\s+VAN)[-/\s]\d",         # CV-, CV/, CV space, Công văn -/space
        r"^(NQ|NGHI\s+QUYET)[-/\s]\d",       # NQ-, NQ/, NQ space, Nghị quyết -/space
        r"^(QD|QĐ|QUYET\s+DINH)[-/\s]\d",   # QD-, QD/, QD space, Quyết định -/space
        r"^(KH|KE\s+HOACH)[-/\s]\d",         # KH-, KH/, KH space, Kế hoạch -/space
        r"^(TT)[-/\s]\d",                    # TT-, TT/, TT space
    ]
    for pat in doc_code_digit_patterns:
        if re.match(pat, s_up):
            return True
    
    # Pattern: Start with 1-3 uppercase letters optionally followed by digit (without space/dash/slash)
    # This catches CV12, NQ05, QD110, etc.
    if re.match(r"^[A-Z]{1,3}\d", s_up):
        return True
    
    # Pattern: Start with digit(s) followed by slash and 2-3 uppercase letters (e.g. 01/NQ, 05/KH)
    if re.match(r"^\d+/[A-Z]{2,3}", s_up):
        return True

    return False


def _merge_ocr_lines(parts: List[str]) -> str:
    """Merge OCR-broken lines handling hyphenation and broken words."""
    if not parts:
        return ""
    merged = parts[0].strip()
    for nxt in parts[1:]:
        nxt = nxt.strip()
        if not nxt:
            continue
        # If previous ends with hyphenated break, join without space
        if merged.endswith('-'):
            merged = merged[:-1] + nxt
        else:
            merged = merged + ' ' + nxt
    # normalize spaces
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged


def _postprocess_summary(text: str) -> str:
    """Cleans and normalizes the extracted summary text."""
    if not text:
        return ""
    # normalize spaces and remove odd punctuation
    s = text.replace('\n', ' ')
    s = re.sub(r"\s+", " ", s).strip()

    # remove leading/trailing punctuation
    # Remove common start/end noise: - : ; , . *
    s = s.strip(' -–—:;,.“"”’\'')

    # lowercase internal words but preserve acronyms (2-4 uppercase letters)
    orig = text
    acronyms = set(re.findall(r"\b([A-ZĐ]{2,4})\b", orig))
    lower = s.lower()
    
    # capitalize first letter
    if lower:
        lower = lower[0].upper() + lower[1:]

    # restore acronyms
    for a in acronyms:
        lower = re.sub(rf"\b{a.lower()}\b", a, lower)

    return lower.strip()


def _extract_summary(lines: List[str], doc_type_index: int, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None) -> str:
    """SPEC V4.0 Summary extraction — Markdown-Anchored Zoning.

    Rules:
    - START: Immediately under doc_type or on same line.
    - END: First BOLD HEADING, Numbered Section (Điều 1), or too many skip lines.
    - Priority: BOLD lines.
    """
    if doc_type_index < 0:
        return ""

    doc_line = lines[doc_type_index].strip()
    collected: List[str] = []
    
    # 1. Same-line content check
    same_line_content = ""
    words = doc_line.split()
    
    # Check for keywords like "Về", "V/v", "Về việc"
    found_marker = False
    for idx, w in enumerate(words):
        l_w = w.lower()
        if l_w in ["về", "v/v", "v/"] or (l_w == "việc" and idx > 0 and words[idx-1].lower() == "về"):
            start_marker = idx
            if l_w == "việc": start_marker = idx - 1
            same_line_content = " ".join(words[start_marker:])
            found_marker = True
            break
            
    # Fallback: if no marker found but there's content after the likely DocType keyword
    if not found_marker and len(words) > 1:
        # doc_type we extracted is likely the first 1 or 2 words
        # If it's BÁO CÁO ĐỀ ÁN... then doc_type might just be BÁO CÁO (2 words)
        # We'll skip the first few words if they are uppercase markers
        skip_words = 0
        if len(words) >= 1:
            w1 = words[0].upper()
            if any(w1.startswith(kw) for kw in ["QUYẾT", "NGHỊ", "BÁO", "KẾ", "THÔNG", "CÔNG", "TỜ", "ĐỀ"]):
                skip_words = 1
                if len(words) >= 2 and words[1].upper() in ["ĐỊNH", "QUYẾT", "CÁO", "HOẠCH", "BÁO", "VĂN", "TRÌNH", "ÁN", "NGHỊ"]:
                    skip_words = 2
        
        if skip_words < len(words):
            candidate = " ".join(words[skip_words:])
            # Clean up candidate (remove numbers, dots at start if noise)
            candidate = re.sub(r"^[:.,\s-]+", "", candidate).strip()
            if candidate and len(candidate) > 3:
                same_line_content = candidate

    if same_line_content:
        collected.append(same_line_content)
        
    start_idx = doc_type_index + 1
    # Find continuation block
    for k in range(start_idx, min(start_idx + 10, len(lines))):
        s = lines[k].strip()
        if not s: continue
        
        # Boundaries: Motto, Title Headings, Numbered sections
        if _is_quoc_hieu_or_tieu_ngu(s): break
        
        s_up = s.upper()
        norm = ' '.join(s.split())
        
        is_bold = bool(bold_lines and norm in bold_lines)
        is_heading = bool(uppercase_titles and norm in uppercase_titles)
        
        # STOP if we hit a known section marker or a new heading that isn't bold summary
        if re.match(r"^(QUYẾT\s+NGHỊ|QUYET\s+NGHI|KÍNH\s+GỬI|KINH\s+GUI|ĐIỀU|DIEU)\b", s_up):
            break
            
        # If we hit an uppercase heading that is NOT bold summary content, stop
        if is_heading and not is_bold and len(s) < 100:
            break

        # Exclusion: "Căn cứ", "Xét đề nghị" usually start the preamble, not summary
        if re.search(r"^(CĂN\s+CỨ|CAN\s+CU|XÉT\s+ĐỀ\s+NGHỊ|XET\s+DE\s+NGHI)", s_up):
            break
            
        # Date markers also stop summary
        if re.match(r"^(NGÀY|NGAY)\s+\d", s_up) or re.search(r"(HÀ\s+NỘI|TP\.?)\b.*(NGÀY|NGAY)", s_up):
            break

        # If it's BOLD, it's highly likely summary content
        if is_bold:
            # USER REQUEST: Summary often starts with doc type + content
            # If this is the FIRST line collected and it doesn't look like a summary start,
            # but it IS bold, we might be in the right place.
            if not collected:
                # If it starts with action verbs or doc type, it's good
                if any(s_up.startswith(kw) for kw in ["PHÊ DUYỆT", "BAN HÀNH", "VỀ VIỆC", "QUY ĐỊNH", "THÔNG BÁO"]):
                    collected.append(s)
                elif len(s) > 20: 
                    collected.append(s)
            else:
                collected.append(s)
        elif collected:
            # If we already have something and hit a non-bold line, 
            # we check if it's a small OCR break or the end
            if len(s) > 10 and not s_up.startswith("V/V"):
                # If it's a continuation of the same sentence (doesn't start with upper/symbol), keep it
                if s[0].islower():
                    collected.append(s)
                else:
                    # If the next line is ALSO bold, maybe this non-bold line is just a stray
                    next_idx = k + 1
                    is_next_bold = False
                    if next_idx < len(lines):
                        next_s = lines[next_idx].strip()
                        next_norm = ' '.join(next_s.split())
                        if bold_lines and next_norm in bold_lines:
                            is_next_bold = True
                    
                    if is_next_bold:
                        collected.append(s)
                    else:
                        break
            else:
                break
        else:
            # Haven't found summary yet, allow a few lines of "V/v" search
            if "V/V" in s_up or "VỀ VIỆC" in s_up or "VỀ:" in s_up:
                collected.append(s)
            elif len(s) > 15 and not any(kw in s_up for kw in ["SỐ:", "NGÀY"]):
                # Heuristic: first meaningful line under doc_type
                # But be careful not to grab "Cộng hòa..." or similar (already excluded by is_excluded_line in _extract_doc_type but let's be safe)
                if not any(kw in s_up for kw in ["CỘNG HÒA", "ĐỘC LẬP", "HẠNH PHÚC"]):
                    collected.append(s)
                    if not is_bold: break # stop if not bold and we just guessed one line

    # If we have nothing, but we found a BLOCK of bold lines shortly after header?
    # "Tiên đoán trích yếu": Look for first bold block in range [doc_type_index+1 : doc_type_index+10]
    if not collected and bold_lines:
         candidates = []
         search_limit = min(len(lines), doc_type_index + 15)
         for k in range(doc_type_index + 1, search_limit):
             s = lines[k].strip()
             if not s: continue
             if _is_summary_exclude_line(s, bold_lines, uppercase_titles): continue # Strict check
             
             norm = ' '.join(s.split())
             if norm in bold_lines:
                 candidates.append(s)
                 # Determine if we stop? Block is contiguous.
                 # If we have candidates and next line is NOT bold, stop.
                 next_idx = k + 1
                 if next_idx < search_limit:
                     next_s = lines[next_idx].strip()
                     next_norm = ' '.join(next_s.split())
                     if next_norm not in bold_lines:
                         break 
             else:
                 # If we haven't started a block, continue searching
                 if candidates:
                     break
         
         if candidates:
             collected = candidates

    merged = _merge_ocr_lines(collected)
    processed = _postprocess_summary(merged)
    return processed


def _extract_summary_fallback(lines: List[str]) -> str:
    """Fallback strategies to force extract summary if standard method fails.
    
    Strategy 1: Scan first 30 lines for "Về việc", "V/v", "Trích yếu".
    Strategy 2: First meaningful line that isn't a header/date/recipient.
    """
    if not lines:
        return ""

    # Strategy 1: Explicit markers
    # We look for lines starting with cues
    cues = ["VỀ VIỆC", "V/V", "TRÍCH YẾU"]
    for i, line in enumerate(lines[:30]):
        s = line.strip()
        s_up = s.upper()
        
        # Check if line starts with any cue
        # Handling "V / v" or "V . v" noise? Standardize first.
        # Simple check:
        for cue in cues:
            if s_up.startswith(cue) or s_up.replace(" ", "").startswith(cue.replace(" ", "")):
                # Found it. Capture this line and maybe next if short?
                # Usually "Về việc: ...."
                # If content is short, grab next line too?
                content = s
                if len(content) < 50 and i + 1 < len(lines):
                     next_line = lines[i+1].strip()
                     if next_line and not any(k in next_line.upper() for k in ["KÍNH GỬI", "ĐIỀU", "CĂN CỨ"]):
                         content += " " + next_line
                return _postprocess_summary(content)

    # Strategy 2: Heuristic - First "Body" Paragraph
    # Skip headers, dates, recipients (Kính gửi), "Căn cứ"
    # Find first block of text that looks like a sentence.
    
    blacklist = [
        "CỘNG HÒA", "ĐỘC LẬP", "HẠNH PHÚC", "SOCIALIST", "INDEPENDENCE",
        "SỐ:", "SỐ :", "NO:", "DATE:", "NGÀY", "HÀ NỘI", "TP.",
        "THẨM PHÁN", "THƯ KÝ", "ĐẠI DIỆN",
        "KÍNH GỬI", "NƠI NHẬN", "LƯU:",
        "QUYẾT ĐỊNH", "NGHỊ QUYẾT", "THÔNG TƯ", "CHỈ THỊ", "THÔNG BÁO", # Doc Types
        "CĂN CỨ", "XÉT", # Legal bases (prologue)
        # Agency Keywords (avoid grabbing header)
        "UBND", "ỦY BAN", "SỞ", "BỘ", "TỔNG CỤC", "BAN", "TRƯỜNG", "HỘI ĐỒNG", 
        "CỤC", "VIỆN", "TRUNG TÂM", "CHI CỤC", "ĐOÀN", "KHỐI",
    ]
    
    for i, line in enumerate(lines[:40]):
        s = line.strip()
        if not s: continue
        s_up = s.upper()
        
        # Skip blacklisted keywords
        # FIX: Only skip if line is mostly UPPERCASE (likely a header). 
        # Sentences like "UBND tỉnh yêu cầu..." should be allowed.
        is_upper_line = s.isupper() or (len(s) > 0 and sum(1 for c in s if c.isupper()) / len(s) > 0.7)
        
        if is_upper_line and any(b in s_up for b in blacklist):
            continue
            
        # FIX: Normalize line for blacklist check (remove leading *, -, spaces)
        s_clean = re.sub(r"^[\*\-\.,\s]+", "", s_up)
        
        # Also skip strict preamble keywords/starters regardless of case ratio
        # "Số: 99..." might be mixed case "Số"
        # Check against s_clean to catch "* T.p ..."
        if any(s_clean.startswith(b) for b in ["CỘNG HÒA", "ĐỘC LẬP", "HẠNH PHÚC", "KÍNH GỬI", "SỐ:", "SỐ", "NO:", "NGÀY", "HÀ NỘI", "TP.", "T.P"]):
            continue
            
        # Skip if purely uppercase (likely title or agency)
        if is_upper_line and len(s) < 50:
            continue
            
        # Skip agency-like lines (extracted earlier, but just in case)
        if _is_quoc_hieu_or_tieu_ngu(s):
            continue
            
        # FIX: Apply strict summary line exclusion to Fallback candidates too
        # This catches "_________", Date lines, etc.
        if _is_summary_exclude_line(s):
            continue
            
        # If we reached here, it's a candidate.
        # Check if it looks like a sentence? 
        return _postprocess_summary(s)
        
    return ""


def _looks_like_proper_name(text: str) -> bool:
    """Check if the text looks like a Vietnamese proper name (Title Case)."""
    if not text:
        return False
    words = text.split()
    if not (2 <= len(words) <= 6):
        return False
    
    # Check if all words start with an uppercase letter
    # and contain only letters, with rest being lowercase (Proper Case)
    for w in words:
        if not w or not w[0].isupper():
            return False
        if len(w) > 1:
            rest_letters = [c for c in w[1:] if c.isalpha()]
            if rest_letters and not all(c.islower() for c in rest_letters):
                return False
        # Digits are definitely out in names.
        if any(c.isdigit() for c in w):
            return False
            
    # Optional: Use underthesea if available for better NER validation
    try:
        from .post_processing import get_post_processor
        pp = get_post_processor()
        if pp.use_nlp and hasattr(pp, 'ner'):
            res = pp.ner(text)
            # res format: [(word, pos, chunk, label), ...]
            # Check if majority of tokens are labeled as PER
            per_count = sum(1 for _, _, _, label in res if label == 'B-PER' or label == 'I-PER')
            if per_count > 0:
                return True
    except:
        pass

    return True


def _extract_signer(lines: List[str]) -> str:
    """Người ký: tên dạng Proper Noun (Title Case) hoặc VIẾT HOA ở cuối văn bản.
    
    Tối ưu:
    - Tìm tên phía trên dòng "Nơi nhận" 
    - Chấp nhận tên VIẾT HOA (Phổ biến trong văn bản hành chính)
    - Ưu tiên dòng có chức danh đi kèm phía trên (KT., CHỦ TỊCH,...)
    - USER REQUEST: Phải bắt đầu bằng danh từ riêng (Proper Name).
    """
    if not lines:
        return ""

    # 1. Search in the last 25 lines (footer area)
    tail_len = min(len(lines), 25)
    real_start_idx = len(lines) - tail_len
    tail = lines[-tail_len:]
    
    # find boundaries like "Nơi nhận" to avoid capturing names in distribution list
    distribution_idx = -1
    for i, line in enumerate(tail):
        if "NƠI NHẬN" in line.upper():
            distribution_idx = i
            break
            
    # If found "Nơi nhận", only check lines ABOVE it
    search_tail = tail[:distribution_idx] if distribution_idx > 0 else tail

    title_pattern = (
        r"^(TM\.|TL\.|KT\.|B[IÍ]\s+TH[ƯU]|PHÓ|PHO"
        r"|CHỦ\s+TỊCH|CHU\s+TICH|TRƯỞNG|TRUONG"
        r"|GIÁM\s+ĐỐC|GIAM\s+DOC|HIỆU\s+TRƯỞNG|HIEU\s+TRUONG"
        r"|CỤC\s+TRƯỞNG|CHI\s+CỤC\s+TRƯỞNG|CHI\s+CUC\s+TRUONG"
        r"|THỦ\s+TRƯỞNG|THU\s+TRUONG|VIỆN\s+TRƯỞNG|VIEN\s+TRUONG"
        r"|P\.\s*GIÁM\s+ĐỐC|P\.\s*GIAM\s+DOC|P\.\s*TRƯỞNG\s+PHÒNG)"
    )

    name_blacklist_re = re.compile(
        r"\b(TM\.|TL\.|KT\.|B[ÍI]\s+TH[ƯU]|CHỦ\s+TỊCH|CHU\s+TICH|PHÓ|PHO|TRƯỞNG|TRUONG"
        r"|GIÁM\s+ĐỐC|GIAM\s+DOC|HIỆU\s+TRƯỞNG|HIEU\s+TRUONG|THỦ\s+TRƯỞNG|THU\s+TRUONG|VIỆN\s+TRƯỞNG|VIEN\s+TRUONG"
        r"|UBND|HĐND|HOND|SỞ|SO|CỤC|CUC|PHÒNG|PHONG|BAN|NƠI\s+NHẬN|NOI\s+NHAN|LƯU|LUU|ĐẢNG|DANG)\b",
        re.IGNORECASE
    )

    def _is_title_line(s_up: str) -> bool:
        """Kiểm tra dòng có phải chức danh ký không."""
        return bool(re.search(title_pattern, s_up))

    def _is_valid_name(line: str) -> bool:
        """Kiểm tra dòng có thể là tên người ký không."""
        # Loại trừ nếu dòng là chức danh (kể cả không dấu - OCR)
        if _is_title_line(line.upper()):
            return False
        if name_blacklist_re.search(line):
            return False
        if re.search(r"\d", line):  # Tên không chứa số
            return False
        words = line.split()
        if not (2 <= len(words) <= 7):
            return False
        s_up = line.upper()
        is_all_caps = s_up == line and any(c.isalpha() for c in line)
        is_title_case = all(w[0].isupper() for w in words if w and w[0].isalpha())
        if not (is_all_caps or is_title_case):
            return False
        test_name = " ".join([w.capitalize() for w in words]) if is_all_caps else line
        return _looks_like_proper_name(test_name)

    # ===== METHOD 2 (ƯU TIÊN): Scan thuận chiều - tìm tên ngay sau dòng chức danh =====
    # Văn bản VN: "TM. ỦY BAN" → "CHỦ TỊCH" → "Nguyễn Văn A"
    # Hoặc: "GIÁM ĐỐC" → "Trần Thị B"
    method2_result = ""
    forward_list = list(search_tail)
    for mi in range(len(forward_list) - 1):
        this_line = forward_list[mi].strip()
        next_line = forward_list[mi + 1].strip()
        if not this_line or not next_line:
            continue
        if _is_title_line(this_line.upper()) and _is_valid_name(next_line):
            method2_result = next_line  # ghi đè → lấy kết quả cuối (gần chỗ ký nhất)

    if method2_result:
        return method2_result

    # ===== METHOD 1 (FALLBACK): Scan ngược chiều =====
    candidates = []

    for i in range(len(search_tail) - 1, -1, -1):
        line = search_tail[i].strip()
        if not line: continue
        
        s_up = line.upper()
        
        # Exclusions
        if "LƯU:" in s_up or "LƯU VT" in s_up: continue
        if any(kw in s_up for kw in ["NGÀY", "THÁNG", "NĂM"]): continue 
        if re.search(title_pattern, s_up): continue
             
        words = line.split()
        if not (2 <= len(words) <= 7):
            continue

        # Check if line is either Title Case or ALL CAPS
        is_all_caps = line.upper() == line and any(c.isalpha() for c in line)
        is_title_case = all(w[0].isupper() for w in words if w and w[0].isalpha())

        if not (is_all_caps or is_title_case):
            continue
        score = 10
        if is_all_caps:
            score += 5

        # Bonus: Check for Title line ABOVE
        current_abs_idx = real_start_idx + i
        for k in range(1, 4):  # Scan 3 lines up
            prev = current_abs_idx - k
            if prev < 0:
                break
            p_line = lines[prev].strip().upper()
            if _is_title_line(p_line):
                score += (25 - k * 2)
                break

        # Prefer bottom lines
        score += i
        candidates.append((score, line))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    # Final check: return capitalized version
    return candidates[0][1]


def _extract_tenure(lines: List[str]) -> str:
    """Extract tenure/term information (e.g. 'khóa V - nhiệm kỳ 2005 -2010').
    
    Scanning logic:
    - Look in first 20 lines (header/preamble).
    - Pattern: 'nhiệm kỳ' followed by years.
    - User Request: Output format "YYYY - YYYY".
    """
    # Regex to capture "nhiệm kỳ ... 20xx ... 20xx"
    # Returns only "20xx - 20xx"
    # Handles various separators like hyphen, en-dash
    pat = r"nhi[ệe]m\s+k[ỳy]\b.*?(\d{4})\s*[-–]\s*(\d{4})"
    
    for line in lines[:20]:
        s = line.strip()
        if not s: continue
        
        match = re.search(pat, s, re.IGNORECASE)
        if match:
             y1 = match.group(1)
             y2 = match.group(2)
             return f"{y1} - {y2}"
                
    return ""

def _map_symbol_to_issuer(symbol: str) -> str:
    """Map abbreviated symbol (suffix) to full Issuer name from Reference DB."""
    if not symbol:
        return ""
    s_up = symbol.upper().strip()
    mapping = _GLOBAL_REF_DB.get("issuers", {})
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if re.search(rf"(?:^|[-/\s]){key}(?:$|[-/\s])", s_up):
            return mapping[key]
    return ""


def extract_metadata(text: str, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None) -> Dict[str, str]:
    """API đơn giản theo SPEC V3: trích metadata văn bản hành chính Việt Nam."""
    lines = _normalize_lines(text, bold_lines=bold_lines, uppercase_titles=uppercase_titles)
    if not lines:
        return {
            "co_quan_ban_hanh": "",
            "so_van_ban": "",
            "ky_hieu_van_ban": "",
            "ngay_ban_hanh": "",
            "the_loai_van_ban": "",
            "trich_yeu_noi_dung": "",
            "nguoi_ky": "",
        }

    # Extract basic components
    doc_type, idx = _extract_doc_type(lines, uppercase_titles=uppercase_titles, bold_lines=bold_lines)
    issuer = _extract_agency(lines, doc_type, bold_lines=bold_lines, doc_type_index=idx, uppercase_titles=uppercase_titles)
    num, symbol = _extract_number_and_symbol(lines)
    
    # User Request: "ký hiệu văn bản thì không cần dịch"
    # Symbol remains as extracted from _extract_number_and_symbol

    # Fallback to Bold/Title check for DocType if still empty
    if not doc_type and bold_lines:
        known_types_upper = {v.upper() for v in ABBR_TO_TYPE.values()}
        for line in bold_lines:
             s_up = line.upper().strip()
             if s_up in known_types_upper:
                 doc_type = line.strip()
                 break
             for kt in known_types_upper:
                 if s_up.startswith(kt):
                      if len(s_up) == len(kt) or not s_up[len(kt)].isalnum():
                          doc_type = line[:len(kt)].strip()
                          break
             if doc_type: break

    signed_date = _extract_date_v3(lines)
    
    # Heuristic for "CÔNG VĂN"
    if not doc_type and symbol and ("CV" in symbol.upper() or "CÔNG VĂN" in symbol.upper()):
          doc_type = "CÔNG VĂN"

    summary = _extract_summary(lines, idx, bold_lines=bold_lines)
    
    # Mandatory Summary Fallback
    if not summary:
        summary = _extract_summary_fallback(lines)
        if not doc_type and summary:
             doc_type = "CÔNG VĂN"

    # Prepend DocType to Summary if not already there
    if doc_type and summary:
        dt_up = doc_type.upper()
        sm_up = summary.upper()
        if dt_up not in sm_up:
            summary = f"{doc_type} {summary}"
    
    signer = _extract_signer(lines)
    tenure = _extract_tenure(lines)

    # Final Validation: Check if the document is substantially valid
    is_valid = _is_valid_document(
        issuer=issuer,
        num=num,
        symbol=symbol,
        date=signed_date,
        doc_type=doc_type,
        summary=summary,
        signer=signer
    )

    # Return Vietnamese keys to match Excel Exporter expectation
    result = {
        "co_quan_ban_hanh": issuer or "",
        "so_van_ban": num or "",
        "ky_hieu_van_ban": symbol or "",
        "ngay_ban_hanh": signed_date or "",
        "the_loai_van_ban": doc_type or "",
        "trich_yeu_noi_dung": summary or "",
        "nguoi_ky": signer or "",
        "nhiem_ky": tenure or "", 
        "hop_so": "", # User usually enters this manually or it's context-dependent
        "so_ho_so": "", # Initialized for GUI binding
        "ngay_ky": signed_date or "", # Primary alias requested by user
        "is_valid": is_valid, # Hidden field for internal filtering
        # Keep old keys for backward compat if needed (optional)
        "issuer": issuer or "",
        "doc_number": num or "",
        "symbol": symbol or "",
        "signed_date": signed_date or "",
        "doc_type": doc_type or "",
        "summary": summary or "",
        "signer": signer or "",
        "tenure": tenure or "", 
        "ngay_ki": signed_date or "", # OCR variant alias
    }
    
    # If invalid per strict criteria, mark it
    if not is_valid:
        logger.warning("Document identified as INVALID (missing key metadata)")
        
    return result


def _is_valid_document(issuer: str, num: str, symbol: str, date: str, doc_type: str, summary: str, signer: str) -> bool:
    """Kiểm tra xem văn bản có đủ thông tin tối thiểu để coi là hợp lệ không.
    
    Văn bản bị coi là không hợp lệ nếu thiếu đồng thời:
    - Loại văn bản
    - Ngày ban hành
    - Số văn bản VÀ Ký hiệu
    - Cơ quan ban hành VÀ Người ký (hoặc trích yếu quá ngắn)
    """
    # Trích yếu quá ngắn thường là rác OCR hoặc trang thông tin rác
    if not summary or len(summary) < 10:
        has_summary = False
    else:
        has_summary = True

    conditions = [
        bool(doc_type),
        bool(date),
        bool(num or symbol),
        bool(issuer or signer or (has_summary and len(summary) > 50))
    ]
    
    # Một văn bản hợp lệ nên thỏa mãn ít nhất 2 điều kiện quan trọng
    # Hoặc nếu có Loại văn bản + (Ngày hoặc Số)
    if doc_type and (date or num or symbol):
        return True
    
    # Nếu thiếu Loại văn bản thì phải có ít nhất 3 điều kiện còn lại
    if sum(conditions) >= 2:
        return True
        
    return False


def _process_file_for_extract(args):
    """Module-level worker used by ProcessPoolExecutor.

    Receives a tuple (file_path, pages, base_dir, reference_path) and
    returns the metadata dict for that file. We construct a fresh
    MetadataExtractor inside the process to avoid pickling self.
    """
    # Normalize args tuple to (file_path, pages, base_dir, reference_path, styles)
    styles = None
    if len(args) == 2:
        file_path, pages = args
        base_dir = None
        reference_path = None
    elif len(args) == 4:
        file_path, pages, base_dir, reference_path = args
    elif len(args) == 5:
        file_path, pages, base_dir, reference_path, styles = args
    else:
        # Fallback: try to unpack first two
        file_path, pages = args[0], args[1]
        base_dir = None
        reference_path = None

    text = "\n".join(pages)
    # create an extractor in the worker process (safe for multiprocessing)
    extractor = MetadataExtractor(reference_path=reference_path) if reference_path else MetadataExtractor(reference_path=None)
    # Prepare bold-lines set for first pages if styles provided
    bold_set = None
    if styles:
        try:
            # styles expected as dict of page_index -> list of line strings
            first_pages = [0, 1]
            bold_set = set()
            upper_set = set()
            for p in first_pages:
                for l in styles.get(p, []):
                    norm = ' '.join(l.split())
                    # merged styles may contain both bold and uppercase hints;
                    # collect them into both sets so extractor can prefer either.
                    bold_set.add(norm)
                    upper_set.add(norm)
        except Exception:
            bold_set = None
            upper_set = None
    else:
        upper_set = None
    data = extractor.extract_from_text(text, file_path, bold_lines=bold_set, uppercase_titles=upper_set)

    # Số trang văn bản: ưu tiên dùng chính số lượng trang đã đọc từ PDF
    try:
        if isinstance(pages, list):
            data["so_trang_van_ban"] = str(len(pages))
    except Exception:
        # Nếu có lỗi, giữ nguyên giá trị đã được extractor suy luận (nếu có)
        pass

    # add base_dir derived fields
    if base_dir:
        rel_path = os.path.relpath(file_path, base_dir)
        data["duong_dan_file"] = rel_path
        data["xem_file"] = f'=HYPERLINK("{rel_path}", "Xem")'

        rel_dir = os.path.dirname(rel_path)
        if rel_dir:
            folder_parts = rel_dir.split(os.sep)
            candidate = folder_parts[-1] if folder_parts else ''
            import re as _re
            m_folder = _re.search(r"(\d+)", candidate)
            # Do NOT override extracted metadata with folder name.
            # Store inferred values separately so OCR/text extraction remains primary.
            if m_folder:
                data["so_ho_so_from_path"] = m_folder.group(1)
                data["so_va_ky_hieu_ho_so_from_path"] = m_folder.group(1)
            elif candidate:
                data["so_va_ky_hieu_ho_so_from_path"] = candidate

        # filename parsing (outside rel_dir handling)
        try:
            filename = os.path.basename(file_path)
            stem, _ = os.path.splitext(filename)
            nums = _re.findall(r"(\d+)", stem)
            # Store filename-derived hints separately; do not use them to populate
            # primary metadata fields which must come from OCR/text in the PDF.
            if len(nums) >= 2 and ('_' in stem or '-' in stem):
                first_num = nums[0]
                last_num = nums[-1]
                data["so_ho_so_from_filename"] = first_num
                data["so_va_ky_hieu_ho_so_from_filename"] = f"{first_num}_{last_num}"
                data["so_van_ban_from_filename"] = last_num
                # DO NOT overwrite primary so_ho_so here
            else:
                m_lead = _re.match(r"^(\d{3,})", stem)
                if m_lead:
                    data["so_ho_so_from_filename"] = m_lead.group(1)
                    data["so_va_ky_hieu_ho_so_from_filename"] = m_lead.group(1)
        except Exception:
            pass

    return data


# Mapping viết tắt -> thể loại văn bản
ABBR_TO_TYPE = {
    'NQ': 'Nghị quyết',
    'CT': 'Chỉ thị',
    'KL': 'Kết luận',
    'TT': 'Thông tri',
    'HD': 'Hướng dẫn',
    'QD': 'Quyết định',
    'QĐ': 'Quyết định',
    'TB': 'Thông báo',
    'BC': 'Báo cáo',
    'KH': 'Kế hoạch',
    'CV': 'Công văn',
    'BB': 'Biên bản',
    'TTNB': 'Thông tri nội bộ',
    'TTr': 'Tờ trình',
    'DA': 'Đề án',
    'GP': 'Giấy phép',
    'GC': 'Giấy chứng nhận',
    'GM': 'Giấy mời',
    'QC': 'Quy chế',
}

def _normalize_abbr(s: str) -> str:
    """Normalize ký hiệu string for matching abbreviations.

    - Replace Vietnamese Đ/đ with D/d so QĐ -> QD
    - Keep only ASCII letters and convert to uppercase
    """
    if not s:
        return ''
    s = s.replace('Đ', 'D').replace('đ', 'd')
    # remove non-letters
    filtered = ''.join([ch for ch in s if ch.isalpha()])
    return filtered.upper()


class ReferenceDB:
    """Lightweight reference database loaded from a tab-separated text file.

    Expected format (tab-separated, per line):
    id \t ky_hieu \t date \t the_loai \t summary

    The loader is forgiving and will accept lines with fewer columns.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.entries: List[Dict[str, str]] = []
        self._load()

    def _load(self):
        with open(self.filepath, 'r', encoding='utf-8') as fh:
            for row in fh:
                # skip empty lines
                if not row.strip():
                    continue
                parts = [p.strip() for p in row.split('\t')]
                # Normalize length
                while len(parts) < 5:
                    parts.append('')
                entry = {
                    'id': parts[0],
                    'ky_hieu': parts[1],
                    'ngay': parts[2],
                    'the_loai': parts[3],
                    'summary': parts[4]
                }
                self.entries.append(entry)

    def find_similar(self, text: str, top_n: int = 3, min_ratio: float = 0.45) -> List[Dict[str, object]]:
        """Return a list of candidate entries similar to `text` with a score.

        Uses difflib.SequenceMatcher ratio on the summary field.
        """
        if not text or not self.entries:
            return []
        text_norm = ' '.join(text.split())
        candidates = []
        for e in self.entries:
            s = e.get('summary', '')
            if not s:
                continue
            ratio = difflib.SequenceMatcher(None, text_norm.lower(), s.lower()).ratio()
            if ratio >= min_ratio:
                candidates.append({'entry': e, 'score': ratio})
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:top_n]

class MetadataExtractor:
    def __init__(self, reference_path: Optional[str] = None):
        """Create extractor. If `reference_path` is provided (or a file named
        `text.txt` exists in the project root) we load it as a reference database
        to help match similar documents during extraction.
        """
        self.reference = None
        # If a specific path provided, try to load it. Otherwise if text.txt
        # exists next to the project root, load that.
        candidate = None
        if reference_path:
            candidate = reference_path
        else:
            # look for text.txt in repo root (one level up from src)
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            default = os.path.join(repo_root, 'text.txt')
            if os.path.exists(default):
                candidate = default

        if candidate and os.path.exists(candidate):
            try:
                self.reference = ReferenceDB(candidate)
                logger.info(f"Loaded reference DB from {candidate} ({len(self.reference.entries)} entries)")
            except Exception:
                logger.exception("Failed to load reference DB")
                self.reference = None

    def extract_from_text(self, text: str, file_path: Optional[str] = None, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None) -> Dict[str, str]:
        """Trích xuất metadata chính từ nội dung văn bản PDF.
        Delegates to the global optimized extract_metadata function (SPEC V3).
        """
        # Call the optimized global function
        meta = extract_metadata(text, bold_lines=bold_lines, uppercase_titles=uppercase_titles)
        
        # Add file-specific fields if needed (e.g. loai_ban, con_dau default)
        if "loai_ban" not in meta:
             meta["loai_ban"] = "bản chính"
        if "con_dau" not in meta:
             meta["con_dau"] = ""
             
        return meta
        
    def extract_multiple_from_text(self, text: str, file_path: Optional[str] = None, bold_lines: Optional[set] = None, uppercase_titles: Optional[set] = None) -> List[Dict[str, str]]:
        """Trích metadata cho 1 văn bản duy nhất từ toàn bộ text.

        Theo yêu cầu nghiệp vụ hiện tại: **mỗi file PDF tương ứng 1 dòng văn bản** trong Excel.
        Vì vậy hàm này không còn tách nhiều văn bản trong cùng một file nữa, mà chỉ
        gọi `extract_from_text` cho toàn bộ nội dung.
        """
        if not text or not text.strip():
            return []

        # Bỏ qua logic chia block; xử lý toàn bộ text như một văn bản
        res = self.extract_from_text(text, file_path=file_path, bold_lines=bold_lines, uppercase_titles=uppercase_titles)
        return [res]

    def extract_from_directory(self, all_texts: Dict[str, List[str]], base_dir: Optional[str] = None, processes: int = 1, all_styles: Optional[Dict[str, Dict[int, List[str]]]] = None) -> List[Dict[str, str]]:
        """Trích xuất metadata cho nhiều file (dữ liệu từ pdf_processor).

        If `processes` > 1, extraction is distributed across processes using
        concurrent.futures.ProcessPoolExecutor. Each worker constructs its own
        MetadataExtractor to avoid pickling the parent instance.
        """
        if not all_texts:
            return []

        if processes and processes > 1:
            # Use multiprocessing to parallelize work across processes
            from concurrent.futures import ProcessPoolExecutor
            reference_path = None
            try:
                reference_path = self.reference.filepath if self.reference else None
            except Exception:
                reference_path = None

            args = []
            for fp, pages in all_texts.items():
                styles_for_fp = None
                try:
                    if all_styles and fp in all_styles:
                        styles_for_fp = all_styles.get(fp)
                except Exception:
                    styles_for_fp = None
                args.append((fp, pages, base_dir, reference_path, styles_for_fp))
            metadata_list: List[Dict[str, str]] = []
            file_paths = [fp for fp, _ in all_texts.items()]
            with ProcessPoolExecutor(max_workers=processes) as ex:
                for res in ex.map(_process_file_for_extract, args):
                    metadata_list.append(res)
            # do not return here; fall through to post-processing grouping below

        # fallback: sequential processing
        metadata_list: List[Dict[str, str]] = []
        expanded_file_paths: List[str] = []  # mỗi phần tử tương ứng 1 văn bản (có thể nhiều văn bản / 1 file)
        base_files = list(all_texts.keys())
        for file_path in base_files:
            pages = all_texts[file_path]
            text = "\n".join(pages)
            styles_for_file = None
            if all_styles and file_path in all_styles:
                # prepare set of bold lines from first pages
                try:
                    styles_for_file = all_styles.get(file_path)
                    bold_first = set()
                    upper_first = set()
                    for pidx in (0, 1):
                        for ln in styles_for_file.get(pidx, []):
                            norm = ' '.join(ln.split())
                            bold_first.add(norm)
                            upper_first.add(norm)
                except Exception:
                    bold_first = None
                    upper_first = None
            else:
                bold_first = None
                upper_first = None

            # Thay vì coi cả file là 1 văn bản, sử dụng extract_multiple_from_text
            docs = self.extract_multiple_from_text(text, file_path=file_path, bold_lines=bold_first, uppercase_titles=upper_first)
            if not docs:
                continue

            for doc in docs:
                data = dict(doc)  # sao chép để tránh tham chiếu chung
                if base_dir:
                    rel_path = os.path.relpath(file_path, base_dir)
                    data["duong_dan_file"] = rel_path
                    data["xem_file"] = f'=HYPERLINK("{rel_path}", "Xem")'
                    
                    # Lấy số và ký hiệu hồ sơ từ tên thư mục cha của file
                    try:
                        # Get parent folder name (ignoring base_dir)
                        folder_parts = []
                        rel_dir = os.path.dirname(rel_path)
                        if rel_dir:
                            # Lấy tên thư mục con trực tiếp chứa file -> thường là 'số hồ sơ'
                            folder_parts = rel_dir.split(os.sep)
                            if folder_parts:
                                # Prefer numeric folder name as so_ho_so
                                candidate = folder_parts[-1]
                                if candidate.isdigit():
                                    data["so_ho_so"] = candidate
                                    data["so_va_ky_hieu_ho_so"] = candidate
                                else:
                                    # If folder name contains digits, extract leading digits
                                    import re as _re
                                    m_folder = _re.search(r"(\d+)", candidate)
                                    if m_folder:
                                        data["so_ho_so"] = m_folder.group(1)
                                        data["so_va_ky_hieu_ho_so"] = m_folder.group(1)
                                    else:
                                        data["so_va_ky_hieu_ho_so"] = candidate

                        # --- NEW LOGIC: Extract Tenure (Nhiệm kỳ) from directory path ---
                        # Rules: Check parts of rel_dir for "Nhiệm kỳ" or "Nhiem ky". 
                        # OR if it contains a year range like "2010-2018".
                        # Use the immediate parent if it matches, otherwise scan up.
                        for part in reversed(folder_parts):
                            norm_part = " ".join(part.lower().split())
                            
                            # Priority 1: Explicit "Nhiệm kỳ" label
                            if "nhiem ky" in norm_part or "nhiệm kỳ" in norm_part:
                                data["nhiem_ky"] = part
                                data["tenure"] = part
                                break
                            
                            # Priority 2: Year range (YYYY-YYYY or YYYY_YYYY)
                            # User request: "G:\...\2.SOHOA_KCCQĐT_2010-2018" -> 2010-2018
                            import re as _re
                            m_years = _re.search(r"(\d{4})[-_](\d{4})", part)
                            if m_years:
                                y1, y2 = int(m_years.group(1)), int(m_years.group(2))
                                # Validity check: reasonable years
                                if 1900 <= y1 <= 2100 and 1900 <= y2 <= 2100:
                                    # Use the range as the tenure
                                    val = f"{y1}-{y2}"
                                    data["nhiem_ky"] = val
                                    data["tenure"] = val
                                    break
                        # -----------------------------------------------------------------

                        # Nếu không có thông tin đủ từ thư mục, thử parse từ tên file
                        # Ví dụ: "3001_0001.pdf" -> so_ho_so=3001, so_van_ban=0001
                        filename = os.path.basename(file_path)
                        stem, _ = os.path.splitext(filename)
                        try:
                            import re as _re
                            # Collect all digit groups in the stem
                            nums = _re.findall(r"(\d+)", stem)
                            # If there are at least two numeric groups and the name contains a separator
                            if len(nums) >= 2 and ('_' in stem or '-' in stem):
                                first_num = nums[0]
                                last_num = nums[-1]
                                # if so_ho_so not already set from folder, set it from filename's first numeric group
                                if not data.get("so_ho_so"):
                                    data["so_ho_so"] = first_num
                                # set per-file combined id using underscore
                                data["so_va_ky_hieu_ho_so"] = f"{first_num}_{last_num}"
                                # if extractor failed to get a văn bản số from text, use filename's last numeric group
                                if not data.get("so_van_ban"):
                                    data["so_van_ban"] = last_num
                                # store explicit filename-derived parts
                                data["so_ho_so_from_filename"] = first_num
                                data["so_van_ban_from_filename"] = last_num
                            else:
                                # Try a loose match: leading digits could be the so_ho_so
                                m_lead = _re.match(r"^(\d{3,})", stem)
                                if m_lead and not data.get("so_ho_so"):
                                    data["so_ho_so"] = m_lead.group(1)
                                    data["so_va_ky_hieu_ho_so"] = m_lead.group(1)
                        except Exception:
                            # If anything fails, don't crash the extractor; log and continue
                            logger.debug("Filename parsing for so_ho_so/so_van_ban failed", exc_info=True)
                    except Exception:
                        logger.exception('Failed to extract folder name as so_va_ky_hieu_ho_so')

                # Assign page count
                try:
                    if isinstance(pages, list):
                        data["so_trang_van_ban"] = str(len(pages))
                except Exception:
                    pass

                metadata_list.append(data)
                expanded_file_paths.append(file_path)

        # Post-process grouping: compute per-ho-so aggregates (group by so_ho_so nếu có,
        # nếu không thì theo thư mục cha). Mỗi phần tử trong expanded_file_paths tương ứng 1 văn bản.
        try:
            groups = {}
            for fp, data in zip(expanded_file_paths, metadata_list):
                key = data.get('so_ho_so') or os.path.basename(os.path.dirname(fp)) or 'root'
                groups.setdefault(key, []).append(fp)

            # compute aggregates per group
            for key, fps in groups.items():
                total_docs = len(fps)
                total_pages = 0
                # compute page counts using all_texts (số trang hồ sơ = tổng trang của tất cả file trong nhóm)
                for f in set(fps):
                    try:
                        total_pages += len(all_texts.get(f, []))
                    except Exception:
                        total_pages += 0

                # assign aggregate fields cho từng văn bản trong nhóm
                running_index = 1
                for fp, md in zip(expanded_file_paths, metadata_list):
                    if (md.get('so_ho_so') or os.path.basename(os.path.dirname(fp)) or 'root') != key:
                        continue
                    md['so_luong_trang_ho_so'] = str(total_pages)
                    md['tong_so_van_ban_trong_ho_so'] = str(total_docs)
                    md['muc_luc_so'] = str(running_index)
                    md['dia_chi_tai_lieu_goc'] = fp
                    running_index += 1

                    if not md.get('so_va_ky_hieu_ho_so'):
                        parent = os.path.basename(os.path.dirname(fp))
                        if parent:
                            md['so_va_ky_hieu_ho_so'] = parent

                    nk = md.get('nhiem_ky')
                    if not nk:
                        parent = os.path.basename(os.path.dirname(fp))
                        m = re.search(r'(20\d{2})\s*[-_/]\s*(20\d{2})', parent)
                        if m:
                            md['nhiem_ky'] = f"{m.group(1)}-{m.group(2)}"
                        else:
                            md['nhiem_ky'] = ''
        except Exception:
            logger.debug('Post-group aggregation failed', exc_info=True)

        return metadata_list
