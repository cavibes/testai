import os
import platform
import random
import datetime

# Detect platform
OS_NAME = platform.system().lower()  # 'darwin', 'linux', 'windows'

# ----------------------------
# Memory Handling
# ----------------------------
def get_available_memory():
    if OS_NAME == "linux":
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) * 1024
        except Exception:
            pass
    elif OS_NAME == "darwin":
        try:
            import subprocess
            mem_bytes = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"]).strip())
            return mem_bytes
        except Exception:
            pass
    # fallback
    return 1_000_000_000  # assume 1GB safe

def get_dynamic_max_code_size(fraction=0.5):
    return int(get_available_memory() * fraction)

def get_dynamic_max_storage_size(fraction=0.5):
    return int(get_available_memory() * fraction)

def trim_code(new_code, max_size):
    code_bytes = new_code.encode('utf-8', errors='ignore')
    if len(code_bytes) > max_size:
        return code_bytes[-max_size:].decode('utf-8', errors='ignore')
    return new_code

# ----------------------------
# Desktop Path
# ----------------------------
def get_desktop_path():
    home = os.path.expanduser("~")
    if OS_NAME in ["darwin", "linux"]:
        return os.path.join(home, "Desktop")
    else:
        # fallback to home folder on unknown OS
        return home

def log_code_update():
    desktop = get_desktop_path()
    filename = "AI_Code_Update_Log.txt"
    file_path = os.path.join(desktop, filename)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, "a") as f:
        f.write(f"[{timestamp}] Code updated\n")

# ----------------------------
# Directories to scan
# ----------------------------
def get_default_directories():
    if OS_NAME == "linux":
        return [".", "/mnt", "/media"]
    elif OS_NAME == "darwin":
        return [".", "./data", "/Volumes"]
    else:  # fallback
        return ["."]