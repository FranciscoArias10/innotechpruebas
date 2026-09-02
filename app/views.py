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

from app.models import DispositivoRegistrado, VersionAppMovil, PreferenciaNotificacion
from app.serializers import (
    DispositivoRegistroSerializer,
    DispositivoSalidaSerializer,
    VersionAppMovilSerializer,
    PreferenciaNotificacionSerializer,
    FeedbackMovilSerializer,
)
from app.throttling import AppVersionRateThrottle, FeedbackRateThrottle
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


class AppVersionView(APIView):
    """
    GET /api/v1.0.0/movil/app/version/

    Devuelve la información de versión de la aplicación para una plataforma específica.
    """
    permission_classes = []
    throttle_classes = [AppVersionRateThrottle]

    def get(self, request):
        respuesta = RespuestaApi()
        plataforma_param = request.query_params.get('plataforma', 'android').lower()

        if plataforma_param not in dict(VersionAppMovil.PLATAFORMA):
            respuesta.set_success(False)
            respuesta.set_message('Plataforma inválida. Use "android" o "ios".')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        version_info = VersionAppMovil.objects.filter(plataforma=plataforma_param, status=True).first()
        
        if not version_info:
            # Si no hay registro para esa plataforma, devolvemos un valor por defecto.
            # Idealmente debería estar configurado, pero no queremos romper la app.
            version_info = VersionAppMovil(
                plataforma=plataforma_param,
                version_minima='1.0.0',
                version_actual='1.0.0',
                forzar_actualizacion=False
            )

        respuesta.set_success(True)
        respuesta.set_message('Versión recuperada con éxito.')
        respuesta.set_data(VersionAppMovilSerializer(version_info).data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class NotificationPreferencesView(APIView):
    """
    GET|PUT /api/v1.0.0/movil/notifications/preferences/

    Consulta o actualiza las preferencias de notificaciones del usuario autenticado.
    El método PUT permite actualización parcial e idempotente.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        preferencias, _ = PreferenciaNotificacion.objects.get_or_create(usuario=request.user)

        respuesta.set_success(True)
        respuesta.set_message('Preferencias de notificación recuperadas con éxito.')
        respuesta.set_data(PreferenciaNotificacionSerializer(preferencias).data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()

    def put(self, request):
        respuesta = RespuestaApi()
        preferencias, _ = PreferenciaNotificacion.objects.get_or_create(usuario=request.user)

        serializer = PreferenciaNotificacionSerializer(preferencias, data=request.data, partial=True)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Los datos enviados no son válidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            with transaction.atomic():
                serializer.save()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudieron actualizar las preferencias de notificación.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Preferencias de notificación actualizadas con éxito.')
        respuesta.set_data(serializer.data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class FeedbackView(APIView):
    """
    POST /api/v1.0.0/movil/feedback/

    Recibe comentarios, quejas o sugerencias de los usuarios.
    Protegido con un rate limit estricto para evitar spam.
    """
    throttle_classes = [FeedbackRateThrottle]

    def post(self, request):
        respuesta = RespuestaApi()

        serializer = FeedbackMovilSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Los datos enviados no son válidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            with transaction.atomic():
                serializer.save(usuario=request.user)
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudo enviar el feedback.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Feedback enviado con éxito.')
        respuesta.set_data(serializer.data)
        respuesta.set_status(status.HTTP_201_CREATED)
        return respuesta.to_dict()

