from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps shipment_id to a list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, shipment_id: str):
        await websocket.accept()
        if shipment_id not in self.active_connections:
            self.active_connections[shipment_id] = []
        self.active_connections[shipment_id].append(websocket)

    def disconnect(self, websocket: WebSocket, shipment_id: str):
        if shipment_id in self.active_connections:
            self.active_connections[shipment_id].remove(websocket)
            if not self.active_connections[shipment_id]:
                del self.active_connections[shipment_id]

    async def broadcast(self, shipment_id: str, message: dict):
        if shipment_id in self.active_connections:
            for connection in self.active_connections[shipment_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    print(f"WS send error: {e}")

manager = ConnectionManager()

@router.websocket("/ws/{shipment_id}")
async def websocket_endpoint(websocket: WebSocket, shipment_id: str):
    await manager.connect(websocket, shipment_id)
    try:
        while True:
            # We don't expect messages from client, just holding connection open
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, shipment_id)
