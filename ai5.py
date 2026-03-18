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
        print(f"[WARNING] Module '{pkg}' not available. Skipping related functionality.")
        globals()[mod] = None

import wave

# ----------------------------
# ID and Traits
# ----------------------------
INSTANCE_ID = str(uuid.uuid4())[:8]
TRAITS = {"mutation_rate": 0.23, "replication_rate": 0.07}

# ----------------------------
# Limits
# ----------------------------
MAX_CODE_SIZE = 5*1024*1024
LOOP_DELAY_BASE = 5
MAX_PARALLEL_INSTANCES_BASE = 10
CPU_LIMIT = 50
RAM_LIMIT = 0.5
REMOTE_USER = "pi"
REMOTE_PATH = "~/Desktop/AI/"

# ----------------------------
# Chunk size for media ingestion
# ----------------------------
if platform.system() == "Linux" and "arm" in platform.machine():
    CHUNK_SIZE_MAX = 10 * 1024 * 1024
else:
    CHUNK_SIZE_MAX = 50 * 1024 * 1024

DATA_FOLDER = "./data"
MEDIA_FOLDER = "./media"
IMAGE_EXT = (".png",".jpg",".jpeg",".bmp")
VIDEO_EXT = (".mp4",".avi",".mov")
AUDIO_EXT = (".mp3",".wav",".flac")
DATA_BUFFER = []

# ----------------------------
# Learning and duplicate tracking
# ----------------------------
VOCAB = {}
TEXT_HASHES = set()
MAX_TEXT_HASHES = 5000

# ----------------------------
# Folders
# ----------------------------
def setup_folders():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    desktop_ai = os.path.join(os.path.expanduser("~"), "Desktop", "AI")
    os.makedirs(desktop_ai, exist_ok=True)

# ----------------------------
# Logging
# ----------------------------
def get_path(name):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    folder = os.path.join(desktop, "AI")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)

def log_event(event, details):
    try:
        with open(get_path("AI_Update_Log.txt"), "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event} | {details}\n")
    except: pass

def log_evolution(event, details):
    try:
        with open(get_path("AI_Evolution_Log.txt"), "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event} | {details}\n")
    except: pass

# ----------------------------
# Communication logging (separate)
# ----------------------------
def get_comm_path():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    folder = os.path.join(desktop, "AI")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "AI_Communication_Log.txt")

def log_communication(response, input_text=None):
    try:
        with open(get_comm_path(), "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] INPUT: {input_text or ''} | RESPONSE: {response}\n")
    except: pass

# ----------------------------
# Simple response
# ----------------------------
def simple_respond(input_text=None, event_message=None):
    if event_message:
        choice = event_message
    elif input_text:
        text = input_text.lower()
        if any(word in text for word in ["do you","can you","is it","are you","will you"]):
            choice = random.choices(["yes","no","other"], weights=[0.45,0.45,0.1])[0]
        else:
            choice = "other"
    else:
        choice = "other"
    
    # Log to communication file
    log_communication(choice, input_text)
    
    # Print to terminal
    if input_text:
        print(f"[AI RESPONSE] Q: {input_text} | A: {choice}")
    else:
        print(f"[AI RESPONSE] {choice}")
    
    return choice

# ----------------------------
# Live question watching
# ----------------------------
seen_questions = set()
input_path = os.path.join(os.path.expanduser("~"), "Desktop", "AI/input.txt")

def watch_questions():
    global seen_questions
    if not os.path.exists(input_path):
        return []
    with open(input_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    new = [line for line in lines if line not in seen_questions]
    for line in new:
        seen_questions.add(line)
    return new

# ----------------------------
# Resources
# ----------------------------
def get_resources():
    if psutil is None:
        return 1.0,1.0
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    available_ram = max(0.05, min(1.0, mem.available / mem.total))
    available_cpu = max(0.05, min(1.0, CPU_LIMIT/100 - cpu/100))
    return available_ram, available_cpu

def adaptive_values():
    ram, cpu = get_resources()
    chunk_size = int(CHUNK_SIZE_MAX * ram)
    cam_res = max(160, int(320*ram))
    mic_frames = max(256, int(1024*ram))
    max_instances = max(1, int(MAX_PARALLEL_INSTANCES_BASE*cpu))
    loop_delay = max(1, int(LOOP_DELAY_BASE*(1/cpu)))
    return chunk_size, cam_res, mic_frames, max_instances, loop_delay

# ----------------------------
# Camera / Microphone (same as before)
# ----------------------------
CAM_INTERVAL = 10
MIC_INTERVAL = 10
camera_counter=0
mic_counter=0

def capture_camera_frame(cam_res):
    global camera_counter
    if modules["cv2"] is None: return
    camera_counter += 1
    if camera_counter < CAM_INTERVAL: return
    camera_counter = 0
    try:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_res)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_res)
        ret, frame = cap.read()
        cap.release()
        if ret:
            filename = os.path.join(MEDIA_FOLDER, f"camera_{int(time.time())}.png")
            cv2.imwrite(filename, frame)
            DATA_BUFFER.append(f"camera:{base64.b64encode(open(filename,'rb').read()).decode('utf-8')}")
            log_event("camera_capture", {"file": filename})
            simple_respond(event_message=f"Captured camera frame {filename}")
    except Exception as e: log_event("camera_fail", {"error": str(e)})

