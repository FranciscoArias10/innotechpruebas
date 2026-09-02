# -*- coding: utf-8 -*-
"""
Pruebas para POST /movil/feedback/.

Cubre:
  1. POST camino feliz
  2. POST sin autenticar -> 401
  3. POST datos inválidos -> 400
  4. Límite de tasa (throttling) estricto (2 por hora) -> 429
  5. Formato del sobre
"""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import FeedbackMovil


class FeedbackTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='alumno_test', password='password123')
        self.url = reverse('movil-feedback')

    def test_post_feedback_exitoso(self):
        """El usuario puede enviar un feedback válido."""
        self.client.force_authenticate(user=self.usuario)
        payload = {
            'tipo': FeedbackMovil.SUGERENCIA,
            'mensaje': 'Me gustaría un modo oscuro'
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['isSuccess'])
        self.assertEqual(response.data['message'], 'Feedback enviado con éxito.')
        self.assertEqual(FeedbackMovil.objects.count(), 1)
        fb = FeedbackMovil.objects.first()
        self.assertEqual(fb.usuario, self.usuario)
        self.assertEqual(fb.tipo, FeedbackMovil.SUGERENCIA)

    def test_post_feedback_sin_autenticar(self):
        """Petición anónima debe ser rechazada."""
        payload = {'tipo': 'ERROR', 'mensaje': 'Algo falló'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_datos_invalidos(self):
        """Si falta el mensaje o el tipo es inválido, retorna 400."""
        self.client.force_authenticate(user=self.usuario)
        
        # Tipo inválido y sin mensaje
        payload = {'tipo': 'INVALIDO'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['isSuccess'])
        self.assertIn('errors', response.data)
        self.assertIn('tipo', response.data['errors'])
        self.assertIn('mensaje', response.data['errors'])

    def test_throttling_estricto(self):
        """
        El rate limit es 2/hour. 
        A la tercera petición en el mismo periodo, debe retornar 429.
        """
        usuario_limit = User.objects.create_user(username='limit_test', password='password123')
        self.client.force_authenticate(user=usuario_limit)
        payload = {'tipo': FeedbackMovil.SUGERENCIA, 'mensaje': 'Test rate limit'}

        # 1ra petición
        r1 = self.client.post(self.url, payload, format='json')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        # 2da petición
        r2 = self.client.post(self.url, payload, format='json')
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)

        # 3ra petición -> Debe ser bloqueada (429 Too Many Requests)
        r3 = self.client.post(self.url, payload, format='json')
        self.assertEqual(r3.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('detail', r3.data)
