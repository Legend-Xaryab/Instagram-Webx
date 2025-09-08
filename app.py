from flask import Flask, request, redirect, url_for, session, render_template_string
from instagrapi import Client
import os
import time
import threading
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_key"  # change this in production!

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global dictionary to track tasks
tasks = {}  # {task_id: {"thread": ..., "stop_event": ..., "status": ..., "info": {...}, "owner": session_id}}


def message_sender(task_id, username, password, chat_id, delay, messages, stop_event):
    """
    Background thread to repeatedly send messages until stopped.
    """
    cl = Client()
    try:
        cl.login(username, password)
    except Exception as e:
        tasks[task_id]["status"] = f"Login failed: {e}"
        return

    index = 0
    while not stop_event.is_set():
        try:
            message = messages[index % len(messages)].strip()
            if message:
                cl.direct_send(message, [chat_id])
                print(f"[{task_id}] Sent: {message}")
            index += 1
            time.sleep(delay)
        except Exception as e:
            tasks[task_id]["status"] = f"Error: {e}"
            break

    tasks[task_id]["status"] = "stopped"


@app.route('/')
def index():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())

    user_id = session["user_id"]
    user_tasks = {tid: data for tid, data in tasks.items() if data["owner"] == user_id}

    # pull error message if exists
    error_message = session.pop("error_message", None)

    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Instagram Bot Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"/>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    *{font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial;}
    .gradient-bg{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);}
    .glass{background:rgba(255,255,255,.1);backdrop-filter:blur(8px);}
    .floaty{animation:floaty 8s ease-in-out infinite;}
    @keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
  </style>
  <meta http-equiv="refresh" content="10"> <!-- auto refresh -->
</head>
<body class="min-h-screen gradient-bg text-white">
  <div class="max-w-4xl mx-auto px-6 py-12">
    <!-- Header -->
    <header class="text-center mb-12">
      <div class="inline-flex items-center justify-center w-20 h-20 rounded-full bg-white text-purple-600 shadow-xl mb-4 floaty">
        <i class="fa-brands fa-instagram text-3xl"></i>
      </div>
      <h1 class="text-4xl font-bold">Instagram Group Messenger</h1>
      <p class="text-blue-100 mt-2">Automated messaging made simple</p>
    </header>

    <!-- Error Alert -->
    {% if error_message %}
      <div class="glass rounded-xl p-4 mb-6 text-red-200 bg-red-900/40 border border-red-500/50">
        <i class="fa-solid fa-triangle-exclamation mr-2"></i> {{ error_message }}
      </div>
    {% endif %}

    <!-- Start Task Form -->
    <section class="glass rounded-2xl p-8 shadow-xl mb-12">
      <h2 class="text-2xl font-semibold mb-6"><i class="fa-solid fa-paper-plane mr-2"></i> Start a New Task</h2>
      <form action="/start" method="post" enctype="multipart/form-data" class="space-y-4">
        <input type="text" name="username" placeholder="Instagram Username" required
               class="w-full px-4 py-3 rounded-lg bg-white/20 text-white placeholder-gray-300 border border-white/20 focus:outline-none focus:ring-2 focus:ring-purple-400"/>
        <input type="password" name="password" placeholder="Instagram Password" required
               class="w-full px-4 py-3 rounded-lg bg-white/20 text-white placeholder-gray-300 border border-white/20 focus:outline-none focus:ring-2 focus:ring-purple-400"/>
        <input type="text" name="chat_id" placeholder="Target Group Chat ID" required
               class="w-full px-4 py-3 rounded-lg bg-white/20 text-white placeholder-gray-300 border border-white/20 focus:outline-none focus:ring-2 focus:ring-purple-400"/>
        <input type="number" name="delay" placeholder="Delay (in seconds)" value="5" required
               class="w-full px-4 py-3 rounded-lg bg-white/20 text-white placeholder-gray-300 border border-white/20 focus:outline-none focus:ring-2 focus:ring-purple-400"/>
        <input type="file" name="messages_file" accept=".txt" required
               class="w-full px-4 py-3 rounded-lg bg-white/20 text-white file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-700"/>
        <button type="submit"
                class="w-full px-4 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg text-white font-semibold transition flex items-center justify-center">
          <i class="fa-solid fa-rocket mr-2"></i> Start Messaging
        </button>
      </form>
    </section>

    <!-- Running Tasks -->
    <section>
      <h2 class="text-2xl font-semibold mb-6"><i class="fa-solid fa-list mr-2"></i> Your Running Tasks</h2>
      {% if user_tasks %}
        <div class="space-y-4">
          {% for tid, data in user_tasks.items() %}
          <div class="glass rounded-xl p-6 flex items-center justify-between border border-white/10">
            <div>
              <p class="font-semibold">Task ID: {{ tid }}</p>
              <p class="text-sm text-blue-200">Status: {{ data['status'] }} | Delay: {{ data['info']['delay'] }}s</p>
            </div>
            {% if data['status'] == 'running' %}
              <a href="/stop/{{ tid }}" class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm transition">
                <i class="fa-solid fa-stop mr-1"></i> Stop
              </a>
            {% else %}
              <span class="px-4 py-2 bg-gray-500 rounded-lg text-sm">Stopped</span>
            {% endif %}
          </div>
          {% endfor %}
        </div>
      {% else %}
        <div class="text-center py-12 text-blue-200">
          <i class="fa-solid fa-circle-check text-5xl mb-4"></i>
          <p>No active tasks right now.</p>
        </div>
      {% endif %}
    </section>
  </div>
</body>
</html>
    """, user_tasks=user_tasks, error_message=error_message)


@app.route('/start', methods=['POST'])
def start_task():
    try:
        username = request.form['username']
        password = request.form['password']
        chat_id = request.form['chat_id']
        delay = int(request.form['delay'])

        # validate file upload
        if 'messages_file' not in request.files:
            session["error_message"] = "No message file uploaded."
            return redirect(url_for("index"))

        messages_file = request.files['messages_file']
        if messages_file.filename == "":
            session["error_message"] = "Please select a valid .txt file."
            return redirect(url_for("index"))

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], messages_file.filename)
        messages_file.save(file_path)

        with open(file_path, 'r') as f:
            messages = f.readlines()
        if not messages:
            session["error_message"] = "Your message file is empty."
            return redirect(url_for("index"))

        # create task
        task_id = str(uuid.uuid4())[:8]
        stop_event = threading.Event()
        thread = threading.Thread(
            target=message_sender,
            args=(task_id, username, password, chat_id, delay, messages, stop_event),
            daemon=True
        )
        thread.start()

        tasks[task_id] = {
            "thread": thread,
            "stop_event": stop_event,
            "status": "running",
            "info": {"username": username, "chat_id": chat_id, "delay": delay},
            "owner": session["user_id"]
        }

        return redirect(url_for("index"))

    except Exception as e:
        session["error_message"] = f"Error starting task: {e}"
        return redirect(url_for("index"))


@app.route('/stop/<task_id>')
def stop_task(task_id):
    if task_id in tasks and tasks[task_id]["owner"] == session.get("user_id"):
        tasks[task_id]["stop_event"].set()
        tasks[task_id]["status"] = "stopping..."
    return redirect(url_for("index"))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
