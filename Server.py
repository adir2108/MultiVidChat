import socket
import threading
import json
import hashlib
import time
import os


HOST = '0.0.0.0'
PORT = 8080

NICKNAMES = {}
CLIENT_ROOM = {}
ROOMS = {
    "lobby": [],
    "room1": [],
    "room2": []
}
CLIENT_STATE = {}
ROOM_MAP = {}
ONLINE_USERS = {}

JSON_FILE = 'chat_data.json'


def init_data():
    if os.path.exists(JSON_FILE) and os.path.getsize(JSON_FILE) > 0:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return data
            except json.JSONDecodeError:
                return {"users": {}, "pms": []}
    else:
        return {"users": {}, "pms": []}


def save_data(data):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


CHAT_DATA = init_data()


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def relay_webrtc_signal(sender_client, payload):
    room = CLIENT_ROOM.get(sender_client)
    if not room:
        return

    sender = ONLINE_USERS.get(sender_client, "Unknown")

    # Construct the signaling message
    data = json.dumps({
        "from": sender,
        "payload": payload
    })

    # Only send the signaling data to the clients in the same room (but not the sender)
    for client in ROOMS.get(room, []):
        if client != sender_client:  # Don't send to the sender
            send_to_client(client, "V|" + data)  # Forward signaling message


def register_user(username, password):
    if username in CHAT_DATA['users']:
        return False

    CHAT_DATA['users'][username] = {'password': hash_password(password)}
    save_data(CHAT_DATA)
    return True


def authenticate_user(username, password):
    user_data = CHAT_DATA['users'].get(username)
    if user_data and user_data['password'] == hash_password(password):
        return True
    return False


def save_pm(sender, recipient, message):
    pm_entry = {
        'sender': sender,
        'recipient': recipient,
        'message': message,
        'timestamp': time.time()
    }
    CHAT_DATA['pms'].append(pm_entry)
    save_data(CHAT_DATA)


def get_pm_history(user1, user2):
    history = []
    for pm in CHAT_DATA['pms']:
        is_relevant = (pm['sender'] == user1 and pm['recipient'] == user2) or \
                      (pm['sender'] == user2 and pm['recipient'] == user1)
        if is_relevant:
            history.append((pm['sender'], pm['message'], pm['timestamp']))
    return history


def send_to_client(client, message):
    try:
        client.send(message.encode('utf-8'))
    except:
        remove_client(client)


def list_rooms_menu(client):
    available_rooms = [name for name in ROOMS.keys() if name != 'lobby']
    room_map = {}
    room_list_str = "Available Rooms:\n"

    for i, name in enumerate(available_rooms):
        room_map[i + 1] = name
        room_list_str += f"{i + 1}. {name} ({len(ROOMS[name])} users)\n"

    create_option_number = len(available_rooms) + 1
    room_map[create_option_number] = 'CREATE_NEW'
    room_list_str += f"{create_option_number}. Create New Room\n"
    room_list_str += "Enter number or type /leave:"

    ROOM_MAP[client] = room_map
    return "M|" + room_list_str, create_option_number


def get_room_members_list(room_name):
    if room_name not in ROOMS or not ROOMS[room_name]:
        return "The room is currently empty."

    member_nicknames = []
    for client in ROOMS[room_name]:
        nickname = ONLINE_USERS.get(client, 'Unknown')
        member_nicknames.append(nickname)

    members_str = f"Members in {room_name} ({len(member_nicknames)}): {', '.join(member_nicknames)}"

    return members_str


def broadcast_to_room(message, room_name, sender_client=None):
    if room_name not in ROOMS:
        return

    for client in ROOMS[room_name]:
        if client != sender_client:
            send_to_client(client, "R|" + message)


def join_room(client, room_name, initial_connect=False):
    username = ONLINE_USERS.get(client, 'Unknown')
    room_name = room_name.strip()

    if client in CLIENT_ROOM and CLIENT_ROOM[client] is not None:
        old_room = CLIENT_ROOM[client]

        if old_room == room_name:
            send_to_client(client, f"I|You are already in {room_name}")
            return

        broadcast_to_room(f'{username} left {old_room}', old_room, client)

        if client in ROOMS[old_room]:
            ROOMS[old_room].remove(client)

        if not ROOMS[old_room] and old_room not in ["lobby", "room1", "room2"]:
            del ROOMS[old_room]
            print(f"Room {old_room} closed.")

    if room_name not in ROOMS:
        ROOMS[room_name] = []
        print(f"Room {room_name} created by {username}.")

    ROOMS[room_name].append(client)
    CLIENT_ROOM[client] = room_name

    join_msg = f'You joined: {room_name}'
    members_list_str = get_room_members_list(room_name)

    message_content = f"\n{join_msg}\n{members_list_str}\n"

    if initial_connect:
        return message_content

    send_to_client(client, "I|" + message_content)
    broadcast_to_room(f'{username} joined {room_name}', room_name, client)


