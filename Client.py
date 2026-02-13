import socket
import threading
import sys
import os
import webbrowser
import json

HOST = '192.168.4.96'
PORT = 8080

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def prompt_input(prompt_char="> "):
    sys.stdout.write(f"\n{prompt_char}")
    sys.stdout.flush()

# מיקום HTML עם הוידאו
VIDEO_HTML = os.path.abspath("VideoClient.html")

def open_video_chat():
    try:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
        webbrowser.get('chrome').open(f"file:///{VIDEO_HTML}")
    except Exception as e:
        print(f"Failed to open browser: {e}")


def receive(client):
    while True:
        try:
            full_message = client.recv(1024).decode('utf-8')
            if not full_message: continue

            parts = full_message.split('|', 1)
            msg_type = parts[0]
            message = parts[1] if len(parts) > 1 else ""

            sys.stdout.write('\r' + ' ' * 80 + '\r')

            if msg_type == 'T':
                print(f"{message}", end='')
            elif msg_type == 'F':
                print(f"\n{message}\n")
            elif msg_type == 'S':
                print(f"\n{message}")
            elif msg_type == 'V':
                if message == "OPEN_VIDEO":
                    open_video_chat()
            elif msg_type == 'E':
                print(f"\n{message}\n")
            elif msg_type == 'M':
                print(f"\n{message}")
            elif msg_type == 'I':
                print(f"{message}")
            elif msg_type == 'P':
                print(f"** {message} **")
            elif msg_type == 'O':
                print(f"({message})")
            elif msg_type == 'R':
                print(message)

            prompt_input()

        except Exception:
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            print("\n*** Disconnected from Server ***")
            client.close()
            break

def write(client):
    while True:
        try:
            message = input()
            if message:
                client.send(message.encode('utf-8'))
            prompt_input()
        except EOFError:
            print("\nClosing connection...")
            client.close()
            break
        except Exception:
            break

clear_console()
print("Connecting...")
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client.connect((HOST, PORT))
except ConnectionRefusedError:
    print("Cannot connect to server.")
    exit()

receive_thread = threading.Thread(target=receive, args=(client,))
receive_thread.start()

write_thread = threading.Thread(target=write, args=(client,))
write_thread.start()
