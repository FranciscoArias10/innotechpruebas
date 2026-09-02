# -*- coding: utf-8 -*-
"""
Pruebas para el endpoint GET /representative/students/<id>/grades/

Cubre los 4 casos obligatorios (feliz, inválido, sin autenticar, repetición),
más la prueba obligatoria con mock.patch para el caso 403 (permiso denegado por parentesco).
"""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class RepresentativeStudentGradesTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='representante', password='clave-de-prueba')
        self.student_id = 4412
        self.materia_asignada_id = 123
        self.periodo_id = 6
        self.url = reverse('movil-representative-student-grades', kwargs={'student_id': self.student_id})

    def test_obtiene_notas_estudiante_representado_exitoso(self):
        """Camino feliz: devuelve 200 OK con la estructura de notas."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            f"{self.url}?materia_asignada_id={self.materia_asignada_id}",
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['isSuccess'])
        self.assertIn('data', r.data)
        self.assertIn('subject', r.data['data'])
        self.assertIn('evaluation_model', r.data['data'])

    def test_el_sobre_usa_isSuccess_y_no_success(self):
        """El sobre de respuesta debe usar isSuccess y no success."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            f"{self.url}?materia_asignada_id={self.materia_asignada_id}",
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )
        self.assertIn('isSuccess', r.data)
        self.assertNotIn('success', r.data)

    def test_exige_header_periodo_valido(self):
        """Si falta X-Period-ID o no es entero, retorna 400 Bad Request."""
        self.client.force_authenticate(user=self.usuario)

        # Sin header
        r1 = self.client.get(f"{self.url}?materia_asignada_id={self.materia_asignada_id}")
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r1.data['isSuccess'])
        self.assertIn('X-Period-ID', r1.data.get('errors', {}))

        # Header no numérico
        r2 = self.client.get(
            f"{self.url}?materia_asignada_id={self.materia_asignada_id}",
            HTTP_X_PERIOD_ID='invalido',
        )
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r2.data['isSuccess'])

    def test_exige_materia_asignada_id(self):
        """Si falta materia_asignada_id o no es entero, retorna 400 Bad Request."""
        self.client.force_authenticate(user=self.usuario)

        # Sin materia_asignada_id
        r1 = self.client.get(self.url, HTTP_X_PERIOD_ID=str(self.periodo_id))
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r1.data['isSuccess'])
        self.assertIn('materia_asignada_id', r1.data.get('errors', {}))

        # materia_asignada_id no entero
        r2 = self.client.get(f"{self.url}?materia_asignada_id=abc", HTTP_X_PERIOD_ID=str(self.periodo_id))
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r2.data['isSuccess'])

    def test_exige_autenticacion(self):
        """Petición sin token JWT debe retornar 401 Unauthorized."""
        r = self.client.get(
            f"{self.url}?materia_asignada_id={self.materia_asignada_id}",
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('sige_ports.portal.representa_a', return_value=False)
    def test_permiso_denegado_si_no_representa_al_estudiante(self, mock_representa):
        """Caso denegado obligatorio (403 Forbidden) cuando representa_a devuelve False."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            f"{self.url}?materia_asignada_id={self.materia_asignada_id}",
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        mock_representa.assert_called_once()

    @patch('sige_ports.portal.notas_de_estudiante', side_effect=LookupError('Materia no asignada'))
    def test_materia_no_encontrada_devuelve_404(self, mock_notas):
        """LookupError en el puerto debe retornar 404 Not Found."""
        self.client.force_authenticate(user=self.usuario)
        r = self.client.get(
            f"{self.url}?materia_asignada_id=9999",
            HTTP_X_PERIOD_ID=str(self.periodo_id),
        )

        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(r.data['isSuccess'])

    def test_es_idempotente(self):
        """Consultar dos veces la misma información debe responder de forma idéntica."""
        self.client.force_authenticate(user=self.usuario)
        url_full = f"{self.url}?materia_asignada_id={self.materia_asignada_id}"
        header = {'HTTP_X_PERIOD_ID': str(self.periodo_id)}

        r1 = self.client.get(url_full, **header)
        r2 = self.client.get(url_full, **header)

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data, r2.data)
