
import openpyxl
import os

def check_results():
    file_path = "results.xlsx"
    if not os.path.exists(file_path):
        print("results.xlsx not found!")
        return

    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    
    # Headers are likely in row 1
    headers = [cell.value for cell in sheet[1]]
    print(f"Headers: {headers}")
    
    # Identify indices
    try:
        issuer_idx = headers.index("Cơ quan ban hành")
        doc_type_idx = headers.index("Thể loại văn bản")
        summary_idx = headers.index("Trích yếu nội dung văn bản")
        number_idx = headers.index("Số văn bản")
    except ValueError as e:
        print(f"Missing header: {e}")
        return

    issues_found = 0
    
    for row in sheet.iter_rows(min_row=2):
        issuer = row[issuer_idx].value
        doc_type = row[doc_type_idx].value
        summary = row[summary_idx].value
        number = row[number_idx].value
        
        # Check for noise
        if issuer and ("Se: BODY" in str(issuer) or "S6:" in str(issuer)):
            print(f"FAIL: Issuer matches noise: {issuer}")
            issues_found += 1
            
        if doc_type and ("S6" in str(doc_type) or "Se:" in str(doc_type)):
            print(f"FAIL: Doc Type matches noise: {doc_type}")
            issues_found += 1
            
        if summary and ("Se: BODY" in str(summary)):
             print(f"FAIL: Summary matches noise: {summary}")
             issues_found += 1
             
        # Also check for "S6" in other fields if suspected
        
    if issues_found == 0:
        print("PASS: No OCR noise (S6, Se: BODY) found in key columns.")
    else:
        print(f"FAIL: Found {issues_found} issues.")

if __name__ == "__main__":
    check_results()
