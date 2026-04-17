import asyncio
import json
from aiohttp import web

PORT = 8000

ROOM_PEERS = {}
ws_room_map = {}

# ---------------- HTML ROUTE ----------------
async def index(request):
    return web.FileResponse("VideoClient.html")

# ---------------- WEBSOCKET ----------------
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    room = None

    async for msg in ws:
        data = json.loads(msg.data)
        action = data.get("action")

        if action == "set_user":
            room = data["room"]
            ws_room_map[ws] = room

            ROOM_PEERS.setdefault(room, []).append(ws)

            is_caller = len(ROOM_PEERS[room]) == 1

            await ws.send_json({
                "action": "set_user_ack",
                "isCaller": is_caller
            })

        elif action in ["offer", "answer", "ice"]:
            room = ws_room_map.get(ws)
            if not room:
                continue

            for peer in ROOM_PEERS.get(room, []):
                if peer != ws:
                    await peer.send_json(data)

    return ws

# ---------------- APP ----------------
app = web.Application()
app.add_routes([
    web.get("/", index),
    web.get("/VideoClient.html", index),
    web.get("/ws", websocket_handler)
])

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)