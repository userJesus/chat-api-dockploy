from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
from datetime import datetime
import sys

# Função auxiliar para garantir que o log saia na hora no Docker
def log(msg):
    print(f"[LOG] {msg}", flush=True)

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
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log(f"Conexão aceita. Total ativos: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            log(f"Conexão removida. Total ativos: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        log(f"Enviando broadcast: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                log(f"Erro ao enviar broadcast: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# --- Endpoint de Saúde (Teste HTTP) ---
@app.get("/")
def read_root():
    log("Recebido GET na raiz /")
    return {"status": "Chat API is running", "timestamp": datetime.now().isoformat()}

# --- Endpoint do WebSocket ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    log(f"Nova tentativa de conexão WebSocket de: {client_id}")
    
    try:
        await manager.connect(websocket)
        
        await manager.broadcast({
            "user": "Sistema",
            "message": f"Guest-{client_id} entrou.",
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            data = await websocket.receive_text()
            log(f"Mensagem recebida de {client_id}: {data}")
            
            await manager.broadcast({
                "user": f"Guest-{client_id}",
                "message": data,
                "timestamp": datetime.now().isoformat()
            })
            
    except WebSocketDisconnect:
        log(f"Cliente {client_id} desconectou (WebSocketDisconnect)")
        manager.disconnect(websocket)
        await manager.broadcast({
            "user": "Sistema",
            "message": f"Guest-{client_id} saiu.",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        log(f"Erro CRÍTICO na conexão de {client_id}: {str(e)}")
        manager.disconnect(websocket)
