from flask import Flask, request, render_template_string
from instagrapi import Client
import os
import time
import threading
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

tasks = {}
sessions = {}  # store logged-in clients by session ID (temporary)


def send_messages_task(task_id, cl, thread_id, delay, file_path):
    try:
        with open(file_path, 'r') as file:
            messages = file.readlines()

        for index, message in enumerate(messages):
            if tasks[task_id]["stop"]:
                tasks[task_id]["status"] = "Stopped by user."
                return

            message = message.strip()
            if message:
                cl.direct_send(message, [], thread_ids=[thread_id])
                print(f"[{index+1}] Sent: {message}")
                time.sleep(delay)

        tasks[task_id]["status"] = "Completed successfully!"
    except Exception as e:
        tasks[task_id]["status"] = f"Error: {e}"


@app.route('/')
def index():
    return render_template_string('''
    <html>
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        <style>body { font-family: 'Poppins', sans-serif; }</style>
    </head>
    <body class="bg-gradient-to-r from-purple-400 via-pink-500 to-red-500 min-h-screen flex items-center justify-center">
        <div class="bg-white shadow-xl rounded-2xl p-8 w-full max-w-md text-center">
            <h2 class="text-2xl font-bold mb-6 text-gray-800">🚀 Instagram Group Message Bot</h2>
            <form action="/get_chats" method="post" class="space-y-4">
                <input type="text" name="username" placeholder="Instagram Username" required class="w-full px-4 py-2 border rounded-lg">
                <input type="password" name="password" placeholder="Instagram Password" required class="w-full px-4 py-2 border rounded-lg">
                <button type="submit" class="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition">Login & Fetch Chats</button>
            </form>
        </div>
    </body>
    </html>
    ''')


@app.route('/get_chats', methods=['POST'])
def get_chats():
    username = request.form['username']
    password = request.form['password']

    cl = Client()
    try:
        cl.login(username, password)
    except Exception as e:
        return f"<h3>Login failed: {e}</h3>"

    # Save client in session
    session_id = str(uuid.uuid4())
    sessions[session_id] = cl

    # Fetch group chats
    threads = cl.direct_threads(amount=10)  # fetch latest 10 chats
    options = ""
    for t in threads:
        options += f'<option value="{t.id}">{t.thread_title} ({t.id})</option>'

    return render_template_string(f'''
    <html>
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 min-h-screen flex items-center justify-center">
        <div class="bg-white shadow-xl rounded-2xl p-8 w-full max-w-md text-center">
            <h2 class="text-xl font-bold mb-4">✅ Logged in as {username}</h2>
            <form action="/start_task" method="post" enctype="multipart/form-data" class="space-y-4">
                <input type="hidden" name="session_id" value="{session_id}">
                <label class="block text-left font-semibold">Select Group Chat:</label>
                <select name="thread_id" class="w-full px-4 py-2 border rounded-lg">{options}</select>
                <input type="number" name="delay" placeholder="Delay (seconds)" value="5" required class="w-full px-4 py-2 border rounded-lg">
                <input type="file" name="messages_file" accept=".txt" required class="w-full px-4 py-2 border rounded-lg">
                <button type="submit" class="w-full py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition">Start Sending</button>
            </form>
        </div>
    </body>
    </html>
    ''')


@app.route('/start_task', methods=['POST'])
def start_task():
    session_id = request.form['session_id']
    cl = sessions.get(session_id)

    if not cl:
        return "<h3>Session expired. Please login again.</h3>"

    thread_id = request.form['thread_id']
    delay = int(request.form['delay'])

    messages_file = request.files['messages_file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], messages_file.filename)
    messages_file.save(file_path)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "Running", "stop": False}

    thread = threading.Thread(target=send_messages_task, args=(task_id, cl, thread_id, delay, file_path))
    thread.start()

    return f"<h3>✅ Task started! Your Task ID is:</h3><p><b>{task_id}</b></p><p>Use /stop/{task_id} to stop or /status/{task_id} to check progress.</p>"


@app.route('/stop/<task_id>')
def stop_task(task_id):
    if task_id in tasks:
        tasks[task_id]["stop"] = True
        return f"<h3>🛑 Task {task_id} stopped.</h3>"
    return "<h3>❌ Task not found.</h3>"


@app.route('/status/<task_id>')
def check_status(task_id):
    if task_id in tasks:
        return f"<h3>📌 Status of {task_id}: {tasks[task_id]['status']}</h3>"
    return "<h3>❌ Task not found.</h3>"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
