# -*- coding: utf-8 -*-
"""
Pruebas para GET|PUT /movil/notifications/preferences/.

Cubre:
  1. GET camino feliz (genera valores por defecto si no existen)
  2. GET sin autenticar -> 401
  3. PUT camino feliz parcial (actualiza solo los campos enviados)
  4. PUT idempotencia (mismo resultado al enviar repetidas veces)
  5. PUT sin autenticar -> 401
  6. PUT datos inválidos -> 400 con errors
  7. Formato del sobre (isSuccess y no success)
  8. Aislamiento entre usuarios
"""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import PreferenciaNotificacion


class NotificationPreferencesTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='alumno_test', password='password123')
        self.otro_usuario = User.objects.create_user(username='otro_alumno', password='password123')
        self.url = reverse('movil-notification-preferences')

    def test_get_preferencias_crea_defaults(self):
        """Un usuario nuevo obtiene preferencias por defecto (todas habilitadas)."""
        self.client.force_authenticate(user=self.usuario)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['isSuccess'])
        self.assertEqual(response.data['message'], 'Preferencias de notificación recuperadas con éxito.')
        data = response.data['data']
        self.assertTrue(data['push_enabled'])
        self.assertTrue(data['grades'])
        self.assertTrue(data['attendance'])
        self.assertTrue(data['events'])
        self.assertTrue(data['announcements'])
        self.assertTrue(data['tasks'])
        self.assertEqual(PreferenciaNotificacion.objects.filter(usuario=self.usuario).count(), 1)

    def test_get_exige_autenticacion(self):
        """Petición anónima debe ser rechazada con 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_parcial_actualiza_campo(self):
        """PUT parcial actualiza únicamente los campos provistos sin alterar los demás."""
        self.client.force_authenticate(user=self.usuario)

        # Desactivar solo 'grades' y 'tasks'
        response = self.client.put(self.url, {'grades': False, 'tasks': False}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['isSuccess'])
        self.assertEqual(response.data['message'], 'Preferencias de notificación actualizadas con éxito.')
        data = response.data['data']
        self.assertFalse(data['grades'])
        self.assertFalse(data['tasks'])
        # Los demás deben seguir en True
        self.assertTrue(data['push_enabled'])
        self.assertTrue(data['attendance'])
        self.assertTrue(data['events'])
        self.assertTrue(data['announcements'])

        # Verificar en base de datos
        pref = PreferenciaNotificacion.objects.get(usuario=self.usuario)
        self.assertFalse(pref.grades)
        self.assertFalse(pref.tasks)
        self.assertTrue(pref.push_enabled)

    def test_put_es_idempotente(self):
        """Múltiples llamadas PUT con los mismos datos dejan el mismo estado en base de datos."""
        self.client.force_authenticate(user=self.usuario)
        payload = {'push_enabled': False, 'attendance': False}

        r1 = self.client.put(self.url, payload, format='json')
        r2 = self.client.put(self.url, payload, format='json')

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data['data'], r2.data['data'])
        self.assertEqual(PreferenciaNotificacion.objects.filter(usuario=self.usuario).count(), 1)

    def test_put_exige_autenticacion(self):
        """PUT sin autenticación retorna 401."""
        response = self.client.put(self.url, {'grades': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_rechaza_datos_invalidos(self):
        """PUT con tipos no booleanos retorna 400 y el formato errors."""
        self.client.force_authenticate(user=self.usuario)

        response = self.client.put(self.url, {'grades': 'no-es-booleano'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['isSuccess'])
        self.assertIn('errors', response.data)
        self.assertIn('grades', response.data['errors'])

    def test_sobre_usa_is_success_y_no_success(self):
        """El sobre debe cumplir con la regla institucional isSuccess."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(self.url)
        self.assertIn('isSuccess', r.data)
        self.assertNotIn('success', r.data)

    def test_aislamiento_entre_usuarios(self):
        """Las preferencias de un usuario no afectan a otro usuario."""
        self.client.force_authenticate(user=self.usuario)
        self.client.put(self.url, {'grades': False}, format='json')

        # El otro usuario consulta sus preferencias
        self.client.force_authenticate(user=self.otro_usuario)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['data']['grades'])
