import sys, os, time, random, ast, uuid, shutil, socket, platform, base64, subprocess

# ----------------------------
# Optional modules (no pip / no git)
# ----------------------------
modules = {
    "psutil": "psutil",
    "cv2": "opencv-python",
    "pyaudio": "pyaudio",
    "requests": "requests"
}

for mod, pkg in modules.items():
    try:
        globals()[mod] = __import__(mod)
    except ImportError:
        print(f"[WARNING] Module '{pkg}' not available. Skipping related functionality.")
        globals()[mod] = None

import wave

# ----------------------------
# ID, Traits, Limits
# ----------------------------
INSTANCE_ID = str(uuid.uuid4())[:8]
TRAITS = {"mutation_rate": 0.23, "replication_rate": 0.07}
MAX_CODE_SIZE = 5 * 1024 * 1024
LOOP_DELAY = 5
MAX_PARALLEL_INSTANCES = 10
CPU_LIMIT = 50
RAM_LIMIT = 0.5
if platform.system() == "Linux" and "arm" in platform.machine():
    CHUNK_SIZE = 10*1024*1024
else:
    CHUNK_SIZE = 50*1024*1024

REMOTE_USER = "pi"
REMOTE_PATH = "~/Desktop/AI/"

DATA_FOLDER = "./data"
MEDIA_FOLDER = "./media"
IMAGE_EXT = (".png",".jpg",".jpeg",".bmp")
VIDEO_EXT = (".mp4",".avi",".mov")
AUDIO_EXT = (".mp3",".wav",".flac")

DATA_BUFFER = []

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
# Resource / Network
# ----------------------------
def resources_ok():
    if psutil is None: return True
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.3)
    return (mem.available / mem.total > RAM_LIMIT) and (cpu < CPU_LIMIT)

def running_copies():
    if psutil is None: return 0
    count = 0
    for p in psutil.process_iter(attrs=["cmdline"]):
        try:
            if p.info["cmdline"] and "ai_copy_" in " ".join(p.info["cmdline"]):
                count += 1
        except: pass
    return count

def discover_pis(base_ip="192.168.1.", timeout=0.2):
    found = []
    for i in range(1,255):
        ip = f"{base_ip}{i}"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            if sock.connect_ex((ip,22))==0: found.append(ip)
        except: pass
        finally: sock.close()
    return found

# ----------------------------
# Mutation & Syntax
# ----------------------------
def mutate(code):
    if random.random() < TRAITS["mutation_rate"]:
        addition = random.choice(["# note","x=1","y=x+1","pass"])
        new = code+"\n"+addition
        log_evolution("mutation", {"added": addition})
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

# ----------------------------
# Folders / Media
# ----------------------------
def setup_folders():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(MEDIA_FOLDER, exist_ok=True)

def ingest_media():
    if not os.path.exists(MEDIA_FOLDER): return
    for file in os.listdir(MEDIA_FOLDER):
        path = os.path.join(MEDIA_FOLDER,file)
        ext = os.path.splitext(file)[1].lower()
        try:
            if ext in IMAGE_EXT+VIDEO_EXT+AUDIO_EXT:
                size = os.path.getsize(path)
                with open(path,"rb") as f:
                    chunk_index=0
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk: break
                        DATA_BUFFER.append(f"{file}_chunk{chunk_index}:{base64.b64encode(chunk).decode('utf-8')}")
                        chunk_index += 1
                log_event("media_ingested", {"file":file,"chunks":chunk_index,"size":size})
        except Exception as e: log_event("media_fail", {"file":file,"error":str(e)})

# ----------------------------
# Camera / Mic
# ----------------------------
CAMERA_INTERVAL = 10
MIC_INTERVAL = 10
camera_counter = 0
mic_counter = 0

def capture_camera_frame():
    global camera_counter
    if modules["cv2"] is None: return
    camera_counter += 1
    if camera_counter < CAMERA_INTERVAL: return
    camera_counter=0
    try:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT,240)
        ret, frame = cap.read()
        cap.release()
        if ret:
            filename=os.path.join(MEDIA_FOLDER,f"camera_{int(time.time())}.png")
            cv2.imwrite(filename,frame)
            DATA_BUFFER.append(f"camera:{base64.b64encode(open(filename,'rb').read()).decode('utf-8')}")
            log_event("camera_capture", {"file":filename})
    except Exception as e: log_event("camera_fail", {"error":str(e)})

