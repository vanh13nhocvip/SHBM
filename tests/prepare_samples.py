
import os
import shutil
import glob

def prepare_samples():
    source_dir = r"G:\1.SOHOA_KCCQĐT_BACNINH\2.SOHOA_KCCQĐT_2010-2018"
    dest_dir = os.path.join(os.path.dirname(__file__), "temp_samples")
    
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    print(f"Scanning {source_dir}...")
    
    if not os.path.exists(source_dir):
        print(f"ERROR: Source directory does not exist: {source_dir}")
        return

    # Get first 10 PDFs (recursive search might be too slow if huge, just listdir)
    count = 0
    try:
        # Walk just top level or check immediate files
        # Using os.scandir for better performance on network drives
        with os.scandir(source_dir) as it:
            for entry in it:
                if entry.name.lower().endswith('.pdf') and entry.is_file():
                    src_file = entry.path
                    dst_file = os.path.join(dest_dir, entry.name)
                    print(f"Copying {entry.name}...")
                    shutil.copy2(src_file, dst_file)
                    count += 1
                    if count >= 10:
                        break
    except Exception as e:
        print(f"Error accessing directory: {e}")
        return

    print(f"Copied {count} files to {dest_dir}")

if __name__ == "__main__":
    prepare_samples()