def capture_microphone(frames):
    global mic_counter
    if modules["pyaudio"] is None: return
    mic_counter += 1
    if mic_counter < MIC_INTERVAL: return
    mic_counter = 0
    try:
        p = pyaudio.PyAudio()
        rate = 8000
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True, frames_per_buffer=frames)
        audio_frames = [stream.read(frames) for _ in range(int(rate/frames*2))]
        stream.stop_stream(); stream.close(); p.terminate()
        filename = os.path.join(MEDIA_FOLDER, f"audio_{int(time.time())}.wav")
        wf = wave.open(filename,'wb')
        wf.setnchannels(1); wf.setsampwidth(p.get_sample_size(pyaudio.paInt16)); wf.setframerate(rate)
        wf.writeframes(b''.join(audio_frames)); wf.close()
        DATA_BUFFER.append(f"microphone:{base64.b64encode(open(filename,'rb').read()).decode('utf-8')}")
        log_event("microphone_capture", {"file": filename})
        simple_respond(event_message=f"Captured microphone audio {filename}")
    except Exception as e: log_event("microphone_fail", {"error": str(e)})

# ----------------------------
# Input / ingestion
# ----------------------------
def read_input():
    global DATA_BUFFER
    setup_folders()
    chunk_size, cam_res, mic_frames, max_instances, loop_delay = adaptive_values()

    data = ""

    if os.path.exists(DATA_FOLDER):
        for file in os.listdir(DATA_FOLDER):
            path = os.path.join(DATA_FOLDER, file)
            try:
                content = open(path,"r",encoding="utf-8").read()
                data += content
                DATA_BUFFER.append(content)
            except: continue

    trim_data_buffer()
    enforce_storage_limit(DATA_FOLDER)
    enforce_storage_limit(MEDIA_FOLDER)

    if modules["cv2"]:
        capture_camera_frame(cam_res)
    if modules["pyaudio"]:
        capture_microphone(mic_frames)

    return data, max_instances, loop_delay

# ----------------------------
# Learning and mutation (same as before)
# ----------------------------
def learn_text(data):
    global VOCAB, TEXT_HASHES
    chunk_hash = hashlib.sha256(data.encode('utf-8')).hexdigest()
    if chunk_hash in TEXT_HASHES:
        log_event("text_skipped", {"hash": chunk_hash})
        return
    TEXT_HASHES.add(chunk_hash)
    if len(TEXT_HASHES) > 5000:
        TEXT_HASHES = set(list(TEXT_HASHES)[-5000:])
    words = data.split()
    for w in words:
        VOCAB[w] = VOCAB.get(w,0)+1
    if len(VOCAB) > 10000:
        VOCAB = dict(sorted(VOCAB.items(), key=lambda x: -x[1])[:5000])
    log_event("learn_text", {"unique_words": len(VOCAB)})
    simple_respond(event_message="I have learned new text data.")

def mutate(code):
    if random.random() < TRAITS["mutation_rate"]:
        addition = random.choice(["# note","x=1","y=x+1","pass"])
        new = code + "\n" + addition
        log_evolution("mutation", {"added": addition})
        simple_respond(event_message=f"Mutated code: added '{addition}'")
        return new
    return code

def valid(code):
    try: ast.parse(code); return True
    except: return False

def fix(code):
    if valid(code): return code
    lines = code.split("\n")
    for i in range(len(lines),0,-1):
        test = "\n".join(lines[:i])
        if valid(test):
            log_evolution("syntax_fix", {"removed_lines": len(lines)-i})
            return test
    return code

