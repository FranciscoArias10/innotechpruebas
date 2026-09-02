# -*- coding: utf-8 -*-
"""
Vistas de la app. ESTO SI VIAJA a sige-ube.

Patron obligatorio, copiado del sistema real:
  - APIView (no ViewSet)
  - permission_classes explicito
  - toda la respuesta sale por RespuestaApi, nunca por Response directo
  - un try/except que traduce el fallo a un mensaje util, no a un 500 pelado
"""
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from app.models import DispositivoRegistrado
from app.serializers import DispositivoRegistroSerializer, DispositivoSalidaSerializer
from sige_ports import RespuestaApi


class DeviceRegisterView(APIView):
    """
    POST /api/v1.0.0/movil/device/register/

    Registra o actualiza el token de notificaciones de un dispositivo.

    Es IDEMPOTENTE: mandar el mismo token dos veces no crea dos filas, actualiza
    la que ya existe. La app movil reintenta al reinstalar y al rotar el token,
    asi que esto no es un lujo.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        respuesta = RespuestaApi()

        entrada = DispositivoRegistroSerializer(data=request.data)
        if not entrada.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Los datos enviados no son válidos.')
            respuesta.set_errors(entrada.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            with transaction.atomic():
                dispositivo, creado = DispositivoRegistrado.objects.update_or_create(
                    usuario=request.user,
                    token=entrada.validated_data['token'],
                    defaults={
                        'plataforma': entrada.plataforma_valor(),
                        'app_version': entrada.validated_data.get('app_version', ''),
                        'modelo_dispositivo': entrada.validated_data.get('modelo_dispositivo', ''),
                        'activo': True,
                    },
                )
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudo registrar el dispositivo.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Dispositivo registrado.' if creado else 'Dispositivo actualizado.')
        respuesta.set_data(DispositivoSalidaSerializer(dispositivo).data)
        respuesta.set_status(status.HTTP_201_CREATED if creado else status.HTTP_200_OK)
        return respuesta.to_dict()
