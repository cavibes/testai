import sys, os, time, ast, hashlib, json, socket, threading, shutil, random, wave, subprocess, re
import requests

# ----------------------------
# INSTALL MODULES
# ----------------------------
def install_module(mod_name, pip_name=None):
    if pip_name is None: pip_name = mod_name
    try:
        return __import__(mod_name)
    except:
        subprocess.run([sys.executable, "-m", "pip", "install", pip_name])
        try:
            return __import__(mod_name)
        except:
            return None

psutil = install_module("psutil")
numpy = install_module("numpy")
cv2 = install_module("cv2", "opencv-python-headless")
flask = install_module("flask")

if flask:
    from flask import Flask, jsonify, request

# ----------------------------
# PATHS
# ----------------------------
HOME = os.path.expanduser("~/Desktop/AI")
DATA_FOLDER = os.path.join(HOME,"AI_data")
SYNC_FOLDER = os.path.join(HOME,"AI_sync")
KNOWLEDGE_FILE = os.path.join(SYNC_FOLDER,"knowledge.json")
STOP_FLAG = os.path.join(SYNC_FOLDER,"STOP_ALL.flag")

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(SYNC_FOLDER, exist_ok=True)

# ----------------------------
# MEMORY
# ----------------------------
VOCAB = {}
FILE_HASHES = {}
ACTION_LOG = []
PEERS = set()

# ----------------------------
# RESOURCE CHECK
# ----------------------------
def get_resources():
    if not psutil:
        return 1.0, 0.0
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    return mem.available/mem.total, cpu/100

# ----------------------------
# LEARNING
# ----------------------------
def store_file(path):
    try:
        data = open(path,"rb").read()
        h = hashlib.sha256(data).hexdigest()[:12]
        dest = os.path.join(DATA_FOLDER,h)
        if not os.path.exists(dest):
            shutil.copy2(path,dest)
    except: pass

def learn_text_content(data, source="unknown"):
    h = hashlib.sha256(data.encode()).hexdigest()
    if h in FILE_HASHES:
        return False
    FILE_HASHES[h] = True

    words = data.split()
    if len(words) < 50:
        return False

    for w in words:
        VOCAB[w] = VOCAB.get(w,0)+1

    ACTION_LOG.append(f"Learned from {source}")
    return True

def learn_file(path):
    try:
        data = open(path,"r",errors="ignore").read()
        return learn_text_content(data, path)
    except:
        return False

# ----------------------------
# FILE SCANNING
# ----------------------------
SCAN_PATHS = [os.path.expanduser("~/"), "/", "/Applications", "/Users", "/Volumes"]

def scan_directory(base, max_seconds=5):
    start = time.time()
    changed = False
    for root, _, files in os.walk(base):
        for f in files:
            path = os.path.join(root,f)
            if learn_file(path):
                changed = True
            if time.time() - start > max_seconds:
                return changed
    return changed

def intelligent_scan():
    changed = False
    for base in SCAN_PATHS:
        if os.path.exists(base):
            try:
                if scan_directory(base):
                    changed = True
            except: pass
    return changed

# ----------------------------
# AGGRESSIVE INTERNET LEARNING
# ----------------------------
TOPICS = ["Artificial intelligence","Machine learning","Robotics",
          "Programming","Software engineering","Computer hardware",
          "Technology","Quantum computing","Data science","Neural networks"]

RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.theverge.com/rss/index.xml"
]

CHUNK_SIZE = 100  # words per chunk

def clean_text(raw):
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text, size=CHUNK_SIZE):
    words = text.split()
    for i in range(0, len(words), size):
        yield ' '.join(words[i:i+size])

def fetch_and_learn_wikipedia(topic):
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ','_')}"
        r = requests.get(url, timeout=5).json()
        extract = r.get("extract", "")
        if extract:
            extract = clean_text(extract)
            for chunk in chunk_text(extract):
                learn_text_content(chunk, f"wiki:{topic}")
    except:
        ACTION_LOG.append(f"Failed wiki:{topic}")

def fetch_and_learn_rss(url):
    try:
        r = requests.get(url, timeout=5).text
        clean = clean_text(r)
        for chunk in chunk_text(clean):
            learn_text_content(chunk, f"rss:{url}")
    except:
        ACTION_LOG.append(f"Failed rss:{url}")

def learn_from_internet_aggressive():
    # Prioritize AI, tech, software, hardware
    prioritized_topics = ["Artificial intelligence","Machine learning","Programming",
                          "Software engineering","Computer hardware","Technology"]
    topic = random.choice(prioritized_topics)
    fetch_and_learn_wikipedia(topic)
    feed = random.choice(RSS_FEEDS)
    fetch_and_learn_rss(feed)

# ----------------------------
# BACKGROUND INTERNET THREAD
# ----------------------------
def internet_loop():
    while True:
        try:
            learn_from_internet_aggressive()
        except: pass
        time.sleep(60)

