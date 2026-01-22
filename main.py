from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
from datetime import datetime

app = FastAPI()

# Configuração de CORS (Permite que o front-end no v0 conecte aqui)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, idealmente restrinja para o domínio do seu front
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gerenciador de Conexões (Na memória)
class ConnectionManager:
    def __init__(self):
        # Lista de sockets ativos
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Envia a mensagem para todos os conectados
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                # Se falhar ao enviar, assume que caiu e remove
                self.disconnect(connection)

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"status": "Chat API is running"}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)
    
    # Notifica que alguém entrou
    await manager.broadcast({
        "user": "Sistema",
        "message": f"Guest-{client_id} entrou na sala.",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            # Espera receber mensagem do cliente
            data = await websocket.receive_text()
            
            # Reenvia para todos (Broadcast)
            await manager.broadcast({
                "user": f"Guest-{client_id}",
                "message": data,
                "timestamp": datetime.now().isoformat()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({
            "user": "Sistema",
            "message": f"Guest-{client_id} saiu da sala.",
            "timestamp": datetime.now().isoformat()
        })