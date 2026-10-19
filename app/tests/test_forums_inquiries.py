# -*- coding: utf-8 -*-
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


class TestForumsAndInquiriesEndpoints(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='alumno_test',
            password='Password123*',
            email='alumno@uniebec.edu.ec'
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        self.persona_id = 45
        self.estudiante_id = 12
        self.materia_asignada_id = 99
        self.foro_id = 101
        self.post_id = 1001

    # =========================================================================
    # 1. FOROS DE LA MATERIA (GET /student/subjects/<id>/forums/)
    # =========================================================================

    def test_forums_requires_auth(self):
        """Petición anónima debe ser rechazada con 401 Unauthorized."""
        resp = self.client.get(f'/api/v1.0.0/student/subjects/{self.materia_asignada_id}/forums/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('app.student_views.obtener_estudiante_de_usuario', return_value=None)
    def test_forums_non_student_forbidden(self, mock_est):
        """Usuario que no es estudiante debe ser rechazado con 403 Forbidden."""
        resp = self.client.get(
            f'/api/v1.0.0/student/subjects/{self.materia_asignada_id}/forums/',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(resp.data['isSuccess'])

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.obtener_foros_materia')
    def test_forums_success(self, mock_foros, mock_est):
        """Lista foros de una materia asignada exitosamente."""
        mock_est.return_value = {'persona_id': self.persona_id, 'estudiante_id': self.estudiante_id}
        mock_foros.return_value = {
            'forums': [
                {
                    'id': self.foro_id,
                    'materia_asignada_id': self.materia_asignada_id,
                    'materia_nombre': 'Matemáticas Discretas',
                    'titulo': 'Debate Semana 2: Grafos y Árboles',
                    'descripcion': 'Consigna o tema propuesto por el docente...',
                    'fecha_creacion': '2026-10-10T14:30:00Z',
                    'fecha_cierre': '2026-10-25T23:59:59Z',
                    'esta_cerrado': False,
                    'docente_nombre': 'Ing. Juan Pérez',
                    'total_posts': 4,
                    'ultimo_post_fecha': '2026-10-12T09:15:00Z'
                }
            ]
        }
        resp = self.client.get(
            f'/api/v1.0.0/student/subjects/{self.materia_asignada_id}/forums/',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(len(resp.data['data']['forums']), 1)
        foro = resp.data['data']['forums'][0]
        self.assertEqual(foro['id'], self.foro_id)
        self.assertEqual(foro['total_posts'], 4)

    # =========================================================================
    # 2. DETALLE DE UN FORO (GET /student/forums/<id>/)
    # =========================================================================

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.obtener_detalle_foro')
    def test_forum_detail_success(self, mock_det, mock_est):
        """Retorna cabecera del foro e hilo de aportes."""
        mock_est.return_value = {'persona_id': self.persona_id, 'estudiante_id': self.estudiante_id}
        mock_det.return_value = {
            'forum': {
                'id': self.foro_id,
                'materia_asignada_id': self.materia_asignada_id,
                'materia_nombre': 'Matemáticas Discretas',
                'titulo': 'Debate Semana 2',
                'descripcion': 'Consigna...',
                'fecha_creacion': '2026-10-10T14:30:00Z',
                'fecha_cierre': '2026-10-25T23:59:59Z',
                'esta_cerrado': False,
                'docente_nombre': 'Ing. Juan Pérez',
                'total_posts': 2
            },
            'posts': [
                {
                    'id': 1001,
                    'foro_id': self.foro_id,
                    'autor_id': 99,
                    'autor_nombre': 'Ing. Juan Pérez',
                    'es_docente': True,
                    'es_propio': False,
                    'mensaje': 'Bienvenidos al foro.',
                    'fecha': '2026-10-10T15:00:00Z',
                    'fecha_edicion': None
                },
                {
                    'id': 1002,
                    'foro_id': self.foro_id,
                    'autor_id': self.persona_id,
                    'autor_nombre': 'Alumno Test',
                    'es_docente': False,
                    'es_propio': True,
                    'mensaje': 'Mi aporte...',
                    'fecha': '2026-10-11T10:20:00Z',
                    'fecha_edicion': None
                }
            ]
        }
        resp = self.client.get(f'/api/v1.0.0/student/forums/{self.foro_id}/', **self.auth_headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertIn('forum', resp.data['data'])
        self.assertIn('posts', resp.data['data'])
        self.assertEqual(len(resp.data['data']['posts']), 2)

    # =========================================================================
    # 3. PUBLICAR APORTE (POST /student/forums/<id>/posts/)
    # =========================================================================

    def test_forum_post_create_validation_error(self):
        """Mensaje vacío debe devolver 400 Bad Request."""
        with patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': self.persona_id}):
            resp = self.client.post(
                f'/api/v1.0.0/student/forums/{self.foro_id}/posts/',
                data={'mensaje': ''},
                format='json',
                **self.auth_headers
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(resp.data['isSuccess'])
            self.assertIn('mensaje', resp.data['errors'])

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.publicar_post_foro')
    def test_forum_post_create_closed_forbidden(self, mock_pub, mock_est):
        """Si el foro está cerrado, debe devolver 400 Bad Request."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_pub.side_effect = ValueError("El foro se encuentra cerrado para nuevas publicaciones.")
        resp = self.client.post(
            f'/api/v1.0.0/student/forums/{self.foro_id}/posts/',
            data={'mensaje': 'Mi aporte tardío'},
            format='json',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data['isSuccess'])
        self.assertIn('cerrado', resp.data['message'])

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.publicar_post_foro')
    def test_forum_post_create_success(self, mock_pub, mock_est):
        """Publicación exitosa en un foro abierto devuelve 201 Created."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_pub.return_value = {
            'id': 1005,
            'foro_id': self.foro_id,
            'autor_id': self.persona_id,
            'autor_nombre': 'Alumno Test',
            'es_docente': False,
            'es_propio': True,
            'mensaje': 'Mi aporte fundamentado',
            'fecha': '2026-10-16T12:00:00Z',
            'fecha_edicion': None
        }
        resp = self.client.post(
            f'/api/v1.0.0/student/forums/{self.foro_id}/posts/',
            data={'mensaje': 'Mi aporte fundamentado'},
            format='json',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(resp.data['data']['id'], 1005)

    # =========================================================================
    # 4. EDITAR Y ELIMINAR APORTE PROPIO
    # =========================================================================

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.editar_post_foro')
    def test_forum_post_edit_success(self, mock_edit, mock_est):
        """Edición exitosa del aporte propio devuelve 200 OK con fecha_edicion."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_edit.return_value = {
            'id': self.post_id,
            'foro_id': self.foro_id,
            'autor_id': self.persona_id,
            'autor_nombre': 'Alumno Test',
            'es_docente': False,
            'es_propio': True,
            'mensaje': 'Mensaje corregido',
            'fecha': '2026-10-16T12:00:00Z',
            'fecha_edicion': '2026-10-16T12:30:00Z'
        }
        resp = self.client.put(
            f'/api/v1.0.0/student/forums/posts/{self.post_id}/',
            data={'mensaje': 'Mensaje corregido'},
            format='json',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(resp.data['data']['mensaje'], 'Mensaje corregido')
        self.assertIsNotNone(resp.data['data']['fecha_edicion'])

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.editar_post_foro')
    def test_forum_post_edit_foreign_forbidden(self, mock_edit, mock_est):
        """Intentar editar el aporte de otro usuario debe devolver 403 Forbidden."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_edit.side_effect = PermissionError("Solo el autor original puede editar este aporte.")
        resp = self.client.put(
            f'/api/v1.0.0/student/forums/posts/{self.post_id}/',
            data={'mensaje': 'Modificación no autorizada'},
            format='json',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(resp.data['isSuccess'])

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.eliminar_post_foro')
    def test_forum_post_delete_success(self, mock_del, mock_est):
        """Eliminación exitosa del aporte propio devuelve 200 OK."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_del.return_value = {'id': self.post_id}
        resp = self.client.delete(
            f'/api/v1.0.0/student/forums/posts/{self.post_id}/',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(resp.data['data']['id'], self.post_id)

    # =========================================================================
    # 5. CONSULTAS PRIVADAS AL DOCENTE (GET / POST)
    # =========================================================================

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.obtener_consultas_docente')
    def test_inquiries_list_success(self, mock_inq, mock_est):
        """Listar consultas privadas al docente devuelve total_nuevas e inquiries."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_inq.return_value = {
            'total_nuevas': 1,
            'inquiries': [
                {
                    'id': 201,
                    'materia_asignada_id': self.materia_asignada_id,
                    'materia_nombre': 'Matemáticas Discretas',
                    'docente_nombre': 'Ing. Juan Pérez',
                    'estudiante_id': self.estudiante_id,
                    'estudiante_nombre': 'Alumno Test',
                    'asunto': 'Duda sobre el ejercicio 4',
                    'pregunta': 'Profesor, tengo dudas con...',
                    'fecha_pregunta': '2026-10-12T16:00:00Z',
                    'respuesta': 'Hola. Resuelve por sustitución.',
                    'fecha_respuesta': '2026-10-13T09:30:00Z',
                    'respondida': True,
                    'leida': True
                }
            ]
        }
        resp = self.client.get(
            f'/api/v1.0.0/student/subjects/{self.materia_asignada_id}/inquiries/',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(resp.data['data']['total_nuevas'], 1)
        self.assertEqual(len(resp.data['data']['inquiries']), 1)

    @patch('app.student_views.obtener_estudiante_de_usuario')
    @patch('app.student_ports.crear_consulta_docente')
    def test_inquiry_create_success(self, mock_crear, mock_est):
        """Enviar nueva consulta al docente devuelve 201 Created."""
        mock_est.return_value = {'persona_id': self.persona_id}
        mock_crear.return_value = {
            'id': 205,
            'materia_asignada_id': self.materia_asignada_id,
            'materia_nombre': 'Matemáticas Discretas',
            'docente_nombre': 'Ing. Juan Pérez',
            'estudiante_id': self.estudiante_id,
            'estudiante_nombre': 'Alumno Test',
            'asunto': 'Consulta sobre examen',
            'pregunta': '¿Qué temas abarcará el examen?',
            'fecha_pregunta': '2026-10-16T15:00:00Z',
            'respuesta': None,
            'fecha_respuesta': None,
            'respondida': False,
            'leida': False
        }
        payload = {
            'asunto': 'Consulta sobre examen',
            'pregunta': '¿Qué temas abarcará el examen?'
        }
        resp = self.client.post(
            f'/api/v1.0.0/student/subjects/{self.materia_asignada_id}/inquiries/',
            data=payload,
            format='json',
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['isSuccess'])
        self.assertEqual(resp.data['data']['id'], 205)
        self.assertFalse(resp.data['data']['respondida'])
        self.assertFalse(resp.data['data']['leida'])

    def test_inquiry_create_validation_error(self):
        """Asunto o pregunta vacía devuelve 400 Bad Request."""
        with patch('app.student_views.obtener_estudiante_de_usuario', return_value={'persona_id': self.persona_id}):
            resp = self.client.post(
                f'/api/v1.0.0/student/subjects/{self.materia_asignada_id}/inquiries/',
                data={'asunto': '', 'pregunta': ''},
                format='json',
                **self.auth_headers
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(resp.data['isSuccess'])
            self.assertIn('asunto', resp.data['errors'])
            self.assertIn('pregunta', resp.data['errors'])
