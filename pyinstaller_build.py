import os
import shutil
import customtkinter
import subprocess
import sys

def main():
    # Get customtkinter path
    try:
        ctk_path = os.path.dirname(customtkinter.__file__)
    except Exception as e:
        print(f"Error finding customtkinter: {e}")
        return

    print(f"CustomTkinter path: {ctk_path}")

    # Build command parts
    params = [
        "pyinstaller",
        "--name=SHBM_Portable",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]

    # Add data files
    # Format: --add-data "source;destination" (Windows uses ;)
    datas = [
        (os.path.join("src", "resources"), os.path.join("src", "resources")),
        (os.path.join("src", "tools", "deps"), os.path.join("src", "tools", "deps")),
        (os.path.join(ctk_path, "gui"), os.path.join("customtkinter", "gui")),
        (os.path.join(ctk_path, "assets"), os.path.join("customtkinter", "assets")),
    ]

    # Add extra hidden imports if needed
    params.extend([
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=customtkinter",
        "--hidden-import=PyPDF2",
        "--hidden-import=pdfplumber",
        "--hidden-import=pdf2image",
        "--hidden-import=pytesseract",
        "--hidden-import=pandas",
        "--hidden-import=openpyxl",
    ])

    # Main entry point
    params.append(os.path.join("src", "__main__.py"))

    print("Running PyInstaller command for Portable version...")
    print(" ".join(params))
    
    result = subprocess.run(params, capture_output=True, text=True)
    if result.returncode != 0:
        print("PyInstaller failed!")
        print(result.stdout)
        print(result.stderr)
        return

    print("Build successful!")

    # Copy to H:\
    target_h = r'H:\SHBM_Installer'
    source_exe = os.path.join("dist", "SHBM_Portable.exe")
    
    if os.path.exists(source_exe):
        try:
            if not os.path.exists(target_h):
                os.makedirs(target_h)
            shutil.copy2(source_exe, os.path.join(target_h, "SHBM_Portable.exe"))
            print(f"Copied successfully to {target_h}\SHBM_Portable.exe")
        except Exception as e:
            print(f"Error copying to H:\: {e}")
    else:
        print(f"Error: Could not find built executable at {source_exe}")

if __name__ == "__main__":
    main()
