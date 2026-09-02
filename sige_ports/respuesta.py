# -*- coding: utf-8 -*-
"""
Doble de `helpers.response_api_helper.HelperResponseApi` del sistema real.

Produce EXACTAMENTE el mismo sobre que la API de produccion:

    {"isSuccess": bool, "message": str|null, "data": {...}}

OJO CON ESTO: siete de los doce documentos de especificacion del sistema real
dicen que el campo se llama "success". Es falso: el codigo siempre ha devuelto
"isSuccess". Corregir esos documentos es parte de su trabajo (tarea T1).
"""
from rest_framework import status as http
from rest_framework.response import Response


class RespuestaApi(object):

    def __init__(self):
        self.isSuccess = False
        self.message = None
        self.data = {}
        self.errors = {}
        self.code = http.HTTP_500_INTERNAL_SERVER_ERROR

    def set_success(self, is_success=True):
        self.isSuccess = is_success
        return self

    def set_message(self, message=None):
        self.message = message
        return self

    def set_data(self, data=None):
        self.data = data if isinstance(data, dict) else {}
        return self

    def set_errors(self, errors):
        self.errors = errors
        return self

    def set_status(self, code):
        self.code = code
        return self

    def to_dict(self, show_empty=False):
        cuerpo = {'isSuccess': self.isSuccess, 'message': self.message}
        if self.data or show_empty:
            cuerpo['data'] = self.data
        if self.errors:
            cuerpo['errors'] = self.errors
        return Response(cuerpo, status=self.code)
