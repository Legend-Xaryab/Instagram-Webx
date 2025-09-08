from flask import Flask, request, render_template_string, redirect, url_for, session
from instagrapi import Client
import os
import time
import uuid
import threading

app = Flask(__name__)
app.secret_key = "super-secret-key"   # change this in production

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Store tasks here
tasks = {}

# Admin credentials (change these)
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


# ------------------- Helper -------------------
def message_sender(task_id, username, password, chat_id, delay, messages, stop_event):
    cl = Client()
    try:
        cl.login(username, password)
    except Exception as e:
        tasks[task_id]["status"] = f"Login failed: {e}"
        return

    for msg in messages:
        if stop_event.is_set():
            tasks[task_id]["status"] = "stopped"
            return
        try:
            cl.direct_send(msg.strip(), [chat_id])
            time.sleep(delay)
        except Exception as e:
            tasks[task_id]["status"] = f"Error: {e}"
            return

    tasks[task_id]["status"] = "finished"


# ------------------- User Panel -------------------
@app.route("/")
def index():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    user_id = session["user_id"]

    user_tasks = {tid: data for tid, data in tasks.items() if data["owner"] == user_id}
    error_message = session.pop("error_message", None)

    return render_template_string(USER_TEMPLATE,
                                  user_tasks=user_tasks,
                                  error_message=error_message)


@app.route("/start", methods=["POST"])
def start_task():
    try:
        username = request.form["username"]
        password = request.form["password"]
        chat_id = request.form["chat_id"]
        delay = int(request.form["delay"])

        if "messages_file" not in request.files:
            session["error_message"] = "No message file uploaded."
            return redirect(url_for("index"))

        messages_file = request.files["messages_file"]
        if messages_file.filename == "":
            session["error_message"] = "Please select a valid .txt file."
            return redirect(url_for("index"))

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], messages_file.filename)
        messages_file.save(file_path)

        with open(file_path, "r") as f:
            messages = f.readlines()
        if not messages:
            session["error_message"] = "Your message file is empty."
            return redirect(url_for("index"))

        task_id = str(uuid.uuid4())[:8]
        stop_event = threading.Event()
        thread = threading.Thread(target=message_sender,
                                  args=(task_id, username, password, chat_id, delay, messages, stop_event),
                                  daemon=True)
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


@app.route("/stop/<task_id>")
def stop_task(task_id):
    user_id = session.get("user_id")
    task = tasks.get(task_id)
    if task and task["owner"] == user_id:
        task["stop_event"].set()
        task["status"] = "stopped"
    return redirect(url_for("index"))


# ------------------- Admin Panel -------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Invalid credentials")
    return render_template_string(ADMIN_LOGIN_TEMPLATE)


@app.route("/admin/panel")
def admin_panel():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    return render_template_string(ADMIN_PANEL_TEMPLATE, running_tasks=tasks)


@app.route("/admin/stop/<task_id>")
def admin_stop_task(task_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    task = tasks.get(task_id)
    if task:
        task["stop_event"].set()
        task["status"] = "stopped"
    return redirect(url_for("admin_panel"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ------------------- Templates -------------------
USER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>User Panel - Messenger Bot</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"/>
  <style>
    .gradient-bg{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);}
    .glass{background:rgba(255,255,255,.1);backdrop-filter:blur(8px);}
  </style>
</head>
<body class="min-h-screen gradient-bg text-white">
  <div class="max-w-3xl mx-auto px-6 py-12">
    <header class="text-center mb-10">
      <h1 class="text-3xl font-bold">Your Tasks</h1>
      <p class="text-blue-200">Manage your running tasks</p>
    </header>

    {% if error_message %}
    <div class="glass rounded-xl p-4 mb-6 text-red-200 bg-red-900/40 border border-red-500/50">
      <i class="fa-solid fa-triangle-exclamation mr-2"></i> {{ error_message }}
    </div>
    {% endif %}

    <form action="/start" method="post" enctype="multipart/form-data" class="glass rounded-xl p-6 mb-10">
      <input class="w-full p-2 rounded mb-3 text-black" type="text" name="username" placeholder="Instagram Username" required>
      <input class="w-full p-2 rounded mb-3 text-black" type="password" name="password" placeholder="Instagram Password" required>
      <input class="w-full p-2 rounded mb-3 text-black" type="text" name="chat_id" placeholder="Group Chat ID" required>
      <input class="w-full p-2 rounded mb-3 text-black" type="number" name="delay" placeholder="Delay in seconds" required>
      <input class="w-full p-2 rounded mb-3 text-black" type="file" name="messages_file" accept=".txt" required>
      <button class="w-full bg-green-600 hover:bg-green-700 p-2 rounded">Start Messaging</button>
    </form>

    <h2 class="text-xl font-semibold mb-4">Running Tasks</h2>
    {% if user_tasks %}
      <div class="space-y-4">
        {% for tid, task in user_tasks.items() %}
        <div class="glass rounded-xl p-4 flex justify-between items-center">
          <div>
            <p class="font-semibold">Task ID: {{ tid }}</p>
            <p class="text-blue-200 text-sm">Status: {{ task.status }}</p>
          </div>
          <a href="/stop/{{ tid }}" class="px-3 py-1 bg-red-600 hover:bg-red-700 rounded">Stop</a>
        </div>
        {% endfor %}
      </div>
    {% else %}
      <p class="text-blue-200">No tasks running.</p>
    {% endif %}
  </div>
</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Login</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="flex items-center justify-center min-h-screen bg-gray-900 text-white">
  <form method="post" class="bg-gray-800 p-8 rounded-lg shadow-lg w-80">
    <h2 class="text-2xl font-bold mb-4">Admin Login</h2>
    {% if error %}<p class="text-red-400 mb-3">{{ error }}</p>{% endif %}
    <input class="w-full p-2 mb-3 text-black rounded" type="text" name="username" placeholder="Username" required>
    <input class="w-full p-2 mb-3 text-black rounded" type="password" name="password" placeholder="Password" required>
    <button class="w-full bg-blue-600 hover:bg-blue-700 p-2 rounded">Login</button>
  </form>
</body>
</html>
"""

ADMIN_PANEL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-gray-900 text-white p-8">
  <h1 class="text-3xl font-bold mb-6">Admin Panel</h1>
  <a href="/admin/logout" class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded mb-6 inline-block">Logout</a>

  {% if running_tasks %}
    <div class="space-y-4">
      {% for tid, task in running_tasks.items() %}
      <div class="bg-gray-800 p-4 rounded flex justify-between items-center">
        <div>
          <p><strong>Task ID:</strong> {{ tid }}</p>
          <p class="text-sm text-gray-400">User: {{ task.info.username }} | Chat: {{ task.info.chat_id }}</p>
          <p>Status: {{ task.status }}</p>
        </div>
        <a href="/admin/stop/{{ tid }}" class="px-3 py-1 bg-red-600 hover:bg-red-700 rounded">Stop</a>
      </div>
      {% endfor %}
    </div>
  {% else %}
    <p>No tasks running.</p>
  {% endif %}
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
