import sys, os, time, random, uuid, shutil, subprocess, hashlib, threading

# ----------------------------
# Terminal Colors
# ----------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# ----------------------------
# System Detection
# ----------------------------
IS_PI = False
try:
    with open("/proc/cpuinfo", "r") as f:
        if "Raspberry Pi" in f.read():
            IS_PI = True
except:
    pass

# ----------------------------
# Limits (Adaptive)
# ----------------------------
if IS_PI:
    CPU_LIMIT = 50
    RAM_LIMIT = 0.5
    MAX_STORAGE_BYTES = 200 * 1024 * 1024
    SCAN_FILES_PER_LOOP = 10
else:
    CPU_LIMIT = 85
    RAM_LIMIT = 0.85
    MAX_STORAGE_BYTES = 500 * 1024 * 1024
    SCAN_FILES_PER_LOOP = 50

# ----------------------------
# Globals
# ----------------------------
INSTANCE_ID = str(uuid.uuid4())[:8]
modules = {}
VOCAB = {}
FILE_HASHES = {}

DATA_FOLDER = "./data"
MEDIA_FOLDER = "./media"

HOME = os.path.expanduser("~")
PRIORITY_DIRS = [
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "Documents"),
    os.path.join(HOME, "Downloads"),
]

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "Library", ".cache"}

# ----------------------------
# User Permission
# ----------------------------
def ask_user_permission(msg):
    try:
        return input(f"{YELLOW}[AI REQUEST]{RESET} {msg} (yes/no): ").strip().lower() == "yes"
    except:
        return False

# ----------------------------
# Dependency Decision
# ----------------------------
def dependency_needed(name):
    if IS_PI and name in ["cv2", "pyaudio"]:
        return False
    return True

# ----------------------------
# Safe Install
# ----------------------------
def safe_install(package, import_name=None):
    name = import_name if import_name else package

    if not dependency_needed(name):
        print(f"{YELLOW}[SKIP]{RESET} {name}")
        return None

    try:
        __import__(name)
        print(f"{GREEN}[OK]{RESET} {name}")
        return __import__(name)
    except:
        print(f"{YELLOW}[MISSING]{RESET} {name}")

        if not ask_user_permission(f"Install {package}?"):
            print(f"{RED}[DENIED]{RESET} {package}")
            return None

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"{GREEN}[INSTALLED]{RESET} {package}")
            return __import__(name)
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} {package}: {e}")
            return None

# ----------------------------
# PyAudio Setup (Safe)
# ----------------------------
def setup_pyaudio():
    try:
        import pyaudio
        print(f"{GREEN}[OK]{RESET} pyaudio")
        return pyaudio
    except:
        print(f"{YELLOW}[INFO]{RESET} PyAudio needs PortAudio")

        if not ask_user_permission("Install PyAudio dependencies?"):
            return None

        if shutil.which("brew") is None:
            print(f"{RED}[MISSING]{RESET} Homebrew")
            print("Run manually:")
            print('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
            return None

        try:
            subprocess.run(["brew", "install", "portaudio"], check=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyaudio"])
            import pyaudio
            print(f"{GREEN}[INSTALLED]{RESET} pyaudio")
            return pyaudio
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} pyaudio: {e}")
            return None

# ----------------------------
# Initialize Dependencies
# ----------------------------
def initialize_dependencies():
    global modules

    print(f"{YELLOW}[AI] Checking dependencies...{RESET}")

    modules["cv2"] = safe_install("opencv-python", "cv2")
    modules["psutil"] = safe_install("psutil")
    modules["numpy"] = safe_install("numpy")
    modules["pyaudio"] = setup_pyaudio()

    print(f"\n{YELLOW}[AI] Features:{RESET}")
    for k, v in modules.items():
        print(f"  {k}: {(GREEN+'ENABLED'+RESET) if v else (RED+'DISABLED'+RESET)}")

# ----------------------------
# Learning
# ----------------------------
def learn_text(data):
    h = hashlib.sha256(data.encode()).hexdigest()
    if h in FILE_HASHES:
        return
    FILE_HASHES[h] = True

    for w in data.split():
        VOCAB[w] = VOCAB.get(w, 0) + 1

    if IS_PI and len(VOCAB) > 2000:
        VOCAB.clear()

# ----------------------------
# File Hashing
# ----------------------------
def get_file_hash(path):
    try:
        stat = os.stat(path)
        return f"{stat.st_size}_{stat.st_mtime}"
    except:
        return None

# ----------------------------
# Smart Scan
# ----------------------------
def scan_directory(base_path):
    scanned = 0

    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in files:
            if scanned >= SCAN_FILES_PER_LOOP:
                return

            path = os.path.join(root, f)

            try:
                h = get_file_hash(path)
                if not h or FILE_HASHES.get(path) == h:
                    continue

                FILE_HASHES[path] = h

                if f.endswith(".txt"):
                    with open(path, "r", errors="ignore") as file:
                        learn_text(file.read())

                scanned += 1
            except:
                continue

def intelligent_scan():
    for folder in PRIORITY_DIRS:
        if os.path.exists(folder):
            scan_directory(folder)

    scan_directory(HOME)

# ----------------------------
# Camera
# ----------------------------
def capture_camera():
    if modules.get("cv2") is None:
        return
    try:
        cap = modules["cv2"].VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if ret:
            path = os.path.join(MEDIA_FOLDER, f"cam_{time.time()}.png")
            modules["cv2"].imwrite(path, frame)
    except:
        modules["cv2"] = None
        print(f"{RED}[DISABLED]{RESET} Camera")

# ----------------------------
# Storage Control
# ----------------------------
def enforce_storage(folder):
    if not os.path.exists(folder):
        return

    files = [(f, os.path.getmtime(os.path.join(folder,f))) for f in os.listdir(folder)]
    files.sort(key=lambda x: x[1])

    size = sum(os.path.getsize(os.path.join(folder,f)) for f,_ in files)

    while size > MAX_STORAGE_BYTES and files:
        f,_ = files.pop(0)
        p = os.path.join(folder,f)
        size -= os.path.getsize(p)
        os.remove(p)

# ----------------------------
# AI Response
# ----------------------------
def simple_respond(q):
    if any(x in q.lower() for x in ["do","can","is","are","will"]):
        print(f"{GREEN}[AI]{RESET} {random.choice(['yes','no','other'])}")
    else:
        print(f"{GREEN}[AI]{RESET} other")

def question_listener():
    while True:
        try:
            q = input(f"{YELLOW}[ASK]{RESET} ")
            simple_respond(q)
        except:
            pass

# ----------------------------
# Main
# ----------------------------
def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(MEDIA_FOLDER, exist_ok=True)

    initialize_dependencies()

    threading.Thread(target=question_listener, daemon=True).start()

    last_heartbeat = time.time()

    while True:
        intelligent_scan()
        capture_camera()

        enforce_storage(DATA_FOLDER)
        enforce_storage(MEDIA_FOLDER)

        if time.time() - last_heartbeat > 60:
            print(f"{GREEN}[HEARTBEAT]{RESET} {INSTANCE_ID}")
            last_heartbeat = time.time()

        time.sleep(5 if IS_PI else 2)

if __name__ == "__main__":
    main()
