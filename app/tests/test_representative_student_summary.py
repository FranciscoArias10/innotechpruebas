# -*- coding: utf-8 -*-
"""
Pruebas para el endpoint GET /representative/students/<id>/summary/

Cubre:
  1. Camino feliz (200 OK con métricas y matrícula)
  2. Formato del sobre (isSuccess y no success)
  3. Validación de header X-Period-ID (400)
  4. Exigencia de autenticación (401)
  5. Parentesco denegado vía mock de portal.representa_a (403)
  6. Estudiante sin matrícula vía LookupError (404)
  7. Error interno del puerto manejado con sobre (500)
"""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class RepresentativeStudentSummaryTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='representante_sum', password='clave-de-prueba')
        self.student_id = 4412
        self.periodo_id = 6
        self.url = reverse('movil-representative-student-summary', kwargs={'student_id': self.student_id})

    def test_obtiene_resumen_estudiante_representado_exitoso(self):
        """Camino feliz: devuelve 200 OK con la estructura de resumen académico."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['isSuccess'])
        self.assertIn('data', r.data)
        data = r.data['data']
        self.assertIn('total_subjects', data)
        self.assertIn('attendance_percentage', data)
        self.assertIn('pending_activities', data)
        self.assertIn('enrollment', data)
        self.assertIn('period', data)
        self.assertEqual(data['total_subjects'], 8)
        self.assertEqual(data['period']['id'], 6)

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
        self.assertIn('X-Period-ID', r2.data.get('errors', {}))

    def test_exige_autenticacion(self):
        """Petición anónima debe ser rechazada con 401 Unauthorized."""
        r = self.client.get(
            self.url,
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_parentesco_denegado_retorna_403(self):
        """Si portal.representa_a devuelve False, debe retornar 403 Forbidden."""
        self.client.force_authenticate(user=self.usuario)

        with patch('sige_ports.portal.representa_a', return_value=False):
            r = self.client.get(
                self.url,
                HTTP_X_PERIOD_ID=str(self.periodo_id),
            )

        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('detail', r.data)

    def test_estudiante_sin_matricula_retorna_404(self):
        """Si el puerto lanza LookupError, la vista traduce a 404 con sobre estándar."""
        self.client.force_authenticate(user=self.usuario)

        with patch('sige_ports.portal.resumen_estudiante', side_effect=LookupError('Sin matricula')):
            r = self.client.get(
                self.url,
                HTTP_X_PERIOD_ID=str(self.periodo_id),
            )

        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(r.data['isSuccess'])
        self.assertIn('Resumen no encontrado', r.data['message'])

    def test_error_inesperado_retorna_500(self):
        """Si el puerto falla inesperadamente, retorna 500 con sobre estándar."""
        self.client.force_authenticate(user=self.usuario)

        with patch('sige_ports.portal.resumen_estudiante', side_effect=Exception('Fallo base')):
            r = self.client.get(
                self.url,
                HTTP_X_PERIOD_ID=str(self.periodo_id),
            )

        self.assertEqual(r.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(r.data['isSuccess'])
