from dataclasses import dataclass
from typing import Optional

@dataclass
class DocumentMetadata:
    co_quan_ban_hanh: str = ""
    so_van_ban: str = ""
    ky_hieu_van_ban: str = ""
    ngay_ky: str = ""
    the_loai_van_ban: str = ""
    trich_yeu_noi_dung: str = ""
    nguoi_ky: str = ""
    loai_ban: str = "bản chính"
    duong_dan_file: Optional[str] = None
    xem_file: Optional[str] = None
    so_ho_so: str = ""