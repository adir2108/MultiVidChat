import asyncio
import websockets
import json

ROOM_PEERS = {}

async def handler(ws):
    room = None
    username = None

    async for msg in ws:
        data = json.loads(msg)
        action = data.get("action")

        if action == "set_user":
            username = data["username"]
            room = data["room"]

            if room not in ROOM_PEERS:
                ROOM_PEERS[room] = []
            ROOM_PEERS[room].append(ws)

            # מי הראשון בחדר יהיה caller
            is_caller = len(ROOM_PEERS[room]) == 1
            await ws.send(json.dumps({"action": "set_user_ack", "isCaller": is_caller}))

        elif action in ["offer", "answer", "ice"]:
            for peer in ROOM_PEERS.get(room, []):
                if peer != ws:
                    await peer.send(json.dumps(data))

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("WebSocket server running on port 8765")
        await asyncio.Future()  # run forever

asyncio.run(main())
