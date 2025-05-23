from channels.generic.websocket import WebsocketConsumer
from .models import Conversation, Message
from django.template.loader import render_to_string
import json
from asgiref.sync import async_to_sync


class ConversationConsumer(WebsocketConsumer):
    def connect(self):

        self.user = self.scope["user"]
        conversation_name = self.scope["url_route"]["kwargs"]["name"]

        self.conversation = Conversation.objects.get(name=conversation_name)
        async_to_sync(self.channel_layer.group_add)(
            self.conversation.name, self.channel_name
        )

        if self.user not in self.conversation.users_online.all():
            self.conversation.users_online.add(self.user)
            self.update_online_count()

        self.accept()

    def disconnect(self, close_code):
        if self.user in self.conversation.users_online.all():
            self.conversation.users_online.remove(self.user)
            self.update_online_count()

        async_to_sync(self.channel_layer.group_discard)(
            self.conversation.name, self.channel_name
        )

    def receive(self, text_data):
        data = json.loads(text_data)
        message_string = data["message"]
        message = Message.objects.create(
            message=message_string, conversation=self.conversation, from_user=self.user
        )

        event = {"type": "message_handler", "message_id": message.id}

        async_to_sync(self.channel_layer.group_send)(self.conversation.name, event)

    def message_handler(self, event):
        message = Message.objects.get(pk=event["message_id"])
        context = {"message": message, "user": self.user}
        html = render_to_string(
            "chat/conversation.html#hx-chat-bubble", context=context
        )
        self.send(text_data=html)

    def update_online_count(self):

        online_count = self.conversation.users_online.count()
        event = {"type": "handle_online_count_changed", "online_count": online_count}
        async_to_sync(self.channel_layer.group_send)(self.conversation.name, event)

    def handle_online_count_changed(self, event):
        online_count = event["online_count"]

        context = {"online_count": online_count}
        html = render_to_string(
            "chat/conversation.html#hx-users-online", context=context
        )
        self.send(text_data=html)
