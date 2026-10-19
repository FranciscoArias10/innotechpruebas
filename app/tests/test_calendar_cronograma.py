import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

class StudentCalendarCronogramaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='usuario_test_cal',
            password='Password123*',
            email='test_cal@ejemplo.test'
        )
        self.client.force_authenticate(user=self.user)
        self.url = '/api/v1.0.0/student/calendar/'

    def test_calendar_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(self.url, HTTP_X_PERIOD_ID='2')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_calendar_requires_x_period_id(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        data = res.json()
        self.assertFalse(data.get('isSuccess', True))

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_views.obtener_calendario_completo')
    def test_calendar_success(self, mock_cal, mock_est):
        mock_est.return_value = {
            'persona_id': 37,
            'estudiante_id': 37,
            'nombres': 'MATEO MATEO',
            'apellidos': 'ANDRADE',
        }
        mock_cal.return_value = {
            'items': [
                {
                    'id': 'act-1',
                    'actividad_id': 1,
                    'tipo': 'actividad',
                    'titulo': 'Ensayo de Historia',
                    'descripcion': 'Subir ensayo en formato PDF',
                    'fecha': '2026-10-25',
                    'hora': '23:59',
                    'fecha_inicio': '2026-10-18T00:00:00',
                    'fecha_fin': '2026-10-25T23:59:00',
                    'materia_id': 10,
                    'materia_asignada_id': 20,
                    'materia_nombre': 'Historia',
                    'materia_color': '#3B82F6',
                    'entregada': False,
                    'vencida': False,
                    'cerrada': False,
                    'ponderacion': 10.0,
                    'nota': None,
                    'tipoentrega': 1,
                },
                {
                    'id': 'sem-1',
                    'tipo': 'institucional',
                    'titulo': 'Inicio SEMANA I',
                    'descripcion': 'Periodo de clases semanal',
                    'fecha': '2026-10-05',
                    'hora': '07:00',
                    'fecha_inicio': '2026-10-05',
                    'fecha_fin': '2026-10-11',
                    'materia_id': None,
                    'materia_asignada_id': None,
                    'materia_nombre': 'Institucional',
                    'materia_color': '#0b3b60',
                    'orden': 1,
                }
            ],
            'activities': [],
            'cronograma_academico': {
                'id': 1,
                'nombre': 'PERIODO ORDINARIO',
                'inicio': '2026-09-21',
                'fin': '2027-03-02',
                'semanas': [{'id': 1, 'orden': 1, 'nombre': 'SEMANA I', 'inicio': '2026-10-05', 'fin': '2026-10-11'}]
            },
            'cronograma_evaluativo': [
                {'id': 1, 'nombre': 'PRIMER BIMESTRE', 'alias': 'PB', 'inicio': '2026-09-21', 'fin': '2026-12-18', 'porcentaje': 50.0}
            ],
            'subjects': [{'id': 10, 'materia_asignada_id': 20, 'nombre': 'Historia', 'color': '#3B82F6'}],
            'total': 2,
            'pending_count': 1,
        }

        res = self.client.get(self.url, HTTP_X_PERIOD_ID='2')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data['isSuccess'])
        self.assertIn('items', data['data'])
        self.assertEqual(len(data['data']['items']), 2)
        self.assertIn('cronograma_academico', data['data'])
        self.assertIn('cronograma_evaluativo', data['data'])
        self.assertIn('subjects', data['data'])

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_views.obtener_calendario_completo')
    def test_calendar_with_filters(self, mock_cal, mock_est):
        mock_est.return_value = {'persona_id': 37, 'estudiante_id': 37}
        mock_cal.return_value = {'items': [], 'activities': [], 'subjects': [], 'total': 0, 'pending_count': 0}

        res = self.client.get(f"{self.url}?view=month&date=2026-10-18&subject_id=10", HTTP_X_PERIOD_ID='2')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_cal.assert_called_once_with(
            persona_id=37,
            periodo_id=2,
            vista='month',
            fecha_ref='2026-10-18',
            subject_id=10
        )
