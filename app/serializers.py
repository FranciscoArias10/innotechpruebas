# -*- coding: utf-8 -*-
from rest_framework import serializers

from app.models import DispositivoRegistrado


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
