# -*- coding: utf-8 -*-
from rest_framework import serializers

from app.models import DispositivoRegistrado, VersionAppMovil, PreferenciaNotificacion, FeedbackMovil


class DispositivoRegistroSerializer(serializers.Serializer):
    """Valida el cuerpo de POST /movil/device/register/."""

    token = serializers.CharField(max_length=255, allow_blank=False)
    plataforma = serializers.ChoiceField(choices=['android', 'ios'])
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    modelo_dispositivo = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')

    _MAPA = {'android': DispositivoRegistrado.ANDROID, 'ios': DispositivoRegistrado.IOS}

    def plataforma_valor(self):
        return self._MAPA[self.validated_data['plataforma']]


class DispositivoSalidaSerializer(serializers.ModelSerializer):
    """Forma de la respuesta. Es el contrato: si cambia, cambia el OpenAPI."""

    plataforma = serializers.CharField(source='get_plataforma_display')

    class Meta:
        model = DispositivoRegistrado
        fields = ('id', 'plataforma', 'app_version', 'modelo_dispositivo', 'activo')


class VersionAppMovilSerializer(serializers.ModelSerializer):
    """Contrato de salida para /movil/app/version/"""

    class Meta:
        model = VersionAppMovil
        fields = ('plataforma', 'version_minima', 'version_actual', 'forzar_actualizacion')


class PreferenciaNotificacionSerializer(serializers.ModelSerializer):
    """Contrato de entrada (PUT parcial) y salida (GET/PUT) para /movil/notifications/preferences/."""

    push_enabled = serializers.BooleanField(required=False)
    grades = serializers.BooleanField(required=False)
    attendance = serializers.BooleanField(required=False)
    events = serializers.BooleanField(required=False)
    announcements = serializers.BooleanField(required=False)
    tasks = serializers.BooleanField(required=False)

    class Meta:
        model = PreferenciaNotificacion
        fields = ('push_enabled', 'grades', 'attendance', 'events', 'announcements', 'tasks')


class FeedbackMovilSerializer(serializers.ModelSerializer):
    """Contrato de entrada para POST /movil/feedback/."""

    mensaje = serializers.CharField(
        max_length=2000,
        min_length=3,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'blank': 'El mensaje no puede estar vacío.',
            'max_length': 'El mensaje no puede exceder los 2000 caracteres.',
            'min_length': 'El mensaje debe tener al menos 3 caracteres.',
        }
    )

    class Meta:
        model = FeedbackMovil
        fields = ('tipo', 'mensaje')


class ForoPostMensajeSerializer(serializers.Serializer):
    """Valida el cuerpo para publicar o editar un aporte en un foro."""

    mensaje = serializers.CharField(
        max_length=5000,
        min_length=1,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'blank': 'El mensaje del aporte no puede estar vacío.',
            'required': 'El campo mensaje es obligatorio.',
            'max_length': 'El mensaje no puede exceder los 5000 caracteres.',
        }
    )


class ConsultaDocenteCrearSerializer(serializers.Serializer):
    """Valida el cuerpo para enviar una nueva consulta privada al docente."""

    asunto = serializers.CharField(
        max_length=255,
        min_length=2,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'blank': 'El asunto no puede estar vacío.',
            'required': 'El campo asunto es obligatorio.',
            'max_length': 'El asunto no puede exceder los 255 caracteres.',
        }
    )
    pregunta = serializers.CharField(
        max_length=5000,
        min_length=3,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'blank': 'El detalle de la pregunta no puede estar vacío.',
            'required': 'El campo pregunta es obligatorio.',
            'max_length': 'La pregunta no puede exceder los 5000 caracteres.',
        }
    )

class SolicitudServicioCrearSerializer(serializers.Serializer):
    """Valida el cuerpo para registrar una nueva solicitud en el Balcón de Servicios (Tarea 16)."""

    tipo = serializers.ChoiceField(
        choices=['CERTIFICADO', 'JUSTIFICACION_FALTA', 'EVALUACION_ATRASADA', 'OTRO_TRAMITE'],
        error_messages={'invalid_choice': 'El tipo de solicitud seleccionado no es válido.'}
    )
    subtipo_certificado = serializers.CharField(
        max_length=60,
        required=False,
        allow_blank=True,
        default=''
    )
    materia_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None
    )
    motivo = serializers.CharField(
        max_length=255,
        min_length=3,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'blank': 'El motivo de la solicitud no puede estar vacío.',
            'required': 'El campo motivo es obligatorio.',
            'max_length': 'El motivo no puede exceder los 255 caracteres.',
            'min_length': 'El motivo debe tener al menos 3 caracteres.',
        }
    )
    motivo_detalle = serializers.CharField(
        max_length=5000,
        required=False,
        allow_blank=True,
        default=''
    )
    falta_desde = serializers.DateField(
        required=False,
        allow_null=True,
        default=None
    )
    falta_hasta = serializers.DateField(
        required=False,
        allow_null=True,
        default=None
    )
    fecha_evaluacion = serializers.DateField(
        required=False,
        allow_null=True,
        default=None
    )
    modalidad_evaluacion = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        default=''
    )


class DocumentoEstudianteSubirSerializer(serializers.Serializer):
    """Valida los metadatos para subir un documento del estudiante requerido por Secretaría (Tarea 16)."""

    tipo_id = serializers.IntegerField(
        min_value=1,
        error_messages={'required': 'El tipo de documento es obligatorio.'}
    )
    observacion = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default=''
    )

