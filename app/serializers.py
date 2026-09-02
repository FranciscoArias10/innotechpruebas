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

    class Meta:
        model = FeedbackMovil
        fields = ('tipo', 'mensaje')
