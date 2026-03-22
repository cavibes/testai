import sys, os, time, hashlib, json, socket, threading, shutil, random, subprocess
import requests
import platform

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
flask = install_module("flask")  # ✅ FIXED

if flask:
    from flask import Flask, jsonify, request

tavily = install_module("tavily")    

# ----------------------------
# PATHS
# ----------------------------
HOME = os.path.expanduser("~/Desktop/AI")
DATA_FOLDER = os.path.join(HOME,"AI_data")
SYNC_FOLDER = os.path.join(HOME,"AI_sync")
CHUNKS_FOLDER = os.path.join(SYNC_FOLDER,"knowledge_chunks")
FILE_HASHES_FILE = os.path.join(SYNC_FOLDER,"file_hashes.json")
STOP_FLAG = os.path.join(SYNC_FOLDER,"STOP_ALL.flag")

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(SYNC_FOLDER, exist_ok=True)
os.makedirs(CHUNKS_FOLDER, exist_ok=True)

# ----------------------------
# MEMORY
# ----------------------------
BrainCore = {}
FILE_HASHES = {}
ACTION_LOG = []
PEERS = set()
DETECTED_HARDWARE = []

SEEN_SOURCES = set()

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
# UTIL
# ----------------------------
def atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp,"w") as f:
        json.dump(data,f)
    os.replace(tmp,path)

def save_file_hashes():
    atomic_write_json(FILE_HASHES_FILE, FILE_HASHES)

def load_file_hashes():
    global FILE_HASHES
    if os.path.exists(FILE_HASHES_FILE):
        try:
            FILE_HASHES = json.load(open(FILE_HASHES_FILE))
        except:
            FILE_HASHES = {}

def load_brain_chunks():
    BrainCore.clear()
    for f in os.listdir(CHUNKS_FOLDER):
        if f.endswith(".json"):
            try:
                data = json.load(open(os.path.join(CHUNKS_FOLDER,f)))
                for w in data.get("text","").split():
                    BrainCore[w] = BrainCore.get(w,0)+1
            except:
                continue

# ----------------------------
# LEARNING CORE
# ----------------------------
def learn_text_content(data, source="unknown"):
    # Normalize content (reduce duplicates)
    normalized = data.lower().strip()

    # Prevent re-learning same source content
    source_key = source + ":" + normalized[:200]

    if source_key in SEEN_SOURCES:
        ACTION_LOG.append(f"[Skip Duplicate] {source}")
        return False

    SEEN_SOURCES.add(source_key)

    # Hash AFTER normalization
    h = hashlib.sha256(normalized.encode()).hexdigest()
    if h in FILE_HASHES:
        return False
    FILE_HASHES[h] = True

    words = normalized.split()
    if len(words) < 50:
        return False

    for w in words:
        BrainCore[w] = BrainCore.get(w,0)+1

    chunk_file = os.path.join(CHUNKS_FOLDER, f"{h}.json")
    atomic_write_json(chunk_file, {"source": source, "text": data[:5000]})

    ACTION_LOG.append(f"Learned from {source}")
    return True

# ----------------------------
# INTERNET SOURCES
# ----------------------------
def fetch_wikipedia():
    try:
        topic = random.choice([
            "Artificial intelligence","Machine learning","Physics",
            "Programming","Robotics","Technology",
            "Computer hardware","Computer software","Operating systems",
            "Embedded systems","IoT devices"
        ])
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ','_')}"
        r = requests.get(url, timeout=5)
        text = ""
        if r.status_code == 200:
            try:
                data = r.json()
                text = data.get("extract","").strip()
                if text:
                    ACTION_LOG.append(f"[Wiki] {topic}")
            except Exception as e:
                ACTION_LOG.append(f"[Wiki] JSON parse failed: {e}")
        else:
            ACTION_LOG.append(f"[Wiki] Status {r.status_code} for {topic}")
        return text
    except Exception as e:
        ACTION_LOG.append(f"[Wiki] Request failed: {e}")
        return ""

