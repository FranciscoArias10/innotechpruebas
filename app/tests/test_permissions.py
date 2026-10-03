# -*- coding: utf-8 -*-
"""
Pruebas directas de seguridad para la clase de permiso EsRepresentanteDelEstudiante.

Valida:
  1. Usuario no autenticado -> False
  2. Falta de student_id en kwargs -> False (Fail-Closed)
  3. student_id no entero -> False (Fail-Closed)
  4. Representación denegada por el puerto -> False
  5. Representación autorizada por el puerto -> True
"""
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from app.permissions import EsRepresentanteDelEstudiante


class PermissionsSecurityTests(TestCase):

    def setUp(self):
        self.permission = EsRepresentanteDelEstudiante()
        self.usuario = User.objects.create_user(username='padre_test', password='password123')

    def test_usuario_anonimo_es_denegado(self):
        request = MagicMock()
        request.user = AnonymousUser()
        view = MagicMock(kwargs={'student_id': 100})
        self.assertFalse(self.permission.has_permission(request, view))

    def test_ausencia_de_student_id_deniega_acceso_fail_closed(self):
        """Si la vista no tiene student_id en kwargs, debe denegar el acceso (Fail-Closed)."""
        request = MagicMock()
        request.user = self.usuario
        view = MagicMock(kwargs={})
        self.assertFalse(self.permission.has_permission(request, view))

    def test_student_id_invalido_deniega_acceso_fail_closed(self):
        """Si student_id no es un entero válido, debe denegar el acceso (Fail-Closed)."""
        request = MagicMock()
        request.user = self.usuario
        view = MagicMock(kwargs={'student_id': 'no-es-un-entero'})
        self.assertFalse(self.permission.has_permission(request, view))

    @patch('sige_ports.portal.representa_a', return_value=False)
    def test_portal_deniega_parentesco(self, mock_representa):
        request = MagicMock()
        request.user = self.usuario
        view = MagicMock(kwargs={'student_id': 500})
        self.assertFalse(self.permission.has_permission(request, view))
        mock_representa.assert_called_once()

    @patch('sige_ports.portal.representa_a', return_value=True)
    def test_portal_confirma_parentesco(self, mock_representa):
        request = MagicMock()
        request.user = self.usuario
        view = MagicMock(kwargs={'student_id': 500})
        self.assertTrue(self.permission.has_permission(request, view))
        mock_representa.assert_called_once()
