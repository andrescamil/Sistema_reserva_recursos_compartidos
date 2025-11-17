from django.db import models


class Cliente(models.Model):
    """
    Representa un nodo/cliente del sistema distribuido.
    Nodo A, Nodo B, Nodo C.
    """
    identificador_externo = models.CharField(
        max_length=64,
        unique=True,
        help_text="Identificador del nodo"
    )
    nombre = models.CharField(
        max_length=128,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.nombre or self.identificador_externo


class Recurso(models.Model):
    """
    Recurso compartido: impresora, sala, equipo, etc.
    Aquí se maneja el ESTADO DEL RECURSO (disponible/ocupado).
    """
    ESTADOS_RECURSO = [
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADO', 'Ocupado'),
        ('FUERA_SERVICIO', 'Fuera de servicio'),
    ]

    codigo = models.CharField(
        max_length=64,
        unique=True
    )
    nombre = models.CharField(
        max_length=128,
        blank=True,
        null=True
    )
    descripcion = models.TextField(
        blank=True,
        null=True
    )

   
    estado_recurso = models.CharField(
        max_length=16,
        choices=ESTADOS_RECURSO,
        default='DISPONIBLE'
    )

  
    reserva_actual = models.ForeignKey(
        'Reserva',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recurso_actual_de'
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.nombre or self.codigo


class Reserva(models.Model):
    """
    Representa una SOLICITUD de acceso al recurso por parte de un cliente.
    Aquí se maneja el ESTADO DE LA SOLICITUD (cola, activa, finalizada, etc.)
    y los datos del algoritmo de Lamport.
    """

    # Estado de la solicitud (NO del recurso).
    # Importante: usamos el nombre de campo 'estado'
    # para reutilizar la columna que ya existía en la BD.
    ESTADOS_SOLICITUD = [
        ('EN_COLA', 'En cola'),
        ('ACTIVA', 'Activa'),
        ('FINALIZADA', 'Finalizada'),
        ('CANCELADA', 'Cancelada'),
        ('RECHAZADA', 'Rechazada'),
        ('EXPIRADA', 'Expirada'),
    ]

    recurso = models.ForeignKey(
        Recurso,
        on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE
    )

    # Algoritmo de Lamport
    reloj_lamport = models.BigIntegerField()
    prioridad_id = models.CharField(
        max_length=64,
        help_text="Usado para desempate determinístico entre dos timestamps iguales"
    )

    estado = models.CharField(
        max_length=16,
        choices=ESTADOS_SOLICITUD
    )

    fecha_concesion = models.DateTimeField(
        null=True,
        blank=True
    )
    fecha_liberacion = models.DateTimeField(
        null=True,
        blank=True
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['recurso', 'estado', 'reloj_lamport', 'prioridad_id'],
                name='ix_reservas_cola'
            )
        ]

    def __str__(self):
        return f"{self.recurso} - {self.cliente} ({self.estado})"


class Evento(models.Model):
    """
    Log de eventos del sistema:
    - Solicitudes
    - Concesiones
    - Liberaciones
    - Expiraciones, etc.
    
    Permite auditar el comportamiento del algoritmo distribuido.
    """
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    tipo_evento = models.CharField(
        max_length=32
    )
    ts_cliente = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Timestamp lógico o físico reportado por el cliente "
    )
    ts_servidor = models.DateTimeField(
        auto_now_add=True
    )
    datos = models.JSONField(
        null=True,
        blank=True,
        help_text="Información adicional (por ejemplo, estado anterior/nuevo, nodo, etc.)"
    )

    def __str__(self):
        return f"{self.tipo_evento} - {self.ts_servidor}"