from flask import Flask, request, redirect, url_for, session
from instagrapi import Client
import os
import time
import threading
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_key"  # required for sessions (change this!)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global dictionary to track tasks
tasks = {}  # {task_id: {"thread": ..., "stop_event": ..., "status": ..., "info": {...}, "owner": session_id}}


def message_sender(task_id, username, password, chat_id, delay, messages, stop_event):
    """
    Background thread that repeatedly sends messages until stopped.
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
    # Ensure this user has a session ID
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())  # assign unique ID per visitor

    # Show only this user's tasks
    user_id = session["user_id"]
    user_tasks = {tid: data for tid, data in tasks.items() if data["owner"] == user_id}

    task_list_html = ""
    if user_tasks:
        task_list_html += "<h3>Your Tasks</h3><ul>"
        for tid, data in user_tasks.items():
            task_list_html += f"<li><b>{tid}</b> - {data['status']} "
            if data["status"] == "running":
                task_list_html += f'<a href="/stop/{tid}"><button style="background:red;color:white;">Stop</button></a>'
            task_list_html += "</li>"
        task_list_html += "</ul>"
    else:
        task_list_html = "<h3>No tasks yet. Start one below 👇</h3>"

    return f'''
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Instagram Group Message Bot</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #6EE7B7, #3B82F6, #9333EA);
                    background-size: 300% 300%;
                    animation: gradientBG 10s ease infinite;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    min-height: 100vh;
                    color: #333;
                    padding: 20px;
                }}
                @keyframes gradientBG {{
                    0% {{background-position: 0% 50%;}}
                    50% {{background-position: 100% 50%;}}
                    100% {{background-position: 0% 50%;}}
                }}
                .container {{
                    max-width: 600px;
                    width: 100%;
                    padding: 30px;
                    margin-top: 20px;
                    background-color: rgba(255, 255, 255, 0.95);
                    box-shadow: 0px 8px 20px rgba(0, 0, 0, 0.2);
                    border-radius: 20px;
                    text-align: center;
                    animation: fadeIn 1s ease forwards;
                }}
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(30px) scale(0.95); }}
                    to {{ opacity: 1; transform: translateY(0) scale(1); }}
                }}
                h2 {{
                    margin-bottom: 20px;
                    color: #111827;
                    font-size: 1.8rem;
                    animation: textGlow 2s infinite alternate;
                }}
                @keyframes textGlow {{
                    from {{ text-shadow: 0 0 5px #3B82F6; }}
                    to {{ text-shadow: 0 0 20px #9333EA; }}
                }}
                input, button {{
                    width: 100%;
                    padding: 12px;
                    margin: 10px 0;
                    border-radius: 10px;
                    border: 1px solid #ccc;
                    font-size: 1rem;
                    transition: all 0.3s ease;
                }}
                input:focus {{
                    border-color: #3B82F6;
                    outline: none;
                    box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
                }}
                button {{
                    background: linear-gradient(45deg, #4CAF50, #3B82F6, #9333EA);
                    color: white;
                    font-weight: bold;
                    cursor: pointer;
                    border: none;
                }}
                button:hover {{
                    transform: translateY(-3px) scale(1.05);
                    box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
                }}
                button:active {{
                    transform: scale(0.95);
                }}
            </style>
            <meta http-equiv="refresh" content="10"> <!-- auto refresh every 10s -->
        </head>
        <body>
            <div class="container">
                <h2>🚀 Instagram Group Message Bot</h2>
                <form action="/start" method="post" enctype="multipart/form-data">
                    <input type="text" name="username" placeholder="Instagram Username" required>
                    <input type="password" name="password" placeholder="Instagram Password" required>
                    <input type="text" name="chat_id" placeholder="Target Group Chat ID" required>
                    <input type="number" name="delay" placeholder="Delay (in seconds)" value="5" required>
                    <input type="file" name="messages_file" accept=".txt" required>
                    <button type="submit">✨ Start Messaging ✨</button>
                </form>
                <hr>
                {task_list_html}
            </div>
        </body>
        </html>
    '''


@app.route('/start', methods=['POST'])
def start_task():
    username = request.form['username']
    password = request.form['password']
    chat_id = request.form['chat_id']
    delay = int(request.form['delay'])

    messages_file = request.files['messages_file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], messages_file.filename)
    messages_file.save(file_path)

    with open(file_path, 'r') as f:
        messages = f.readlines()

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


@app.route('/stop/<task_id>')
def stop_task(task_id):
    if task_id in tasks and tasks[task_id]["owner"] == session.get("user_id"):
        tasks[task_id]["stop_event"].set()
        tasks[task_id]["status"] = "stopping..."
    return redirect(url_for("index"))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