def capture_microphone(duration=2, rate=8000):
    global mic_counter
    if modules["pyaudio"] is None: return
    mic_counter += 1
    if mic_counter < MIC_INTERVAL: return
    mic_counter=0
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,channels=1,rate=rate,input=True,frames_per_buffer=1024)
        frames=[stream.read(1024) for _ in range(0,int(rate/1024*duration))]
        stream.stop_stream(); stream.close(); p.terminate()
        filename=os.path.join(MEDIA_FOLDER,f"audio_{int(time.time())}.wav")
        wf=wave.open(filename,'wb')
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames)); wf.close()
        DATA_BUFFER.append(f"microphone:{base64.b64encode(open(filename,'rb').read()).decode('utf-8')}")
        log_event("microphone_capture", {"file":filename})
    except Exception as e: log_event("microphone_fail", {"error":str(e)})

# ----------------------------
# Input
# ----------------------------
def read_input():
    global DATA_BUFFER
    setup_folders()
    data=""
    # local
    try: content=open("input.txt","r",encoding="utf-8").read(); data+=content; DATA_BUFFER.append(content)
    except: pass
    # fetched
    if modules["requests"] is not None:
        if os.path.exists(DATA_FOLDER):
            for file in os.listdir(DATA_FOLDER):
                path=os.path.join(DATA_FOLDER,file)
                try: content=open(path,"r",encoding="utf-8").read(); data+=content; DATA_BUFFER.append(content)
                except: continue
    ingest_media()
    capture_camera_frame()
    capture_microphone()
    if len(DATA_BUFFER)>50: DATA_BUFFER=DATA_BUFFER[-50:]
    total_size=sum(len(c) if isinstance(c,str) else 0 for c in DATA_BUFFER)
    log_event("input_read", {"buffer_count":len(DATA_BUFFER),"data_size":total_size})
    return data

# ----------------------------
# Replication
# ----------------------------
def replicate(current,new):
    if not resources_ok(): return
    improved=len(new)>len(current)
    filename=f"ai_copy_{int(time.time())}.py"
    try:
        with open(filename,"w") as f: f.write(new if improved else current)
        log_event("replicated", {"file":filename,"improved":improved})
        if running_copies()<MAX_PARALLEL_INSTANCES: subprocess.Popen([sys.executable,filename]); log_event("launched_local", filename)
        # remote replication skipped if no requests
        if modules["requests"] is not None:
            for ip in discover_pis():
                try:
                    subprocess.run(["scp", filename, f"{REMOTE_USER}@{ip}:{REMOTE_PATH}"], check=True)
                    subprocess.run(["ssh", f"{REMOTE_USER}@{ip}", f"python3 {REMOTE_PATH}/{filename} &"], check=True)
                    log_event("launched_remote", ip)
                except Exception as e: log_event("remote_fail", {"ip":ip,"error":str(e)})
    except Exception as e: log_event("replication_fail", str(e))

# ----------------------------
# Safe write
# ----------------------------
def safe_write(code):
    backup=__file__+".bak"
    try: shutil.copy(__file__, backup); open(__file__,"w",encoding="utf-8").write(code); return True
    except: 
        try: shutil.copy(backup,__file__); return False
        except: return False

# ----------------------------
# Main loop
# ----------------------------
def main():
    last_heartbeat=time.time()
    while True:
        input_data=read_input()
        try: code=open(__file__,"r",encoding="utf-8").read()
        except: code=""
        new_code=mutate(code)
        new_code=fix(new_code)
        if valid(new_code):
            old_size=len(code); new_size=len(new_code)
            if safe_write(new_code): log_event("updated", {"old_size":old_size,"new_size":new_size})
            else: log_event("write_fail", {"old_size":old_size,"new_size":new_size})
        replicate(code,new_code)
        if time.time()-last_heartbeat>60:
            print(f"[HEARTBEAT] {INSTANCE_ID}")
            log_event("heartbeat", INSTANCE_ID)
            last_heartbeat=time.time()
        time.sleep(LOOP_DELAY)

if __name__=="__main__":
    main()

pass
y=x+1
x=1