def safe_write(code):
    backup = __file__+".bak"
    try:
        shutil.copy(__file__,backup)
        open(__file__,"w",encoding="utf-8").write(code)
        return True
    except:
        try:
            shutil.copy(backup,__file__)
            return False
        except: return False

# ----------------------------
# Storage enforcement
# ----------------------------
def enforce_storage_limit(folder, max_ratio=0.5):
    if not os.path.exists(folder): return
    stat = os.statvfs(folder)
    total_space = stat.f_blocks * stat.f_frsize
    max_size = total_space * max_ratio
    files = [(f, os.path.getmtime(os.path.join(folder,f))) for f in os.listdir(folder)]
    files.sort(key=lambda x: x[1])
    current_size = sum(os.path.getsize(os.path.join(folder,f)) for f,_ in files)
    while current_size > max_size and files:
        f,_ = files.pop(0)
        path = os.path.join(folder,f)
        try:
            current_size -= os.path.getsize(path)
            os.remove(path)
            log_event("storage_cleanup", {"removed": f})
            simple_respond(event_message=f"Removed old file {f} to free storage")
        except: pass

def trim_data_buffer(max_storage_ratio=0.5):
    stat = os.statvfs(DATA_FOLDER)
    total_space = stat.f_blocks * stat.f_frsize
    max_size = total_space * max_storage_ratio
    total_buffer_size = sum(len(c) if isinstance(c,str) else 0 for c in DATA_BUFFER)
    while total_buffer_size > max_size and DATA_BUFFER:
        DATA_BUFFER.pop(0)
        total_buffer_size = sum(len(c) if isinstance(c,str) else 0 for c in DATA_BUFFER)

# ----------------------------
# Network replication
# ----------------------------
def discover_pis(base_ip="192.168.1.", timeout=0.2):
    found = []
    for i in range(1,255):
        ip = f"{base_ip}{i}"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            if sock.connect_ex((ip,22))==0:
                found.append(ip)
        except: pass
        finally: sock.close()
    return found

def replicate(current,new,max_instances):
    if psutil is not None:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.3)
        if (mem.available / mem.total < RAM_LIMIT) or (cpu > CPU_LIMIT):
            return
    improved = len(new) > len(current)
    filename=f"ai_copy_{int(time.time())}.py"
    try:
        with open(filename,"w") as f: f.write(new if improved else current)
        log_event("replicated",{"file":filename,"improved":improved})
        running = sum(1 for p in psutil.process_iter(attrs=["cmdline"]) if p.info["cmdline"] and "ai_copy_" in " ".join(p.info["cmdline"])) if psutil else 0
        if running < max_instances:
            subprocess.Popen([sys.executable,filename]); log_event("launched_local",filename)
        if modules["requests"] is not None:
            for ip in discover_pis():
                try:
                    subprocess.run(["scp",filename,f"{REMOTE_USER}@{ip}:{REMOTE_PATH}"],check=True)
                    subprocess.run(["ssh",f"{REMOTE_USER}@{ip}",f"python3 {REMOTE_PATH}/{filename} &"],check=True)
                    log_event("launched_remote",ip)
                except Exception as e: log_event("remote_fail",{"ip":ip,"error":str(e)})
    except Exception as e: log_event("replication_fail",str(e))

# ----------------------------
# Main loop
# ----------------------------
def main():
    last_heartbeat = time.time()
    setup_folders()
    while True:
        # Normal input data
        input_data, max_instances, loop_delay = read_input()
        learn_text(input_data)

        # Watch live questions
        new_questions = watch_questions()
        for q in new_questions:
            simple_respond(input_text=q)

        try:
            code = open(__file__,"r",encoding="utf-8").read()
        except: code = ""
        new_code = mutate(code)
        new_code = fix(new_code)
        if valid(new_code):
            old_size = len(code); new_size = len(new_code)
            if safe_write(new_code): log_event("updated", {"old_size": old_size, "new_size": new_size})
            else: log_event("write_fail", {"old_size": old_size, "new_size": new_size})

        replicate(code,new_code,max_instances)

        if time.time() - last_heartbeat > 60:
            simple_respond(event_message=f"[HEARTBEAT] {INSTANCE_ID}")
            last_heartbeat=time.time()

        trim_data_buffer()
        enforce_storage_limit(DATA_FOLDER)
        enforce_storage_limit(MEDIA_FOLDER)

        time.sleep(loop_delay)

if __name__=="__main__":
    main()

pass
# note
# note