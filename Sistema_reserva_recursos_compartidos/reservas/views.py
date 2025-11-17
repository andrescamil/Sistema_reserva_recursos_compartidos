from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .models import Cliente, Recurso, Reserva
from .services import GestorRecursos
import json


# ----------------------------------------------------------------------
# FRONTEND (templates)
# ----------------------------------------------------------------------

def seleccionar_cliente(request):
    """
    Pantalla inicial para escoger el nodo/cliente.
    (Versión sin login: se elige un Cliente existente).
    """
    clientes = Cliente.objects.all()
    return render(request, 'reservas/seleccionar_cliente.html', {
        'clientes': clientes
    })


def lista_recursos(request, cliente_id):
    """
    Lista de recursos para un cliente dado (simula nodo A/B/C).
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    recursos = Recurso.objects.all()
    return render(request, 'reservas/lista_recursos.html', {
        'cliente': cliente,
        'recursos': recursos
    })


def detalle_recurso(request, cliente_id, recurso_id):
    """
    Detalle de un recurso:
    - Botones para solicitar / liberar.
    - La cola se carga por JS usando la API /api/recursos/<id>/cola/
      y se actualiza en tiempo real vía WebSocket.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    recurso = get_object_or_404(Recurso, id=recurso_id)
    return render(request, 'reservas/detalle_recurso.html', {
        'cliente': cliente,
        'recurso': recurso
    })


# ----------------------------------------------------------------------
# API JSON
# ----------------------------------------------------------------------

def cola_recurso(request, recurso_id):
    """
    Devuelve la cola de reservas para un recurso en formato JSON.

    Solo se listan:
    - EN_COLA: solicitudes en espera
    - ACTIVA: la que actualmente tiene el recurso

    Orden: (reloj_lamport, prioridad_id) para mostrar el algoritmo de Lamport.
    """
    if request.method != 'GET':
        return HttpResponseBadRequest("Método no permitido")

    reservas = Reserva.objects.filter(
        recurso_id=recurso_id,
        estado__in=['EN_COLA', 'ACTIVA']
    ).order_by('reloj_lamport', 'prioridad_id')

    data = [
        {
            'id': r.id,
            'cliente': r.cliente.nombre or r.cliente.identificador_externo,
            'estado': r.estado,  # EN_COLA o ACTIVA
            'reloj_lamport': r.reloj_lamport,
            'prioridad_id': r.prioridad_id,
        }
        for r in reservas
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
def solicitar_reserva_api(request, recurso_id):
    """
    Endpoint para que un cliente solicite un recurso.

    Espera JSON:
    {
      "cliente_id": <int>,
      "ts_cliente": <int>  // timestamp lógico o Date.now() desde el navegador
    }
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Método no permitido")

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido")

    cliente_id = payload.get('cliente_id')
    ts_cliente = int(payload.get('ts_cliente', 0))

    if not cliente_id:
        return HttpResponseBadRequest("cliente_id es requerido")

    cliente = get_object_or_404(Cliente, id=cliente_id)

    reserva = GestorRecursos.solicitar_reserva(recurso_id, cliente, ts_cliente)
    return JsonResponse({
        'reserva_id': reserva.id,
        'estado': reserva.estado,
    })


@csrf_exempt
def liberar_reserva_api(request, recurso_id):
    """
    Endpoint para que un cliente libere su reserva ACTIVA sobre un recurso.

    Espera JSON:
    {
      "cliente_id": <int>
    }
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Método no permitido")

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("JSON inválido")

    cliente_id = payload.get('cliente_id')

    if not cliente_id:
        return HttpResponseBadRequest("cliente_id es requerido")

    cliente = get_object_or_404(Cliente, id=cliente_id)
    reserva = GestorRecursos.liberar_reserva(recurso_id, cliente)

    return JsonResponse({
        'ok': True,
        'liberada': bool(reserva),
    })