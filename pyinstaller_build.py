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
        "--name=SHBM",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]

    # Add data files
    # Format: --add-data "source;destination" (Windows uses ;)
    datas = [
        (os.path.join("src", "resources"), os.path.join("src", "resources")),
        (os.path.join(ctk_path, "gui"), os.path.join("customtkinter", "gui")),
        (os.path.join(ctk_path, "assets"), os.path.join("customtkinter", "assets")),
    ]

    for src, dst in datas:
        if os.path.exists(src):
            params.append(f'--add-data={src}{os.pathsep}{dst}')
            print(f"Added data: {src} -> {dst}")
        else:
            print(f"Warning: Source path not found: {src}")

    # Main entry point
    params.append(os.path.join("src", "__main__.py"))

    print("Running PyInstaller command...")
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
    source_exe = os.path.join("dist", "SHBM.exe")
    
    if os.path.exists(source_exe):
        try:
            if not os.path.exists(target_h):
                os.makedirs(target_h)
            shutil.copy2(source_exe, os.path.join(target_h, "SHBM.exe"))
            print(f"Copied successfully to {target_h}\SHBM.exe")
        except Exception as e:
            print(f"Error copying to H:\: {e}")
    else:
        print(f"Error: Could not find built executable at {source_exe}")

if __name__ == "__main__":
    main()
