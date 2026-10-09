# -*- coding: utf-8 -*-
"""
Vistas de periodos. ESTO SI VIAJA a sige-ube.

Endpoints implementados:
  GET period/           -- Lista todos los periodos activos
  GET period/active/    -- Devuelve el periodo activo actual
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from sige_ports import RespuestaApi
from app.auth_ports import obtener_periodos_usuario, obtener_periodo_activo_id


class PeriodListView(APIView):
    """
    GET /api/v1.0.0/period/

    Devuelve todos los periodos disponibles para el usuario autenticado.
    La lista viene de ctr_periodo (via auth_ports).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        try:
            periodos = obtener_periodos_usuario(request.user)
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudieron obtener los periodos. Intenta de nuevo.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        # RespuestaApi.set_data espera dict, no lista.
        # Usamos Response directo para envolver la lista dentro del sobre.
        from rest_framework.response import Response
        cuerpo = {
            'isSuccess': True,
            'message': 'Periodos obtenidos correctamente.',
            'data': periodos,
        }
        return Response(cuerpo, status=status.HTTP_200_OK)


class PeriodActiveView(APIView):
    """
    GET /api/v1.0.0/period/active/

    Devuelve el periodo activo actual.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        try:
            periodos = obtener_periodos_usuario(request.user)
            active_id = obtener_periodo_activo_id(periodos)
            periodo_activo = next((p for p in periodos if p['id'] == active_id), None)
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudo obtener el periodo activo. Intenta de nuevo.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        if not periodo_activo:
            respuesta.set_success(False)
            respuesta.set_message('No hay periodo activo configurado.')
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Periodo activo obtenido correctamente.')
        respuesta.set_data(periodo_activo)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()
