import asyncio
import websockets
import json
import threading
from http.server import SimpleHTTPRequestHandler
from socketserver import ThreadingTCPServer



ROOM_PEERS = {}
ws_room_map = {}  # NEW: track each ws -> room

async def handler(ws):
    room = None
    username = None

    async for msg in ws:
        data = json.loads(msg)
        action = data.get("action")

        if action == "set_user":
            username = data["username"]
            room = data["room"]

            ws_room_map[ws] = room   # <-- store room for this websocket

            if room not in ROOM_PEERS:
                ROOM_PEERS[room] = []
            ROOM_PEERS[room].append(ws)

            is_caller = len(ROOM_PEERS[room]) == 1
            await ws.send(json.dumps({"action": "set_user_ack", "isCaller": is_caller}))

        elif action in ["offer", "answer", "ice"]:
            room_of_ws = ws_room_map.get(ws)
            if room_of_ws is None:
                continue
            for peer in ROOM_PEERS.get(room_of_ws, []):
                if peer != ws:
                    await peer.send(json.dumps(data))

def start_http():
    handler = SimpleHTTPRequestHandler
    httpd = ThreadingTCPServer(("0.0.0.0", 8000), handler)
    print("HTTP server running on port 8000")
    httpd.serve_forever()


async def main():
    threading.Thread(target=start_http, daemon=True).start()

    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("WebSocket server running on port 8765")
        await asyncio.Future()  # run forever

asyncio.run(main())
