# -*- coding: utf-8 -*-
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


class TestStudentEndpoints(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='estudiante_test',
            password='Password123*',
            email='test@uniebec.edu.ec'
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}

    # 1. Autenticacion requerida
    def test_summary_requires_auth(self):
        resp = self.client.get('/api/v1.0.0/movil/student/summary/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # 2. Header X-Period-ID requerido
    def test_summary_requires_x_period_id(self):
        resp = self.client.get('/api/v1.0.0/movil/student/summary/', **self.auth_headers)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data['isSuccess'])
        self.assertIn('X-Period-ID', resp.data['message'])

    def test_summary_invalid_x_period_id_format(self):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='invalido')
        resp = self.client.get('/api/v1.0.0/movil/student/summary/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data['isSuccess'])

    # 3. Usuario no estudiante devuelve 403 Forbidden
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value=None)
    def test_non_student_user_forbidden(self, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/summary/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(resp.data['isSuccess'])

    # 4. Summary camino feliz
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': 10, 'estudiante_id': 5})
    @patch('app.student_views.obtener_resumen_estudiante', return_value={
        'total_subjects': 8,
        'attendance_percentage': 95.5,
        'pending_activities': 2,
        'enrollment': {'id': 1, 'level': '10MO EGB', 'level_alias': '10mo', 'parallel': 'A'},
        'period': {'id': 2, 'name': 'ACADEMICO'}
    })
    def test_summary_success(self, mock_res, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/summary/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(resp.data['data']['total_subjects'], 8)
        self.assertEqual(resp.data['data']['period']['id'], 2)

    # 5. Subjects camino feliz
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': 10, 'estudiante_id': 5})
    @patch('app.student_views.obtener_materias_estudiante', return_value={
        'subjects': [{'materia_asignada_id': 100, 'name': 'MATEMATICAS', 'color': '#0073bc', 'final_grade': 8.5}]
    })
    def test_subjects_success(self, mock_mat, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/subjects/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(len(resp.data['data']['subjects']), 1)

    # 6. Grades camino feliz y validacion X-Period-ID
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': 10, 'estudiante_id': 5})
    @patch('app.student_views.obtener_calificaciones_estudiante', return_value={
        'periodo_id': 2, 'calificaciones': [{'materia_nombre': 'LENGUAJE', 'nota_final': 9.0}]
    })
    def test_grades_success(self, mock_cal, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/grades/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        mock_cal.assert_called_once_with(10, 2)

    # 7. Detalle de calificaciones por materia
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': 10, 'estudiante_id': 5})
    @patch('app.student_views.obtener_detalle_notas_materia', return_value={
        'subject': {'id': 123, 'name': 'MATEMATICAS'},
        'evaluation_model': {'is_quantitative': True, 'items': []}
    })
    def test_subject_grades_detail_success(self, mock_det, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/subjects/123/grades/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        mock_det.assert_called_once_with(10, 2, 123)

    # 8. Asistencia reporte
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': 10, 'estudiante_id': 5})
    @patch('app.student_views.obtener_asistencia_estudiante', return_value={
        'subjects': [{'name': 'LENGUAJE', 'status': 'excelente'}]
    })
    def test_attendance_success(self, mock_asis, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/attendance/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])

    # 9. Horario semanal
    @patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': 10, 'estudiante_id': 5})
    @patch('app.student_views.obtener_horario_estudiante', return_value={
        'turnos': [{'nombre': 'MATUTINO', 'dias': []}],
        'dias_visibles': []
    })
    def test_schedule_success(self, mock_hor, mock_est):
        headers = dict(self.auth_headers, HTTP_X_PERIOD_ID='2')
        resp = self.client.get('/api/v1.0.0/movil/student/schedule/', **headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])