def fetch_rss():
    try:
        url = "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
        r = requests.get(url, timeout=5)

        if r.status_code != 200:
            ACTION_LOG.append(f"[RSS] Failed {r.status_code}")
            return ""

        text = r.text
        items = []

        parts = text.split("<item>")
        for part in parts[1:6]:
            title = ""
            desc = ""

            if "<title>" in part:
                title = part.split("<title>")[1].split("</title>")[0]
            if "<description>" in part:
                desc = part.split("<description>")[1].split("</description>")[0]

            combined = f"{title}. {desc}".strip()
            if combined:
                items.append(combined)

        final = "\n".join(items)

        if final:
            ACTION_LOG.append(f"[RSS] {len(items)} articles")
        return final

    except Exception as e:
        ACTION_LOG.append(f"[RSS] Error {e}")
        return ""

def fetch_reddit():
    try:
        url = "https://www.reddit.com/r/technology/top.json?limit=5"
        headers = {"User-Agent": "AI-Learner"}
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()

        posts = []
        for p in data["data"]["children"]:
            posts.append(p["data"]["title"])

        ACTION_LOG.append(f"[Reddit] {len(posts)} posts")
        return "\n".join(posts)

    except Exception as e:
        ACTION_LOG.append(f"[Reddit] Error {e}")
        return ""

# ----------------------------
# INTERNET LEARNING
# ----------------------------
# ----------------------------
# ----------------------------
# INTERNET LEARNING (TAVILY + RSS + REDDIT)
# ----------------------------

import random
import hashlib
import requests
import threading
import time
import os
from tavily import TavilyClient

# ----------------------------
# Topics for internet learning
# ----------------------------
TOPICS = [
    "Artificial intelligence",
    "Machine learning",
    "Programming",
    "Robotics",
    "Technology",
    "Computer hardware",
    "Computer software",
    "Operating systems",
    "Embedded systems",
    "IoT devices"
]

# ----------------------------
# Initialize Tavily client
# ----------------------------
TAVILY_API_KEY = "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"  # <-- replace with your key (must be in quotes)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# ----------------------------
# Tavily fetch configuration
# ----------------------------
TAVILY_MODE = "test"  # "test" or "production"
CREDITS_PER_FETCH = 4       # average credits used per Tavily fetch
MONTHLY_CREDITS = 1000      # total free credits per month
SECONDS_PER_MONTH = 30*24*60*60  # 30-day month

if TAVILY_MODE == "production":
    tavily_interval = int((SECONDS_PER_MONTH / (MONTHLY_CREDITS / CREDITS_PER_FETCH)))
else:
    tavily_interval = 60  # 1 minute for test mode

# ----------------------------
# Core text learning function
# ----------------------------
def learn_text_directly(text, source):
    """Directly learn text by updating BrainCore and saving a chunk."""
    for w in text.split():
        BrainCore[w] = BrainCore.get(w, 0) + 1

    h = hashlib.sha256(text.encode()).hexdigest()
    chunk_file = os.path.join(CHUNKS_FOLDER, f"{h}.json")
    chunk_data = {"source": source, "text": text[:5000]}
    atomic_write_json(chunk_file, chunk_data)

# ----------------------------
# Fetch content from Tavily
# ----------------------------
def fetch_tavily(query):
    try:
        ACTION_LOG.append(f"[Tavily] Fetching topic: '{query}'")
        response = tavily_client.search(query)
        results = response.get("results", [])
        ACTION_LOG.append(f"[Tavily] Found {len(results)} results for '{query}'")

        for idx, item in enumerate(results):
            ACTION_LOG.append(f"[Tavily Raw {idx+1}] {item}")

            text = item.get("text") or item.get("summary") or item.get("snippet") or item.get("content") or ""
            if text:
                learn_text_directly(text, f"tavily:{query}")
                preview = text.replace("\n", " ")[:200]
                ACTION_LOG.append(f"[Preview Tavily {idx+1}] {preview}...")
            else:
                ACTION_LOG.append(f"[Tavily {idx+1}] Empty text")
        return bool(results)
    except Exception as e:
        ACTION_LOG.append(f"[Tavily Error] {e}")
        return False

# ----------------------------
# Fetch RSS content
# ----------------------------
def fetch_rss():
    try:
        url = "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
        r = requests.get(url, timeout=5)
        rss_text = ""
        if r.status_code == 200:
            items = []
            parts = r.text.split("<item>")
            for part in parts[1:6]:
                title, desc = "", ""
                if "<title>" in part:
                    title = part.split("<title>")[1].split("</title>")[0]
                if "<description>" in part:
                    desc = part.split("<description>")[1].split("</description>")[0]
                combined = f"{title}. {desc}".strip()
                if combined:
                    items.append(combined)
            rss_text = "\n".join(items)
            if rss_text:
                learn_text_directly(rss_text, "rss_feed")
                ACTION_LOG.append(f"[Preview RSS] {items[0][:200]}...")
        else:
            ACTION_LOG.append(f"[RSS Error] HTTP {r.status_code}")
    except Exception as e:
        ACTION_LOG.append(f"[RSS Error] {e}")

