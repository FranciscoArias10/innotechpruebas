# -*- coding: utf-8 -*-
"""
Pruebas del endpoint de registro de dispositivo.

ESTO SI VIAJA. Del otro lado se corren contra el sistema real: si asumieron
algo falso, revienta alla y se arregla antes de desplegar.

Cubran siempre estos cuatro casos en todo endpoint que escriban:
  1. camino feliz
  2. entrada invalida  -> 400 con `errors`
  3. sin autenticar    -> 401
  4. idempotencia / repeticion
"""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import DispositivoRegistrado


class DeviceRegisterTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='pasante', password='clave-de-prueba')
        self.url = reverse('movil-device-register')

    def test_registra_dispositivo_nuevo(self):
        self.client.force_authenticate(user=self.usuario)

        r = self.client.post(self.url, {
            'token': 'abc123', 'plataforma': 'android',
            'app_version': '1.0.0', 'modelo_dispositivo': 'Pixel 7',
        }, format='json')

        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(r.data['isSuccess'])
        self.assertEqual(r.data['data']['plataforma'], 'Android')
        self.assertEqual(DispositivoRegistrado.objects.count(), 1)

    def test_el_sobre_usa_isSuccess_y_no_success(self):
        """El campo se llama isSuccess. Siete specs del sistema dicen otra cosa
        y estan equivocadas: no copien ese error."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.post(self.url, {'token': 'x', 'plataforma': 'ios'}, format='json')
        self.assertIn('isSuccess', r.data)
        self.assertNotIn('success', r.data)

    def test_rechaza_plataforma_desconocida(self):
        self.client.force_authenticate(user=self.usuario)
        r = self.client.post(self.url, {'token': 'abc', 'plataforma': 'symbian'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data['isSuccess'])
        self.assertIn('plataforma', r.data['errors'])

    def test_exige_autenticacion(self):
        r = self.client.post(self.url, {'token': 'abc', 'plataforma': 'ios'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_es_idempotente(self):
        self.client.force_authenticate(user=self.usuario)
        cuerpo = {'token': 'mismo-token', 'plataforma': 'android', 'app_version': '1.0.0'}

        primera = self.client.post(self.url, cuerpo, format='json')
        cuerpo['app_version'] = '1.1.0'
        segunda = self.client.post(self.url, cuerpo, format='json')

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(DispositivoRegistrado.objects.count(), 1)
        self.assertEqual(segunda.data['data']['app_version'], '1.1.0')