def process_new_room_name(client, room_name):
    room_name = room_name.strip()
    CLIENT_STATE[client] = None

    if not room_name or len(room_name) > 15 or ' ' in room_name:
        send_to_client(client, "E|Invalid room name. Must be 1-15 characters and contain no spaces. Try /join again.")
        return

    if room_name in ROOMS:
        send_to_client(client, f"I|Room '{room_name}' already exists. Connecting now.")

    join_room(client, room_name)


def process_room_selection(client, selection, max_choice):
    room_map = ROOM_MAP.get(client)

    try:
        choice = int(selection.strip())
        if choice < 1 or choice > max_choice:
            raise ValueError
    except ValueError:
        send_to_client(client, f"E|Invalid choice. Enter number (1-{max_choice}) or type /leave:")
        return

    CLIENT_STATE[client] = None
    if client in ROOM_MAP:
        del ROOM_MAP[client]

    selected_action = room_map.get(choice)

    if selected_action == 'CREATE_NEW':
        send_to_client(client, "M|Enter the name for the new room (max 15 chars, no spaces):")
        CLIENT_STATE[client] = ('AWAITING_NEW_ROOM_NAME', None)
    elif selected_action:
        join_room(client, selected_action)
    else:
        send_to_client(client, "E|Error processing selection. Try /join again.")


def process_command(client, command):
    parts = command.split()
    cmd = parts[0].lower()
    username = ONLINE_USERS.get(client, 'Unknown')

    if cmd == '/list':
        room_list_str = "Active Rooms:\n"
        rooms_to_list = [name for name in ROOMS.keys() if name != 'lobby']
        if not rooms_to_list:
            send_to_client(client, "I|No active rooms (other than lobby).")
            return

        for name in rooms_to_list:
            room_list_str += f"- {name} ({len(ROOMS[name])} users)\n"
        room_list_str = room_list_str.strip()
        send_to_client(client, "I|" + room_list_str)

    elif cmd == '/join':
        if len(parts) >= 2:
            room_name = parts[1]
            join_room(client, room_name)
        else:
            room_list_str, max_choice = list_rooms_menu(client)
            CLIENT_STATE[client] = ('AWAITING_ROOM_CHOICE', max_choice)
            send_to_client(client, room_list_str)





    elif cmd == '/call':

        username = ONLINE_USERS.get(client, 'Unknown')

        current_room = CLIENT_ROOM.get(client)

        if not current_room:
            send_to_client(client, "E|You are not in a room! Use /join first.")

            return

        for peer in ROOMS[current_room]:

            if peer != client:
                send_to_client(peer, f"M|{username} wants to start a video call! Type /accept")

        send_to_client(client, "I|Video call request sent to the users in the room.")




    elif cmd == '/accept':

        current_room = CLIENT_ROOM.get(client)

        if not current_room:
            send_to_client(client, "E|You are not in a room! Use /join first.")

            return

        bridge_ip = "192.168.4.70"  # host running bridge + HTTP server

        # Send to all peers to open the video page via HTTP

        for peer in ROOMS[current_room]:
            send_to_client(peer, f"V|OPEN_VIDEO|{bridge_ip}")

        send_to_client(client, "S|Call accepted. Opening video chat...")




    elif cmd == '/reject':
        username = ONLINE_USERS.get(client, 'Unknown')
        current_room = CLIENT_ROOM.get(client)

        if not current_room:
            send_to_client(client, "E|You are not in a room! Use /join first.")
            return

        send_to_client(client, "S|You rejected the video call.")



    elif cmd == '/leave':
        if CLIENT_ROOM.get(client) == "lobby":
            send_to_client(client, "I|You are already in the lobby.")
            return

        join_room(client, "lobby")

    elif cmd == '/pm':
        if len(parts) < 3:
            send_to_client(client, "E|USAGE: /pm <recipient_username> <message>")
            return

        recipient = parts[1]
        message = ' '.join(parts[2:])

        save_pm(username, recipient, message)

        recipient_socket = next((sock for sock, user in ONLINE_USERS.items() if user == recipient), None)

        pm_to_sender = f"PM sent to {recipient}: {message}"
        send_to_client(client, "O|" + pm_to_sender)

        if recipient_socket:
            pm_to_recipient = f"PM from {username}: {message}"
            send_to_client(recipient_socket, "P|" + pm_to_recipient)
        else:
            send_to_client(client, f"I|{recipient} is offline. Message saved.")

    elif cmd == '/history':
        if len(parts) < 2:
            send_to_client(client, "E|USAGE: /history <username>")
            return

        target_user = parts[1]
        history = get_pm_history(username, target_user)

        if not history:
            send_to_client(client, f"I|No private message history with {target_user}.")
            return

        hist_str = f"PM History with {target_user}:\n"
        for sender, msg, timestamp in history:
            time_str = time.strftime('%H:%M', time.localtime(timestamp))
            prefix = "-> " if sender == username else "<- "
            hist_str += f"[{time_str}] {prefix}{sender}: {msg}\n"
        hist_str = hist_str.strip()
        send_to_client(client, "I|" + hist_str)

    else:
        send_to_client(client, "E|Unknown command. Available: /list, /join, /leave, /pm, /history")


