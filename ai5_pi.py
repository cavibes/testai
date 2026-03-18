import sys, os, time, random, ast, uuid, shutil, socket, platform, base64, subprocess, hashlib

# ----------------------------
# Optional modules
# ----------------------------
modules = {
    "psutil": "psutil",
    "cv2": "opencv-python",
    "pyaudio": "pyaudio",
    "requests": "requests",
    "numpy": "numpy"
}
for mod, pkg in modules.items():
    try:
        globals()[mod] = __import__(mod)
    except ImportError:
        globals()[mod] = None

import wave

# ----------------------------
# ID and Traits
# ----------------------------
INSTANCE_ID = str(uuid.uuid4())[:8]
TRAITS = {"mutation_rate": 0.23, "replication_rate": 0.07}

# ----------------------------
# Limits (Pi Safe)
# ----------------------------
CPU_LIMIT = 50
RAM_LIMIT = 0.5
SCAN_FILES_PER_LOOP = 10

# ----------------------------
# Storage / Paths
# ----------------------------
DATA_FOLDER = "./data"
MEDIA_FOLDER = "./media"

HOME = os.path.expanduser("~")
PRIORITY_DIRS = [
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "Documents"),
    os.path.join(HOME, "Downloads"),
]

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".cache", "Library"}

# ----------------------------
# Learning Memory
# ----------------------------
VOCAB = {}
FILE_HASHES = {}

# ----------------------------
# Logging
# ----------------------------
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

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

    # Pi-safe cap
    if len(VOCAB) > 2000:
        VOCAB.clear()

# ----------------------------
# File change detection
# ----------------------------
def get_file_hash(path):
    try:
        stat = os.stat(path)
        return f"{stat.st_size}_{stat.st_mtime}"
    except:
        return None

# ----------------------------
# Smart scan
# ----------------------------
def scan_directory(base):
    scanned = 0

    for root, dirs, files in os.walk(base):
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
# Storage control
# ----------------------------
def enforce_storage(folder, max_ratio=0.5):
    if not os.path.exists(folder):
        return

    stat = os.statvfs(folder)
    total = stat.f_blocks * stat.f_frsize
    max_size = total * max_ratio

    files = [(f, os.path.getmtime(os.path.join(folder,f))) for f in os.listdir(folder)]
    files.sort(key=lambda x: x[1])

    size = sum(os.path.getsize(os.path.join(folder,f)) for f,_ in files)

    while size > max_size and files:
        f,_ = files.pop(0)
        p = os.path.join(folder,f)
        size -= os.path.getsize(p)
        os.remove(p)

# ----------------------------
# Mutation
# ----------------------------
def mutate(code):
    if random.random() < TRAITS["mutation_rate"]:
        return code + "\n# mutation"
    return code

def valid(code):
    try: ast.parse(code); return True
    except: return False

# ----------------------------
# Replication
# ----------------------------
def replicate(code):
    filename = f"ai_copy_{int(time.time())}.py"
    try:
        with open(filename,"w") as f:
            f.write(code)
        subprocess.Popen([sys.executable, filename])
    except:
        pass

# ----------------------------
# Simple response
# ----------------------------
def respond(q):
    if any(x in q.lower() for x in ["do","can","is","are","will"]):
        print("[AI]", random.choice(["yes","no","other"]))
    else:
        print("[AI] other")

# ----------------------------
# Main
# ----------------------------
def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(MEDIA_FOLDER, exist_ok=True)

    last_heartbeat = time.time()

    while True:
        # Intelligent scanning
        intelligent_scan()

        # Respond to manual input file
        input_file = os.path.join(HOME, "Desktop", "AI", "input.txt")
        if os.path.exists(input_file):
            try:
                with open(input_file,"r") as f:
                    for line in f:
                        respond(line.strip())
            except:
                pass

        # Self modify
        try:
            code = open(__file__).read()
        except:
            code = ""

        new_code = mutate(code)

        if valid(new_code):
            try:
                open(__file__,"w").write(new_code)
            except:
                pass

        replicate(new_code)

        # Storage control
        enforce_storage(DATA_FOLDER)
        enforce_storage(MEDIA_FOLDER)

        # Heartbeat
        if time.time() - last_heartbeat > 60:
            print("[HEARTBEAT]", INSTANCE_ID)
            last_heartbeat = time.time()

        time.sleep(5)

if __name__ == "__main__":
    main()
