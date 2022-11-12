import asyncio

from typing import Dict
from urllib import request, parse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware  # 引入 CORS 中间件模块

app = FastAPI()

# 设置跨域传参
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],  # 设置允许的origins来源
	allow_credentials=True,
	allow_methods=["*"],  # 设置允许跨域的http方法，比如 get、post、put等。
	allow_headers=["*"])  # 允许跨域的headers，可以用来鉴别来源等作用。


class RoomManager:
	"""Chat Rooms Manager."""
	
	def __init__(self):
		# self.rooms = {
		# 	"room1": {
		# 		"public_key1": "websocket1",
		# 		"public_key2": "websocket2",
		# 	}
		# }
		self.rooms: Dict[str, Dict[str, WebSocket]] = {}
	
	async def connect(self, websocket: WebSocket, room_name: str, public_key: str):
		"""Add a user into specific chat room."""
		await websocket.accept()
		this_room: Dict[str, WebSocket] = self.rooms.get(room_name, {})
		# Designed for two people chat, if room already exists two people, other connection will be refused.
		if len(this_room) == 2:
			return
		this_room[public_key] = websocket
		self.rooms[room_name] = this_room
	
	async def disconnect(self, websocket: WebSocket, room_name: str):
		"""Remove a user from specific chat room."""
		this_room: dict = self.rooms.get(room_name, {})
		for k, v in list(this_room.items()):
			if v == websocket:
				del this_room[k]
		if not this_room:
			del self.rooms[room_name]
	
	async def broadcast_message(self, room_name: str, message: dict, speaker: WebSocket):
		"""Broadcast message to specific chat room."""
		this_room = self.rooms.get(room_name, {})
		for k, v in list(this_room.items()):
			if v is speaker:
				continue
			await v.send_json(message)


room_manager = RoomManager()


@app.websocket("/{room_name}")
async def websocket_endpoint(websocket: WebSocket, room_name: str, public_key: str):
	p = parse.unquote(public_key)
	await room_manager.connect(websocket, room_name, public_key)
	this_room = room_manager.rooms[room_name]
	if len(this_room) == 2:
		for k, v in list(this_room.items()):
			# exchange each other public_key
			if v == websocket:
				await room_manager.broadcast_message(room_name, {"status": "exchange_public_key", "text": k}, websocket)
			else:
				await room_manager.broadcast_message(room_name, {"status": "exchange_public_key", "text": k}, v)
			
			# after exchanged public_key successfully, send two people notices
			if v == websocket:
				await room_manager.broadcast_message(room_name, {"status": "system", "text": "The public keys of both have been exchanged, now you can start chatting"}, websocket)
			else:
				await room_manager.broadcast_message(room_name, {"status": "system", "text": "The public keys of both have been exchanged, now you can start chatting"}, v)
		
	try:
		while True:
			await asyncio.sleep(0.1)
			data: dict = await websocket.receive_json()
			status = data.get("status")
			text = data.get("text")
			if status == "chatting":
				await room_manager.broadcast_message(room_name, {"text": text, "status": status}, websocket)
	
	except WebSocketDisconnect:
		await room_manager.disconnect(websocket, room_name)
		await room_manager.broadcast_message(room_name, {"text": "The other person has left", "status": "left"}, websocket)


if __name__ == "__main__":
	import uvicorn
	
	uvicorn.run(app='main:app', host="0.0.0.0", port=8501, reload=True, debug=True)