import os
import subprocess
import shutil
import sys

def run_cmd(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    return True

def main():
    base_dir = os.getcwd()
    dist_dir = os.path.join(base_dir, "dist")
    build_dir = os.path.join(base_dir, "build")
    
    # 1. Build the Main App (onedir) first
    print("--- 1. Building Main App (onedir) ---")
    app_build_cmd = [
        "pyinstaller",
        "--name=SHBM_App",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--add-data", f"src/resources{os.pathsep}src/resources",
        "--add-data", f"src/tools/deps{os.pathsep}src/tools/deps",
        "--hidden-import", "PIL._tkinter_finder",
        "src/__main__.py"
    ]
    if not run_cmd(app_build_cmd): return

    # 2. Build the Installer (onefile) that bundles the onedir build
    print("\n--- 2. Building Professional Installer (onefile) ---")
    installer_script = os.path.join("src", "tools", "installer.py")
    
    # Ensure dependencies for shortcut creation are available
    subprocess.run([sys.executable, "-m", "pip", "install", "winshell", "pywin32"])

    setup_build_cmd = [
        "pyinstaller",
        "--name=Setup_SHBM",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--add-data", f"dist/SHBM_App{os.pathsep}SHBM_App",
        "--hidden-import", "winshell",
        "--hidden-import", "win32com.client",
        installer_script
    ]
    if not run_cmd(setup_build_cmd): return

    print("\n--- Build Complete! ---")
    print(f"Professional Installer ready at: {os.path.join(dist_dir, 'Setup_SHBM.exe')}")

if __name__ == "__main__":
    main()
