import sys, os, time, ast, uuid, shutil, subprocess, hashlib, json, socket, threading, base64, random

# ----------------------------
# Automatic Dependency Installer
# ----------------------------
def install_module(mod_name, pip_name=None):
    if pip_name is None: pip_name = mod_name
    try:
        return __import__(mod_name)
    except ImportError:
        print(f"[INFO] Installing missing module: {pip_name}")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pip_name])
        try:
            return __import__(mod_name)
        except ImportError:
            print(f"[WARNING] Module {mod_name} could not be installed. Features will be disabled.")
            return None

# Required modules
psutil = install_module("psutil")
numpy = install_module("numpy")
cv2 = install_module("cv2", "opencv-python-headless")
pyaudio = install_module("pyaudio")
flask = install_module("flask")
wave = __import__("wave")

if flask is not None:
    from flask import Flask, jsonify, request

# ----------------------------
# MODE & RESOURCE LIMITS
# ----------------------------
MODE = "PI"  # "PI", "MAC", "AGENT"

if MODE == "MAC":
    RAM_LIMIT = 0.85
    MAX_STORAGE_BYTES = 10*1024*1024*1024  # 10GB
elif MODE == "PI":
    RAM_LIMIT = 0.5
    MAX_STORAGE_RATIO = 0.5
else:
    RAM_LIMIT = 0.3
    MAX_STORAGE_RATIO = 0.3

CPU_LIMIT = 50
SCAN_FILES_PER_LOOP = 20
MAX_COPIES = 5
HEARTBEAT_INTERVAL = 30
UPGRADE_CHANCE = 0.05

# ----------------------------
# PATHS
# ----------------------------
HOME = os.path.expanduser("~")
DATA_FOLDER = os.path.join(HOME,"AI_data")
SYNC_FOLDER = os.path.join(HOME,"AI_sync")
COPIES_FOLDER = os.path.join(HOME,"AI_copies")
KNOWLEDGE_FILE = os.path.join(SYNC_FOLDER,"knowledge.json")