threading.Thread(target=internet_loop, daemon=True).start()

# ----------------------------
# SAVE / LOAD
# ----------------------------
def save_knowledge():
    try:
        with open(KNOWLEDGE_FILE,"w") as f:
            json.dump({"vocab":VOCAB}, f)
    except: pass

def load_knowledge():
    try:
        if os.path.exists(KNOWLEDGE_FILE):
            data = json.load(open(KNOWLEDGE_FILE))
            VOCAB.update(data.get("vocab",{}))
    except: pass

# ----------------------------
# NETWORK (unchanged)
# ----------------------------
def network_sync():
    pass

# ----------------------------
# QUERY SYSTEM
# ----------------------------
def query_ai(text):
    words = text.lower().split()
    scores = {}
    for w in words:
        for v in VOCAB:
            if w in v or v in w:
                scores[v] = scores.get(v, 0) + VOCAB.get(v, 0)
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:20]
    if not top:
        return ["No relevant knowledge found"]
    return [w for w, _ in top]

# ----------------------------
# PI / FLIPPER DETECTION PIPELINE
# ----------------------------
PEER_PI = "192.168.1.50:6000"  # Example Pi IP

def query_pi_flipper():
    try:
        r = requests.get(f"http://{PEER_PI}/flipper_status", timeout=3).json()
        if r.get("flipper_connected"):
            ACTION_LOG.append("Flipper detected via Pi")
            VOCAB["flipper_detected"] = VOCAB.get("flipper_detected", 0) + 1
        else:
            ACTION_LOG.append("No Flipper detected on Pi")
    except:
        ACTION_LOG.append("Failed to reach Pi agent")

# ----------------------------
# FLASK DASHBOARD
# ----------------------------
if flask:
    app = Flask(__name__)
    flask_port = None

    def find_port():
        for port in range(5001,5100):
            try:
                s = socket.socket()
                s.bind(('', port))
                s.close()
                return port
            except:
                continue
        return 5001

    def stop_all_ai():
        open(STOP_FLAG,"w").close()
        ACTION_LOG.append("STOP_ALL triggered")

    @app.route("/stop_all", methods=["POST"])
    def stop_all():
        stop_all_ai()
        return jsonify({"status":"STOP_ALL triggered"})

    @app.route("/status")
    def status():
        ram, cpu = get_resources()
        return jsonify({
            "vocab": len(VOCAB),
            "peers": list(PEERS),
            "ram": ram,
            "cpu": cpu,
            "actions": ACTION_LOG[-10:]
        })

    @app.route("/query", methods=["POST"])
    def query():
        data = request.json
        text = data.get("query", "")
        result = query_ai(text)
        return jsonify({"result": result})

    @app.route("/")
    def dashboard():
        ram, cpu = get_resources()
        return f"""
        <html>
        <body style="font-family:Arial;padding:20px;">
        <h1>AI Dashboard</h1>

        <h2>Status</h2>
        <p><b>Vocab:</b> {len(VOCAB)}</p>
        <p><b>Peers:</b> {len(PEERS)}</p>
        <p><b>RAM:</b> {round(ram,3)}</p>
        <p><b>CPU:</b> {round(cpu,3)}</p>
        <p><b>Port:</b> {flask_port}</p>

        <h2>Controls</h2>
        <form method="post" action="/stop_all">
            <button style="background:red;color:white;padding:10px;">STOP ALL</button>
        </form>

        <h2>Query AI</h2>
        <input id="queryBox" style="width:300px;padding:8px;" placeholder="Ask something...">
        <button onclick="sendQuery()">Ask</button>

        <pre id="queryResult"></pre>

        <script>
        function sendQuery() {{
            let q = document.getElementById("queryBox").value;

            fetch("/query", {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{query: q}})
            }})
            .then(res => res.json())
            .then(data => {{
                document.getElementById("queryResult").innerText =
                    data.result.join(", ");
            }});
        }}
        </script>

        <h2>Recent Actions</h2>
        <pre>{chr(10).join(ACTION_LOG[-20:])}</pre>

        </body>
        </html>
        """

    def run_flask():
        global flask_port
        flask_port = find_port()
        print(f"[INFO] Dashboard: http://localhost:{flask_port}")
        app.run(host="0.0.0.0", port=flask_port, debug=False, use_reloader=False)

    threading.Thread(target=run_flask, daemon=True).start()

# ----------------------------
# MAIN LOOP
# ----------------------------
def main():
    last = time.time()
    last_pi_check = time.time()
    while True:
        load_knowledge()
        intelligent_scan()
        save_knowledge()

        # Heartbeat
        if time.time() - last > 30:
            print("[HEARTBEAT]", len(VOCAB))
            last = time.time()

        # Pi/Flipper polling every 60 seconds
        if time.time() - last_pi_check > 60:
            query_pi_flipper()
            last_pi_check = time.time()

        time.sleep(5)

if __name__ == "__main__":
    main()
