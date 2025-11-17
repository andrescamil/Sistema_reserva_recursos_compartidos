from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Recurso, Reserva, Evento, Cliente


class GestorRecursos:
    """
    Servicio central que implementa:
    - Relojes de Lamport para ordenar solicitudes.
    - Exclusión mutua: solo 1 reserva ACTIVA por recurso.
    - Manejo de cola: EN_COLA -> ACTIVA -> FINALIZADA.
    - Registro de eventos (log) en la tabla Evento.
    """

    # ----------------------------------------------------------------------
    # 1) SOLICITAR RESERVA
    # ----------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def solicitar_reserva(recurso_id: int, cliente: Cliente, ts_cliente: int) -> Reserva:
        """
        Crea una nueva solicitud de reserva para un recurso.

        - Calcula el reloj de Lamport: max(ts_cliente, último_ts) + 1
        - Si el recurso está DISPONIBLE -> reserva ACTIVA y recurso OCUPADO.
        - Si el recurso está OCUPADO -> reserva EN_COLA.
        - Registra un Evento de tipo 'SOLICITUD'.
        - Notifica por WebSocket que la cola del recurso cambió.
        """
        # Bloquea el recurso para evitar condiciones de carrera
        recurso = Recurso.objects.select_for_update().get(id=recurso_id)

        # === Reloj de Lamport ============================================
        # Busca el mayor reloj_lamport existente para este recurso
        last_ts = Reserva.objects.filter(recurso=recurso).aggregate(
            Max('reloj_lamport')
        )['reloj_lamport__max'] or 0

        # Nuevo timestamp lógico
        reloj_lamport = max(ts_cliente or 0, last_ts) + 1

        # prioridad_id: algo único del nodo/cliente (para desempatar)
        prioridad_id = cliente.identificador_externo

        # === Exclusión mutua ============================================
        # Si el recurso está disponible, esta reserva entra ACTIVA
        # y el recurso pasa a OCUPADO.
        if recurso.estado_recurso == 'DISPONIBLE':
            estado = 'ACTIVA'
            recurso.estado_recurso = 'OCUPADO'
        else:
            # Si no está disponible, la solicitud va a la cola
            estado = 'EN_COLA'

        # Crea la reserva
        reserva = Reserva.objects.create(
            recurso=recurso,
            cliente=cliente,
            reloj_lamport=reloj_lamport,
            prioridad_id=prioridad_id,
            estado=estado,
            fecha_concesion=timezone.now() if estado == 'ACTIVA' else None,
        )

        # Si quedó ACTIVA, marca la reserva_actual del recurso
        if estado == 'ACTIVA':
            recurso.reserva_actual = reserva

        recurso.save()

        # Registra eñ evento en el log
        Evento.objects.create(
            reserva=reserva,
            tipo_evento='SOLICITUD',
            ts_cliente=ts_cliente,
            datos={
                'accion': 'solicitar',
                'estado_resultante': estado,
                'reloj_lamport': reloj_lamport,
                'prioridad_id': prioridad_id,
                'cliente': cliente.identificador_externo,
                'recurso': recurso.codigo,
            }
        )

        # Notifica a todos los clientes suscritos a este recurso
        GestorRecursos._notificar_cambio_cola(recurso.id)

        return reserva

    # ----------------------------------------------------------------------
    # 2) LIBERAR RESERVA
    # ----------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def liberar_reserva(recurso_id: int, cliente: Cliente) -> Reserva | None:
        """
        Libera la reserva ACTIVA de un cliente sobre un recurso.

        - Cambia la reserva ACTIVA -> FINALIZADA.
        - Pone el recurso en DISPONIBLE.
        - Busca el siguiente EN_COLA según (reloj_lamport, prioridad_id)
          y lo pasa a ACTIVA, marcando el recurso como OCUPADO otra vez.
        - Registra Eventos de LIBERACION y, si corresponde, de CONCESION.
        - Notifica por WebSocket que la cola cambió.
        """
        recurso = Recurso.objects.select_for_update().get(id=recurso_id)

        # Busca la reserva ACTIVA de este cliente para este recurso
        reserva = Reserva.objects.filter(
            recurso=recurso,
            cliente=cliente,
            estado='ACTIVA'
        ).order_by('-fecha_creacion').first()

        if not reserva:
            # No hay nada activo para este cliente en este recurso
            return None

        # Marca la reserva como FINALIZADA
        reserva.estado = 'FINALIZADA'
        reserva.fecha_liberacion = timezone.now()
        reserva.save()

        # El recurso momentáneamente queda disponible
        recurso.estado_recurso = 'DISPONIBLE'
        recurso.reserva_actual = None

        # Registra eñ evento de liberación
        Evento.objects.create(
            reserva=reserva,
            tipo_evento='LIBERACION',
            datos={
                'accion': 'liberar',
                'cliente': cliente.identificador_externo,
                'recurso': recurso.codigo,
            }
        )

        # ------------------------------------------------------------------
        # Promover siguiente en cola a ACTIVA según Lamport
        # ------------------------------------------------------------------
        siguiente = Reserva.objects.filter(
            recurso=recurso,
            estado='EN_COLA'
        ).order_by('reloj_lamport', 'prioridad_id').first()

        if siguiente:
            siguiente.estado = 'ACTIVA'
            siguiente.fecha_concesion = timezone.now()
            siguiente.save()

            recurso.estado_recurso = 'OCUPADO'
            recurso.reserva_actual = siguiente

            Evento.objects.create(
                reserva=siguiente,
                tipo_evento='CONCESION',
                datos={
                    'accion': 'conceder_desde_cola',
                    'cliente': siguiente.cliente.identificador_externo,
                    'recurso': recurso.codigo,
                    'reloj_lamport': siguiente.reloj_lamport,
                    'prioridad_id': siguiente.prioridad_id,
                }
            )

        recurso.save()

        # Notifica a todos los clientes suscritos a este recurso
        GestorRecursos._notificar_cambio_cola(recurso.id)

        return reserva

    # ----------------------------------------------------------------------
    # 3) NOTIFICACIÓN EN TIEMPO REAL (WebSocket)
    # ----------------------------------------------------------------------
    @staticmethod
    def _notificar_cambio_cola(recurso_id: int) -> None:
        """
        Envía un mensaje por Channels a todos los WebSockets suscritos al grupo
        'recurso_<id>' para que actualicen la cola en tiempo real.

        El consumer RecursoConsumer recibirá un evento del tipo 'cola_actualizada'
        y desde el frontend se volverá a llamar a la API GET /api/recursos/<id>/cola/
        para refrescar la lista.
        """
        channel_layer = get_channel_layer()
        if channel_layer is None:
            # Por si Channels no está configurado
            return

        async_to_sync(channel_layer.group_send)(
            f"recurso_{recurso_id}",
            {
                "type": "cola.actualizada",  # se mapea a metodo cola_actualizada en el consumer
                "recurso_id": recurso_id,
            }
        )