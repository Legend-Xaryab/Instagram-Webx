from flask import Flask, request
from instagrapi import Client
import os
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def index():
    return '''
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Instagram Group Message Bot</title>
            <style>
                body {
                    background-color: #f4f4f9;
                    font-family: Arial, sans-serif;
                    color: #333;
                    text-align: center;
                }
                .container {
                    margin: 50px auto;
                    max-width: 500px;
                    padding: 20px;
                    background-color: #ffffff;
                    box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
                    border-radius: 10px;
                }
                input, button {
                    width: 100%;
                    padding: 10px;
                    margin: 10px 0;
                    border-radius: 5px;
                    border: 1px solid #ccc;
                }
                button {
                    background-color: #4CAF50;
                    color: white;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #45a049;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Instagram Group Message Bot</h2>
                <form action="/" method="post" enctype="multipart/form-data">
                    <input type="text" name="username" placeholder="Instagram Username" required>
                    <input type="password" name="password" placeholder="Instagram Password" required>
                    <input type="text" name="chat_id" placeholder="Target Group Chat ID" required>
                    <input type="number" name="delay" placeholder="Delay (in seconds)" value="5" required>
                    <input type="file" name="messages_file" accept=".txt" required>
                    <button type="submit">Send Messages</button>
                </form>
            </div>
        </body>
        </html>
    '''


@app.route('/', methods=['POST'])
def send_messages():
    username = request.form['username']
    password = request.form['password']
    chat_id = request.form['chat_id']
    delay = int(request.form['delay'])

    messages_file = request.files['messages_file']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], messages_file.filename)
    messages_file.save(file_path)

    with open(file_path, 'r') as file:
        messages = file.readlines()

    cl = Client()
    try:
        cl.login(username, password)
    except Exception as e:
        return f"<h3>Login failed: {e}</h3>"

    try:
        for index, message in enumerate(messages):
            message = message.strip()
            if message:
                cl.direct_send(message, [chat_id])
                print(f"[{index + 1}] Message sent: {message}")
                time.sleep(delay)
    except Exception as e:
        return f"<h3>Error while sending messages: {e}</h3>"

    return "<h3>All messages sent successfully!</h3>"


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)