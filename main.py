from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Pode restringir para ["https://chat.nicoacademy.com"] se quiser
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Envia o dicionário como JSON para todos
        encoded_message = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(encoded_message)
            except:
                self.disconnect(connection)

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"status": "Chat API 2.0 is running"}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)
    
    # Avisa que entrou
    await manager.broadcast({
        "type": "system",
        "user": "Sistema",
        "content": f"Guest-{client_id} entrou na sala.",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            # Recebe os dados brutos (agora esperamos um JSON string do front)
            raw_data = await websocket.receive_text()
            
            try:
                # Tenta processar como JSON
                payload = json.loads(raw_data)
                
                # Prepara o pacote para enviar para todos
                response = {
                    "user": f"Guest-{client_id}",
                    "timestamp": datetime.now().isoformat()
                }

                # Se for mensagem de texto
                if payload.get("type") == "message":
                    response["type"] = "message"
                    response["content"] = payload.get("content")
                
                # Se for aviso de digitando
                elif payload.get("type") == "typing":
                    response["type"] = "typing"
                    response["is_typing"] = payload.get("is_typing")
                
                # Envia para todos
                await manager.broadcast(response)

            except json.JSONDecodeError:
                # Fallback: Se o front mandar texto puro (versão antiga), trata como mensagem
                await manager.broadcast({
                    "type": "message",
                    "user": f"Guest-{client_id}",
                    "content": raw_data,
                    "timestamp": datetime.now().isoformat()
                })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({
            "type": "system",
            "user": "Sistema",
            "content": f"Guest-{client_id} saiu da sala.",
            "timestamp": datetime.now().isoformat()
        })
