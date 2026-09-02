# -*- coding: utf-8 -*-
"""
Pruebas para el endpoint GET /representative/students/<id>/schedule/

Cubre los casos obligatorios, reusando el esquema de T11 y T12.
"""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class RepresentativeStudentScheduleTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='representante_sch', password='clave-de-prueba')
        self.student_id = 4412
        self.periodo_id = 6
        self.url = reverse('movil-representative-student-schedule', kwargs={'student_id': self.student_id})

    def test_obtiene_horario_estudiante_representado_exitoso(self):
        """Camino feliz: devuelve 200 OK con la estructura de horario."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['isSuccess'])
        self.assertIn('data', r.data)
        self.assertIn('turnos', r.data['data'])
        self.assertIn('dias_visibles', r.data['data'])

    def test_el_sobre_usa_isSuccess_y_no_success(self):
        """El sobre de respuesta debe usar isSuccess y no success."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )
        self.assertIn('isSuccess', r.data)
        self.assertNotIn('success', r.data)

    def test_exige_header_periodo_valido(self):
        """Si falta X-Period-ID o no es entero, retorna 400 Bad Request."""
        self.client.force_authenticate(user=self.usuario)

        # Sin header
        r1 = self.client.get(self.url)
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r1.data['isSuccess'])
        self.assertIn('X-Period-ID', r1.data.get('errors', {}))

        # Header no numérico
        r2 = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID='invalido',
        )
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r2.data['isSuccess'])

    def test_exige_autenticacion(self):
        """Petición sin token JWT debe retornar 401 Unauthorized."""
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('sige_ports.portal.representa_a', return_value=False)
    def test_permiso_denegado_si_no_representa_al_estudiante(self, mock_representa):
        """Caso denegado obligatorio (403 Forbidden) cuando representa_a devuelve False."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        mock_representa.assert_called_once()

    @patch('sige_ports.portal.horario_de_estudiante', side_effect=LookupError('No hay horario'))
    def test_horario_no_encontrado_devuelve_404(self, mock_horario):
        """LookupError en el puerto debe retornar 404 Not Found."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(r.data['isSuccess'])

    def test_es_idempotente(self):
        """Consultar dos veces la misma información debe responder de forma idéntica."""
        self.client.force_authenticate(user=self.usuario)
        header = {'HTTP_X_PERIOD_ID': str(self.periodo_id)}

        r1 = self.client.get(self.url, **header)
        r2 = self.client.get(self.url, **header)

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data, r2.data)
