from channels.generic.websocket import AsyncWebsocketConsumer
import json

class RecursoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.recurso_id = self.scope['url_route']['kwargs']['recurso_id']
        self.group_name = f"recurso_{self.recurso_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Recibe mensajes desde GestorRecursos._notificar_cambio_cola
    async def cola_actualizada(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'cola_actualizada',
            'recurso_id': event['recurso_id'],
        }))