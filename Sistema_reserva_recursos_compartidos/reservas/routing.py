from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/recursos/(?P<recurso_id>\d+)/$', consumers.RecursoConsumer.as_asgi()),
]