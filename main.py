from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import json
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        # Agora armazenamos ID -> WebSocket para saber quem é quem
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast(self, message: dict):
        # Envia para todos
        encoded_message = json.dumps(message)
        for connection in self.active_connections.values():
            try:
                await connection.send_text(encoded_message)
            except:
                pass # Se falhar, o disconnect lida depois

    def get_all_users(self):
        return list(self.active_connections.keys())

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"status": "Chat API with Video Relay is running"}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    user_id = f"Guest-{client_id}"
    await manager.connect(websocket, user_id)
    
    # 1. Avisa a todos que entrou (Sistema)
    await manager.broadcast({
        "type": "system",
        "user": "Sistema",
        "content": f"{user_id} entrou na sala.",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            
            try:
                payload = json.loads(raw_data)
                
                # Base da resposta
                response = {
                    "user": user_id,
                    "timestamp": datetime.now().isoformat()
                }

                msg_type = payload.get("type")

                # --- Lógica de Chat ---
                if msg_type == "message":
                    response["type"] = "message"
                    response["content"] = payload.get("content")
                    await manager.broadcast(response)
                
                elif msg_type == "typing":
                    response["type"] = "typing"
                    response["is_typing"] = payload.get("is_typing")
                    await manager.broadcast(response)

                # --- Lógica de Vídeo (O PULO DO GATO) ---
                
                elif msg_type == "join-room":
                    # Quando alguém entra no vídeo, enviamos a lista de quem já está lá SÓ PRA ELE
                    active_users = manager.get_all_users()
                    # Responde apenas para quem pediu (unicast simulado via socket atual)
                    await websocket.send_text(json.dumps({
                        "type": "all-users",
                        "users": active_users
                    }))
                    # Avisa os outros que ele chegou
                    await manager.broadcast({
                        "type": "user-joined",
                        "id": user_id
                    })

                elif msg_type == "signal":
                    # Repassa o sinal WebRTC (Sinalização)
                    # O payload tem { type: "signal", target: "Guest-XYZ", signal: {...} }
                    response["type"] = "signal"
                    response["target"] = payload.get("target") # CRÍTICO: Repassar o alvo
                    response["signal"] = payload.get("signal")
                    response["from"] = user_id # Quem está mandando
                    await manager.broadcast(response)

                elif msg_type == "leave-room":
                    await manager.broadcast({
                        "type": "user-left-video",
                        "id": user_id
                    })
                
                else:
                    # Fallback: Se não conhecemos o tipo, repassamos tudo (segurança)
                    response.update(payload)
                    await manager.broadcast(response)

            except json.JSONDecodeError:
                pass
            
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast({
            "type": "system",
            "user": "Sistema",
            "content": f"{user_id} saiu da sala.",
            "timestamp": datetime.now().isoformat()
        })
        # Avisa para remover o vídeo também
        await manager.broadcast({
            "type": "user-left-video",
            "id": user_id
        })
