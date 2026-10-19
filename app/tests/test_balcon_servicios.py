# -*- coding: utf-8 -*-
import json
from io import BytesIO
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile


class StudentBalconServiciosTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='usuario_test_balcon',
            password='Password123*',
            email='test_balcon@ejemplo.test'
        )
        self.client.force_authenticate(user=self.user)
        self.url_types = '/api/v1.0.0/student/services/types/'
        self.url_requests = '/api/v1.0.0/student/services/requests/'
        self.url_documents = '/api/v1.0.0/student/documents/'
        self.url_doc_upload = '/api/v1.0.0/student/documents/upload/'

    def test_endpoints_require_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url_types).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.url_requests).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.url_documents).status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_ports.obtener_catalogo_servicios_estudiante')
    def test_get_service_types_success(self, mock_cat, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        mock_cat.return_value = {
            'certificados': [{'subtipo': 'NO_ADEUDAR', 'nombre': 'Certificado de No Adeudar'}],
            'tramites': [{'tipo': 'JUSTIFICACION_FALTA', 'nombre': 'Justificación de Inasistencia'}],
            'materias': [{'materia_id': 1, 'nombre': 'Matemáticas'}],
        }

        res = self.client.get(self.url_types)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertTrue(body.get('isSuccess'))
        self.assertIn('certificados', body.get('data'))
        self.assertIn('tramites', body.get('data'))

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_ports.obtener_solicitudes_servicio_estudiante')
    def test_get_requests_success(self, mock_sols, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        mock_sols.return_value = {
            'solicitudes': [
                {
                    'id': 10,
                    'codigo': 'SOL-2026-00010',
                    'tipo': 'CERTIFICADO',
                    'subtipo_certificado': 'NO_ADEUDAR',
                    'estado': 'PENDIENTE',
                    'motivo': 'Para trámite de beca',
                }
            ],
            'kpi': {'total': 1, 'pendientes': 1, 'aprobadas': 0, 'rechazadas': 0}
        }

        res = self.client.get(self.url_requests)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertTrue(body.get('isSuccess'))
        self.assertEqual(len(body['data']['solicitudes']), 1)
        self.assertEqual(body['data']['kpi']['total'], 1)

    @patch('app.student_views._obtener_estudiante_actual')
    def test_create_request_validation_error(self, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        res = self.client.post(self.url_requests, {'tipo': 'TIPO_INVALIDO'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        body = res.json()
        self.assertFalse(body.get('isSuccess'))
        self.assertIn('errors', body)

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_ports.crear_solicitud_servicio_estudiante')
    def test_create_request_success(self, mock_create, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        mock_create.return_value = {
            'id': 15,
            'codigo': 'SOL-2026-00015',
            'tipo': 'CERTIFICADO',
            'subtipo_certificado': 'NO_ADEUDAR',
            'estado': 'PENDIENTE',
            'motivo': 'Trámite de no adeudar bancario',
        }

        payload = {
            'tipo': 'CERTIFICADO',
            'subtipo_certificado': 'NO_ADEUDAR',
            'motivo': 'Trámite de no adeudar bancario',
        }
        res = self.client.post(self.url_requests, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        body = res.json()
        self.assertTrue(body.get('isSuccess'))
        self.assertEqual(body['data']['codigo'], 'SOL-2026-00015')

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_ports.obtener_detalle_solicitud_servicio')
    def test_get_request_detail_success(self, mock_detail, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        mock_detail.return_value = {
            'id': 15,
            'codigo': 'SOL-2026-00015',
            'estado': 'APROBADA',
            'certificado_final': 'balcon/cert_15.pdf',
            'certificado_url': 'http://testserver/media/balcon/cert_15.pdf',
            'adjuntos': [],
        }

        res = self.client.get('/api/v1.0.0/student/services/requests/15/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertTrue(body.get('isSuccess'))
        self.assertEqual(body['data']['estado'], 'APROBADA')

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_ports.obtener_documentos_y_requerimientos_estudiante')
    def test_get_documents_success(self, mock_docs, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        mock_docs.return_value = {
            'requerimientos': [
                {'requerimiento_id': 1, 'tipo_nombre': 'Cédula de identidad', 'estado_entrega': 'PENDIENTE'}
            ],
            'documentos_subidos': [],
            'tipos_documentos': [{'id': 1, 'nombre': 'Cédula de identidad'}],
            'resumen': {'total_requeridos': 1, 'entregados': 0, 'pendientes': 1}
        }

        res = self.client.get(self.url_documents)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertTrue(body.get('isSuccess'))
        self.assertIn('requerimientos', body.get('data'))

    @patch('app.student_views._obtener_estudiante_actual')
    @patch('app.student_ports.subir_documento_estudiante')
    def test_upload_document_success(self, mock_upload, mock_est):
        mock_est.return_value = {'persona_id': 2, 'estudiante_id': 1}
        mock_upload.return_value = {
            'id': 1,
            'tipo_id': 1,
            'nombre_original': 'cedula.pdf',
            'estado': 'PENDIENTE',
            'archivo_url': 'http://testserver/media/documentos/cedula.pdf'
        }

        test_file = SimpleUploadedFile("cedula.pdf", b"test pdf content", content_type="application/pdf")
        res = self.client.post(self.url_doc_upload, {'tipo_id': 1, 'archivo': test_file}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        body = res.json()
        self.assertTrue(body.get('isSuccess'))
        self.assertEqual(body['data']['nombre_original'], 'cedula.pdf')