# ----------------------------
# Fetch Reddit content
# ----------------------------
def fetch_reddit():
    try:
        url = "https://www.reddit.com/r/technology/top.json?limit=5"
        headers = {"User-Agent": "AI-Learner"}
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        posts = []
        for p in data.get("data", {}).get("children", []):
            title = p["data"].get("title", "")
            if title:
                posts.append(title)
        if posts:
            learn_text_directly("\n".join(posts), "reddit")
            ACTION_LOG.append(f"[Preview Reddit] {posts[0][:200]}...")
        else:
            ACTION_LOG.append("[Reddit] No posts found")
    except Exception as e:
        ACTION_LOG.append(f"[Reddit Error] {e}")

# ----------------------------
# Main internet learning cycle
# ----------------------------
def learn_from_internet(last_tavily_time):
    now = time.time()
    # Tavily: only fetch if interval passed
    if now - last_tavily_time >= tavily_interval:
        for topic in TOPICS:
            fetch_tavily(topic)
        last_tavily_time = now

    # RSS and Reddit always fetch every loop
    fetch_rss()
    fetch_reddit()
    return last_tavily_time

# ----------------------------
# Background loop
# ----------------------------
def internet_loop():
    last_tavily_time = 0
    while True:
        try:
            last_tavily_time = learn_from_internet(last_tavily_time)
        except Exception as e:
            ACTION_LOG.append(f"[Internet Loop Error] {e}")
        time.sleep(60)  # general loop sleep for other feeds

# Start the background thread
threading.Thread(target=internet_loop, daemon=True).start()

# ----------------------------
# QUERY
# ----------------------------
def query_ai(text):
    words = text.lower().split()
    scores = {}

    for w in words:
        for v in BrainCore:
            if w in v or v in w:
                scores[v] = scores.get(v,0) + BrainCore.get(v,0)

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:20]
    return [w for w,_ in top] if top else ["No relevant knowledge"]

# ----------------------------
# PI CONNECTION
# ----------------------------
FLIPPER_ENDPOINT = "https://9816bca4-b2a2-4b58-bbf6-1bcc58bac1dd-00-2kdzodsijnbra.riker.replit.dev/api/pi/dashboard"

def query_pi():
    try:
        r = requests.get(FLIPPER_ENDPOINT, timeout=5)
        ACTION_LOG.append(f"[Pi] OK {r.status_code}")
    except Exception as e:
        ACTION_LOG.append(f"[Pi] Error {e}")

# ----------------------------
# FLASK DASHBOARD
# ----------------------------
if flask:
    app = Flask(__name__)
    port = 5001

    @app.route("/")
    def dashboard():
        ram, cpu = get_resources()
        return f"""
        <h1>AI Dashboard</h1>
        <p>Brain: {len(BrainCore)}</p>
        <p>RAM: {round(ram,3)}</p>
        <p>CPU: {round(cpu,3)}</p>

        <h2>Query</h2>
        <input id="q"><button onclick="ask()">Ask</button>
        <pre id="out"></pre>

        <script>
        function ask(){{
            fetch("/query", {{
                method:"POST",
                headers:{{"Content-Type":"application/json"}},
                body:JSON.stringify({{query:document.getElementById("q").value}})
            }})
            .then(r=>r.json())
            .then(d=>document.getElementById("out").innerText=d.result.join(", "))
        }}
        </script>

        <h2>Logs</h2>
        <pre>{chr(10).join(ACTION_LOG[-30:])}</pre>
        """

    @app.route("/query", methods=["POST"])
    def q():
        return jsonify({"result": query_ai(request.json.get("query",""))})

    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=False), daemon=True).start()

# ----------------------------
# MAIN LOOP
# ----------------------------
def main():
    load_file_hashes()

    while True:
        save_file_hashes()
        load_brain_chunks()
        query_pi()

        print("[Brain]", len(BrainCore))
        time.sleep(30)

if __name__ == "__main__":
    main()
