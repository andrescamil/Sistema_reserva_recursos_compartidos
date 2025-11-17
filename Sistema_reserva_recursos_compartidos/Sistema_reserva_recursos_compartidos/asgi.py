"""
ASGI config for Sistema_reserva_recursos_compartidos project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack


import reservas.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Sistema_reserva_recursos_compartidos.settings')

django_asgi_app = get_asgi_application()

django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

application = ProtocolTypeRouter({
    "http": django_asgi_app,   # peticiones normales HTTP
    "websocket": AuthMiddlewareStack(
        URLRouter(
            reservas.routing.websocket_urlpatterns
        )
    ),
})