def remove_client(client):
    if client not in ONLINE_USERS:
        return

    username = ONLINE_USERS[client]
    current_room = CLIENT_ROOM.get(client)

    if current_room and current_room in ROOMS:
        if client in ROOMS[current_room]:
            ROOMS[current_room].remove(client)
            broadcast_to_room(f'{username} disconnected.', current_room, client)

        if not ROOMS[current_room] and current_room not in ["lobby", "room1", "room2"]:
            del ROOMS[current_room]
            print(f"Room {current_room} closed.")

    if client in CLIENT_ROOM:
        del CLIENT_ROOM[client]
    if client in CLIENT_STATE:
        del CLIENT_STATE[client]
    if client in ROOM_MAP:
        del ROOM_MAP[client]
    if client in ONLINE_USERS:
        del ONLINE_USERS[client]

    client.close()
    print(f'{username} disconnected.')


def handle_client(client):
    try:
        send_to_client(client, 'T|Welcome. Type 1 to Register, 2 to Login.')

        while True:
            message = client.recv(1024).decode('utf-8').strip()

            if not message: continue

            auth_choice = message

            if auth_choice == '1':
                send_to_client(client, 'T|Enter desired username:')
                username = client.recv(1024).decode('utf-8').strip()
                send_to_client(client, 'T|Enter password:')
                password = client.recv(1024).decode('utf-8').strip()

                if register_user(username, password):
                    send_to_client(client, 'S|Registration successful. Logging in...')
                    break
                else:
                    send_to_client(client, 'F|Username taken. Try again (1/2):')

            elif auth_choice == '2':
                send_to_client(client, 'T|Enter username:')
                username = client.recv(1024).decode('utf-8').strip()
                send_to_client(client, 'T|Enter password:')
                password = client.recv(1024).decode('utf-8').strip()

                if authenticate_user(username, password):
                    if username in ONLINE_USERS.values():
                        send_to_client(client, 'F|User already logged in. Try again (1/2):')
                        continue
                    send_to_client(client, 'S|Login successful.')
                    break
                else:
                    send_to_client(client, 'F|Invalid credentials. Try again (1/2):')
            else:
                send_to_client(client, 'F|Invalid choice. Type 1 or 2:')

        ONLINE_USERS[client] = username

        DEFAULT_ROOM = "lobby"
        initial_join_msg_content = join_room(client, DEFAULT_ROOM, initial_connect=True)

        lobby_message_content = (
            f"Welcome, {username}!\n"
            "You can start chatting immediately.\n"
            "\n--- COMMANDS ---"
            "\n/list\n/join <room>\n/leave\n/pm <user> <msg>\n/history <user>\n/call"
        )

        full_welcome_message = initial_join_msg_content + lobby_message_content
        send_to_client(client, "I|" + full_welcome_message)

        while True:
            message = client.recv(1024).decode('utf-8').strip()

            if not message: continue

            state_info = CLIENT_STATE.get(client)

            if state_info and state_info[0] == 'AWAITING_ROOM_CHOICE':
                process_room_selection(client, message, state_info[1])
                continue

            elif state_info and state_info[0] == 'AWAITING_NEW_ROOM_NAME':
                process_new_room_name(client, message)
                continue

            if message.startswith("WEBRTC|"):
                try:
                    payload = json.loads(message[len("WEBRTC|"):])
                    relay_webrtc_signal(client, payload)
                except json.JSONDecodeError:
                    pass
                continue

            if message.startswith('/'):
                process_command(client, message)
            else:
                current_room = CLIENT_ROOM.get(client)
                if current_room:
                    formatted_message = f'{username}: {message}'
                    broadcast_to_room(formatted_message, current_room, client)

    except Exception as e:
        print(f"Error handling client {ONLINE_USERS.get(client, 'Unknown')}: {e}")
        remove_client(client)


def receive():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        client, address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()


if __name__ == '__main__':
    receive()