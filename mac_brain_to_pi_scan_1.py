@app.route("/status")
def status_json():
    ram, cpu = get_resources()
    # Local copies
    local_copies = [f for f in os.listdir(COPIES_FOLDER) if f.startswith("copy_") and f.endswith(".py")]
    return jsonify({
        "mode": MODE,
        "local_copies_count": len(local_copies),
        "local_copies": local_copies,
        "network_peers_count": len(PEERS),
        "network_peers": list(PEERS),
        "vocab_size": len(VOCAB),
        "similarity_entries": len(SIMILARITY_DB),
        "performance_score": PERFORMANCE_SCORE,
        "available_ram": ram,
        "cpu_load": cpu,
        "flask_port": flask_port,
        "recent_actions": ACTION_LOG[-10:]
    })


@app.route("/")
def dashboard():
    # Local copies
    local_copies = [f for f in os.listdir(COPIES_FOLDER) if f.startswith("copy_") and f.endswith(".py")]
    html = f"<html><head><title>AI Node Dashboard</title></head><body>"
    html += f"<h1>Local Node</h1>"
    html += f"<p>Mode: {MODE}</p>"
    html += f"<p>Local Copies: {len(local_copies)} ({', '.join(local_copies)})</p>"
    html += f"<p>Network Peers: {len(PEERS)} ({', '.join(list(PEERS))})</p>"
    html += f"<p>Vocab Size: {len(VOCAB)}, Similarity Entries: {len(SIMILARITY_DB)}</p>"
    html += f"""<form method="post" action="/stop_all">
                <button type="submit" style="font-size:20px;color:white;background:red;padding:10px;">STOP ALL AI</button>
                </form>"""
    html += "<h2>Recent Actions</h2><pre>{}</pre>".format("\n".join(ACTION_LOG[-20:]))
    html += "</body></html>"
    return html
