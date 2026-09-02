# -*- coding: utf-8 -*-
"""
Pruebas del panel de administración (T10).

Verifica que:
  1. Los 4 modelos están registrados en admin.site.
  2. Un superusuario puede acceder al listado de cada modelo (HTTP 200).
  3. Un usuario sin privilegios es redirigido al login (HTTP 302).
"""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.admin import (
    DispositivoRegistradoAdmin,
    FeedbackMovilAdmin,
    PreferenciaNotificacionAdmin,
    VersionAppMovilAdmin,
)
from app.models import (
    DispositivoRegistrado,
    FeedbackMovil,
    PreferenciaNotificacion,
    VersionAppMovil,
)
from django.contrib import admin


class AdminRegistroTests(TestCase):
    """Verifica que los modelos estén registrados en el sitio de administración."""

    def test_version_app_movil_registrado(self):
        self.assertIn(VersionAppMovil, admin.site._registry)

    def test_preferencia_notificacion_registrado(self):
        self.assertIn(PreferenciaNotificacion, admin.site._registry)

    def test_feedback_movil_registrado(self):
        self.assertIn(FeedbackMovil, admin.site._registry)

    def test_dispositivo_registrado_registrado(self):
        self.assertIn(DispositivoRegistrado, admin.site._registry)


class AdminAccesoTests(TestCase):
    """Verifica el acceso al panel según privilegios del usuario."""

    def setUp(self):
        self.superusuario = User.objects.create_superuser(
            username='operador', password='clave_admin', email='op@test.com')
        self.usuario_normal = User.objects.create_user(
            username='alumno', password='clave_alumno')

    def _url_changelist(self, modelo):
        app_label = modelo._meta.app_label
        model_name = modelo._meta.model_name
        return reverse('admin:%s_%s_changelist' % (app_label, model_name))

    def test_superusuario_accede_a_version_app(self):
        self.client.force_login(self.superusuario)
        r = self.client.get(self._url_changelist(VersionAppMovil))
        self.assertEqual(r.status_code, 200)

    def test_superusuario_accede_a_preferencias(self):
        self.client.force_login(self.superusuario)
        r = self.client.get(self._url_changelist(PreferenciaNotificacion))
        self.assertEqual(r.status_code, 200)

    def test_superusuario_accede_a_feedback(self):
        self.client.force_login(self.superusuario)
        r = self.client.get(self._url_changelist(FeedbackMovil))
        self.assertEqual(r.status_code, 200)

    def test_superusuario_accede_a_dispositivos(self):
        self.client.force_login(self.superusuario)
        r = self.client.get(self._url_changelist(DispositivoRegistrado))
        self.assertEqual(r.status_code, 200)

    def test_usuario_sin_privilegios_redirigido(self):
        self.client.force_login(self.usuario_normal)
        r = self.client.get(self._url_changelist(FeedbackMovil))
        self.assertEqual(r.status_code, 302)

    def test_anonimo_redirigido_a_login(self):
        r = self.client.get(self._url_changelist(VersionAppMovil))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r.url)