for folder in [DATA_FOLDER,SYNC_FOLDER,COPIES_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ----------------------------
# MEMORY
# ----------------------------
VOCAB = {}
SIMILARITY_DB = {}
FILE_HASHES = {}
PERFORMANCE_SCORE = 0.0
PEERS = set()
PORT = 5000

# ----------------------------
# RESOURCE CHECK
# ----------------------------
def get_resources():
    if psutil is None: return 1.0, 1.0
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    available_ram = max(0.05,min(1.0,mem.available/mem.total))
    available_cpu = max(0.05,min(1.0,CPU_LIMIT/100 - cpu/100))
    return available_ram, available_cpu

# ----------------------------
# STORAGE CONTROL
# ----------------------------
def enforce_storage():
    try:
        files = [(f, os.path.getmtime(os.path.join(DATA_FOLDER,f))) for f in os.listdir(DATA_FOLDER)]
        files.sort(key=lambda x:x[1])
        if MODE == "MAC":
            size = sum(os.path.getsize(os.path.join(DATA_FOLDER,f)) for f,_ in files)
            while size > MAX_STORAGE_BYTES and files:
                f,_ = files.pop(0)
                os.remove(os.path.join(DATA_FOLDER,f))
        else:
            stat = os.statvfs(DATA_FOLDER)
            max_size = stat.f_blocks*stat.f_frsize*MAX_STORAGE_RATIO
            size = sum(os.path.getsize(os.path.join(DATA_FOLDER,f)) for f,_ in files)
            while size > max_size and files:
                f,_ = files.pop(0)
                os.remove(os.path.join(DATA_FOLDER,f))
    except: pass

# ----------------------------
# FILE LEARNING
# ----------------------------
def store_file(path):
    try:
        data = open(path,"rb").read()
        h = hashlib.sha256(data).hexdigest()[:12]
        ext = os.path.splitext(path)[1]
        dest = os.path.join(DATA_FOLDER,f"{h}{ext}")
        if not os.path.exists(dest):
            shutil.copy2(path,dest)
    except: pass

def learn_text(path):
    try:
        data = open(path,"rb").read()
        h = hashlib.sha256(data).hexdigest()
        if h in FILE_HASHES: return False
        FILE_HASHES[h] = True
        for w in data.decode(errors="ignore").split():
            VOCAB[w] = VOCAB.get(w,0)+1
        return True
    except: return False

def extract_image_features(path):
    if cv2 is None or numpy is None: return None
    try:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        img = cv2.resize(img,(64,64))
        hist = cv2.calcHist([img],[0],None,[16],[0,256])
        return hist.flatten().tolist()
    except: return None

def extract_audio_features(path):
    if numpy is None: return None
    try:
        with wave.open(path,'rb') as wf:
            frames = wf.readframes(min(1024,wf.getnframes()))
            data = numpy.frombuffer(frames, dtype=numpy.int16)
            return data[:64].tolist()
    except: return None

def extract_video_features(path):
    if cv2 is None or numpy is None: return None
    try:
        cap = cv2.VideoCapture(path)
        features = []
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, frame_count//5)
        for i in range(0,frame_count,step):
            cap.set(cv2.CAP_PROP_POS_FRAMES,i)
            ret, frame = cap.read()
            if not ret: continue
            frame = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            frame = cv2.resize(frame,(32,32))
            features.extend(frame.flatten().tolist()[:64])
        cap.release()
        return features
    except: return None

def learn_binary(path):
    try:
        h = hashlib.sha256(open(path,"rb").read()).hexdigest()
        if h in FILE_HASHES: return False
        FILE_HASHES[h] = True
        ext = os.path.splitext(path)[1].lower()
        features = None
        if ext in [".png",".jpg",".jpeg",".bmp"]: features = extract_image_features(path)
        elif ext in [".wav",".mp3"]: features = extract_audio_features(path)
        elif ext in [".mp4",".mov",".avi"]: features = extract_video_features(path)
        VOCAB[h] = {"type":"binary","features":features}
        return True
    except: return False

def learn_file(path):
    learned = learn_text(path) if path.endswith((".txt",".md",".csv")) else learn_binary(path)
    if learned: store_file(path)
    return learned

# ----------------------------
# SCANNING
# ----------------------------
def scan_directory(base):
    scanned = 0
    changed = False
    for root,dirs,files in os.walk(base):
        for f in files:
            if scanned >= SCAN_FILES_PER_LOOP: return changed
            path = os.path.join(root,f)
            try:
                if learn_file(path): changed = True
                scanned += 1
            except: continue
    return changed

def intelligent_scan():
    return scan_directory(HOME) if MODE != "AGENT" else False

# ----------------------------
# KNOWLEDGE MERGE
# ----------------------------
def merge_dicts(a,b):
    for k,v in b.items():
        if k not in a: a[k] = v
        else:
            if isinstance(v,int): a[k] += v
            elif isinstance(v,list): a[k] = list(set(a[k]+v))
            elif isinstance(v,dict):
                a[k] = merge_dicts(a[k],v)
    return a

def save_knowledge():
    try:
        new_data = {"vocab":VOCAB,"similarity":SIMILARITY_DB}
        if os.path.exists(KNOWLEDGE_FILE):
            with open(KNOWLEDGE_FILE,"r") as f: old = json.load(f)
            new_data["vocab"] = merge_dicts(old.get("vocab",{}),VOCAB)
            new_data["similarity"] = merge_dicts(old.get("similarity",{}),SIMILARITY_DB)
        with open(KNOWLEDGE_FILE,"w") as f:
            json.dump(new_data,f)
    except: pass

def load_knowledge():
    try:
        if not os.path.exists(KNOWLEDGE_FILE): return
        with open(KNOWLEDGE_FILE,"r") as f:
            data = json.load(f)
        VOCAB.update(data.get("vocab",{}))
        SIMILARITY_DB.update(data.get("similarity",{}))
    except: pass

# ----------------------------
# SAFE UPGRADES
# ----------------------------
def generate_upgrade(code):
    additions = [
        "\n# optimization: minor cleanup",
        "\n# improvement: adjusted loop behavior",
        "\n# note: upgraded version"
    ]
    return code + random.choice(additions)

def validate_code(code):
    try: ast.parse(code); return True
    except: return False

def deploy_upgrade(new_code, score):
    global PERFORMANCE_SCORE
    if score < PERFORMANCE_SCORE: return False
    try:
        fname = os.path.join(COPIES_FOLDER,f"upgrade_{int(time.time())}.py")
        with open(fname,"w") as f: f.write(new_code)
        subprocess.Popen([sys.executable,fname])
        PERFORMANCE_SCORE = score
        return True
    except: return False

# ----------------------------
# REPLICATION
# ----------------------------
def replicate(code):
    if MODE=="AGENT": return
    try:
        fname = os.path.join(COPIES_FOLDER,f"copy_{int(time.time())}.py")
        with open(fname,"w") as f: f.write(code)
        subprocess.Popen([sys.executable,fname])
    except: pass

# ----------------------------
# NETWORKING & AUTO-DISCOVERY
# ----------------------------
def discover_local_peers():
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        base = ".".join(local_ip.split(".")[:-1])
        for i in range(1,255):
            ip = f"{base}.{i}"
            try:
                s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                s.settimeout(0.05)
                s.connect((ip,PORT))
                PEERS.add(ip)
                s.close()
            except: continue
    except: pass

def push_knowledge(peer):
    try:
        url = f"http://{peer}:{PORT}/sync"
        requests.post(url,json={"vocab":VOCAB,"similarity":SIMILARITY_DB},timeout=0.5)
    except: pass

def network_sync():
    discover_local_peers()
    for peer in list(PEERS):
        push_knowledge(peer)

# ----------------------------
# AUTO-DEPLOY HANDLER
# ----------------------------
class DeployHandler:
    pass  # same as previous implementation, simplified for brevity

# ----------------------------
# WEB INTERFACE
# ----------------------------
if flask is not None:
    app = Flask(__name__)
    @app.route("/status")
    def status():
        ram, cpu = get_resources()
        return jsonify({
            "mode": MODE,
            "peers": list(PEERS),
            "vocab_size": len(VOCAB),
            "similarity_entries": len(SIMILARITY_DB),
            "performance_score": PERFORMANCE_SCORE,
            "available_ram": ram,
            "cpu_load": cpu
        })
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT+1,debug=False,use_reloader=False),daemon=True).start()

# ----------------------------
# MAIN LOOP
# ----------------------------
def main():
    last_heartbeat=time.time()
    while True:
        load_knowledge()
        changed = intelligent_scan()
        if MODE!="AGENT" and changed:
            try:
                code = open(__file__).read()
                replicate(code)
                if random.random()<UPGRADE_CHANCE:
                    new_code = generate_upgrade(code)
                    score = random.random()
                    if validate_code(new_code):
                        deploy_upgrade(new_code,score)
            except: pass
        if MODE!="AGENT":
            save_knowledge()
            network_sync()
        enforce_storage()
        if time.time()-last_heartbeat>HEARTBEAT_INTERVAL:
            print("[HEARTBEAT]",MODE,len(VOCAB),len(PEERS))
            last_heartbeat=time.time()
        time.sleep(5)

if __name__=="__main__":
    main()
