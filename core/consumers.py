from channels.generic.websocket import AsyncJsonWebsocketConsumer


class SyncConsumer(AsyncJsonWebsocketConsumer):
    """Har bir ochiq sahifa shu kanalga ulanadi: kimdir o'zgartirsa, hammaga yangi rev raqami boradi."""

    group = "sync"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_active:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("t") == "ping":
            await self.send_json({"t": "pong"})

    async def rev(self, event):
        await self.send_json({"t": "rev", "rev": event["rev"]})
