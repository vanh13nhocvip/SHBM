import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

def create_shortcut(target_path, shortcut_path, description="SHBM"):
    """Tạo shortcut cho ứng dụng."""
    try:
        import winshell
        from win32com.client import Dispatch

        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.Description = description
        shortcut.IconLocation = target_path
        shortcut.save()
        return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False

class InstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SHBM - Bộ cài đặt tự động")
        self.root.geometry("500x300")
        
        # Determine internal paths
        if getattr(sys, 'frozen', False):
            self.base_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(__file__)
            
        self.app_files_source = os.path.join(self.base_dir, "SHBM_App")
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        tk.Label(self.root, text="Chào mừng bạn đến với bộ cài đặt SHBM", font=("Arial", 14, "bold"), pady=10).pack()
        
        # Path selection
        tk.Label(self.root, text="Chọn thư mục cài đặt:", anchor="w", padx=20).pack(fill="x")
        
        path_frame = tk.Frame(self.root, padx=20)
        path_frame.pack(fill="x")
        
        self.install_path_var = tk.StringVar(value=r"C:\SHBM_App")
        tk.Entry(path_frame, textvariable=self.install_path_var).pack(side="left", fill="x", expand=True)
        tk.Button(path_frame, text="Chọn...", command=self.browse_path).pack(side="right", padx=5)
        
        # Options
        self.create_shortcut_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.root, text="Tạo shortcut trên màn hình Desktop", variable=self.create_shortcut_var, pady=10).pack()
        
        # Progress
        self.status_var = tk.StringVar(value="Sẵn sàng cài đặt.")
        tk.Label(self.root, textvariable=self.status_var, pady=10).pack()
        
        # Install Button
        self.install_btn = tk.Button(self.root, text="Bắt đầu cài đặt", command=self.start_install, bg="green", fg="white", font=("Arial", 10, "bold"), padx=20)
        self.install_btn.pack()
        
    def browse_path(self):
        path = filedialog.askdirectory(initialdir="C:\\", title="Chọn thư mục cài đặt")
        if path:
            self.install_path_var.set(os.path.join(path, "SHBM_App"))
            
    def start_install(self):
        self.install_btn.config(state="disabled")
        self.status_var.set("Đang cài đặt... vui lòng đợi.")
        threading.Thread(target=self.install_logic).start()
        
    def install_logic(self):
        dest = self.install_path_var.get()
        try:
            # 1. Create directory
            if not os.path.exists(dest):
                os.makedirs(dest)
            
            # 2. Copy files
            # If we are running as a bundle, we copy everything from SHBM_App directory within MEIPASS
            if not os.path.exists(self.app_files_source):
                # Fallback for dev environment or mismatch
                messagebox.showerror("Lỗi", f"Không tìm thấy dữ liệu nguồn tại {self.app_files_source}")
                self.status_var.set("Cài đặt thất bại.")
                self.install_btn.config(state="normal")
                return

            # Copy contents of self.app_files_source to dest
            for item in os.listdir(self.app_files_source):
                s = os.path.join(self.app_files_source, item)
                d = os.path.join(dest, item)
                if os.path.isdir(s):
                    if os.path.exists(d): shutil.rmtree(d)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
                    
            # 3. Create shortcut
            if self.create_shortcut_var.get():
                exe_path = os.path.join(dest, "SHBM_Portable.exe") # Assuming this exists in bundle
                if not os.path.exists(exe_path):
                    # Guess name
                    for f in os.listdir(dest):
                        if f.endswith(".exe"):
                            exe_path = os.path.join(dest, f)
                            break
                
                if os.path.exists(exe_path):
                    desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
                    shortcut_name = "SHBM.lnk"
                    create_shortcut(exe_path, os.path.join(desktop, shortcut_name))
            
            messagebox.showinfo("Thành công", f"Cài đặt hoàn tất tại: {dest}")
            self.status_var.set("Cài đặt thành công!")
            self.root.quit()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {str(e)}")
            self.status_var.set("Lỗi trong quá trình cài đặt.")
            self.install_btn.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = InstallerGUI(root)
    root.mainloop()
