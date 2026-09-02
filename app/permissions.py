# -*- coding: utf-8 -*-
"""
Permisos personalizados de la app. ESTO SI VIAJA a sige-ube.
"""
from rest_framework.permissions import BasePermission
from sige_ports import portal


class EsRepresentanteDelEstudiante(BasePermission):
    """
    Verifica que el usuario autenticado (representante) tenga un vínculo activo
    con el estudiante indicado en la URL.

    Utiliza el puerto `sige_ports.portal.representa_a(persona_id, estudiante_id)`.
    Si el puerto devuelve False, la petición es rechazada con un código HTTP 403 Forbidden.
    """
    message = 'No tiene permiso para acceder a la información de este estudiante.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        student_id = (
            view.kwargs.get('student_id') or
            view.kwargs.get('estudiante_id') or
            view.kwargs.get('pk')
        )

        if student_id is None:
            return True

        try:
            student_id = int(student_id)
        except (ValueError, TypeError):
            return True

        persona_id = getattr(request.user, 'persona_id', request.user.id)
        return portal.representa_a(persona_id=persona_id, estudiante_id=student_id)
