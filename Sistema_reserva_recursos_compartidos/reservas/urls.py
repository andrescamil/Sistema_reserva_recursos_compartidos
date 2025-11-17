from django.urls import path
from . import views
from . import views_auth

urlpatterns = [
    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout'),
    path('registro/', views_auth.register_view, name='registro'),
    # Frontend
    path('', views.seleccionar_cliente, name='seleccionar_cliente'),
    path('cliente/<int:cliente_id>/recursos/', views.lista_recursos, name='lista_recursos'),
    path('cliente/<int:cliente_id>/recurso/<int:recurso_id>/', views.detalle_recurso, name='detalle_recurso'),

    # API JSON
    path('api/recursos/<int:recurso_id>/cola/', views.cola_recurso, name='cola_recurso'),
    path('api/recursos/<int:recurso_id>/solicitar/', views.solicitar_reserva_api, name='solicitar_reserva_api'),
    path('api/recursos/<int:recurso_id>/liberar/', views.liberar_reserva_api, name='liberar_reserva_api'),
]