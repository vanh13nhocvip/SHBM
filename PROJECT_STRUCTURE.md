# Cấu Trúc và Mô Hình Phần Mềm SHBM (PDF Metadata Extractor)

Tài liệu này tóm tắt kiến trúc, luồng dữ liệu và cấu trúc mã nguồn của dự án SHBM.

## 1. Tổng Quan
**SHBM** (Software for Handling & Bien Muc?) là một ứng dụng Python desktop dùng để trích xuất tự động thông tin biên mục (metadata) từ các file PDF văn bản hành chính. Phần mềm hỗ trợ cả văn bản PDF dạng text và dạng scan (thông qua OCR).

## 2. Cấu Trúc Thư Mục
Dưới đây là cây thư mục chính của dự án:

```
SHBM/
├── Run.bat                     # Script khởi chạy nhanh ứng dụng (Windows)
├── src/                        # Mã nguồn chính
│   ├── __init__.py
│   ├── __main__.py             # Entry point khi chạy dạng module (python -m src)
│   ├── config.py               # Cấu hình đường dẫn (Poppler, Tesseract)
│   ├── pdf_metadata_gui.py     # Giao diện người dùng (GUI) chính (CustomTkinter)
│   ├── pdf_processor.py        # Xử lý PDF: đọc file, OCR, tách text, nhận diện in đậm/hoa
│   ├── metadata_extractor.py   # Core Logic: Trích xuất thông tin từ text (Regex/Heuristic)
│   ├── excel_exporter.py       # Xuất kết quả ra file Excel
│   ├── io_safety.py            # Tiện ích an toàn file I/O
│   ├── cli/                    # Giao diện dòng lệnh (CLI)
│   └── tools/                  # Các công cụ hỗ trợ (tải dependencies, chẩn đoán)
├── tools/                      # Các script tiện ích bên ngoài
│   ├── run_single.py           # Chạy test 1 file
│   └── setup.bat               # Script cài đặt môi trường
└── samples/                    # Thư mục chứa file PDF mẫu để test
```

## 3. Các Module Chính

### 3.1. Giao Diện (GUI)
*   **File:** `src/pdf_metadata_gui.py`
*   **Công nghệ:** `customtkinter` (Modern UI wrapper cho Tkinter).
*   **Chức năng:**
    *   Cho phép người dùng chọn File hoặc Thư mục PDF.
    *   Hiển thị tiến trình xử lý (Progress bar) và trạng thái (Live Data).
    *   Điều phối luồng xử lý đa luồng (`threading`) để không làm đơ giao diện.

### 3.2. Bộ Xử Lý PDF (PDF Processor)
*   **File:** `src/pdf_processor.py`
*   **Thư viện:** `PyPDF2`, `pdf2image`, `pytesseract`, `pdfplumber` (tùy chọn).
*   **Chức năng:**
    *   **Native Extraction:** Dùng `PyPDF2` để lấy text từ PDF gốc.
    *   **OCR Fallback:** Nếu không có text, dùng `pdf2image` chuyển trang thành ảnh -> `pytesseract` để nhận diện chữ.
    *   **Style Extraction:** Dùng `pdfplumber` để tìm các dòng **In Đậm** hoặc **IN HOA** (hỗ trợ tăng độ chính xác trích xuất metadata).
    *   **Caching:** Lưu kết quả OCR vào bộ nhớ đệm để tăng tốc độ khi chạy lại.

### 3.3. Bộ Trích Xuất Metadata (Extractor Logic)
*   **File:** `src/metadata_extractor.py`
*   **Phương pháp:** Regular Expressions (Regex) & Rules-based Heuristics.
*   **Chức năng:** Phân tích văn bản thô (raw text) để lấy các trường:
    *   **Cơ quan ban hành:** Tìm kiếm theo từ khóa ("UBND", "BỘ..."), ưu tiên dòng in hoa/đậm.
    *   **Số & Ký hiệu:** Regex tìm dòng bắt đầu bằng "Số:".
    *   **Ngày tháng:** Regex tìm định dạng ngày tháng tiếng Việt.
    *   **Loại văn bản:** So khớp với danh sách từ khóa (Quyết định, Tờ trình...).
    *   **Trích yếu (Summary):** Tìm đoạn văn bản mô tả nội dung (thường in đậm dưới loại văn bản).

### 3.4. Xuất Dữ Liệu (Exporter)
*   **File:** `src/excel_exporter.py`
*   **Thư viện:** `pandas`, `openpyxl`.
*   **Chức năng:**
    *   Tổng hợp danh sách metadata.
    *   Ghi ra file Excel (.xlsx).
    *   Tạo Hyperlink trỏ về file PDF gốc.

## 4. Mô Hình Luồng Dữ Liệu (Data Flow)

1.  **Input:** Người dùng chọn File/Folder PDF từ GUI.
2.  **Preprocessing (`PDFProcessor`):**
    *   File PDF -> `Extract Text` (Native/OCR) -> Raw Text.
    *   File PDF -> `Extract Styles` -> Map các dòng Bold/Uppercase.
3.  **Processing (`MetadataExtractor`):**
    *   Raw Text + Style Map -> `Extract Fields` -> Dictionary Metadata (Số, Ngày, Trích yếu...).
4.  **Output:**
    *   Dictionary Metadata -> `ExcelExporter` -> File Excel (.xlsx).

## 5. Yêu Cầu Hệ Thống (Dependencies)
*   **Python:** 3.8+
*   **Thư viện Python:**
    *   `customtkinter` (GUI)
    *   `PyPDF2`, `pdfplumber` (PDF Text/Structure)
    *   `pdf2image`, `pytesseract` (OCR)
    *   `pandas`, `openpyxl` (Excel)
    *   `Pillow` (Image Processing)
*   **Phần mềm ngoài (External Tools):**
    *   **Poppler:** Để `pdf2image` render PDF thành ảnh.
    *   **Tesseract-OCR:** Engine nhận diện quang học (cần cài gói ngôn ngữ tiếng Việt `vie`).
