# -*- coding: utf-8 -*-
"""
Suite de Pruebas de Seguridad para la API Móvil.

Ubicación: app/tests/test_security.py

Cubre los principales vectores del OWASP API Security Top 10:
  1. Autenticación Obligatoria (401 Unauthorized) en todos los endpoints privados.
  2. BOLA / IDOR (Broken Object Level Authorization -> 403 Forbidden) en registros de estudiantes.
  3. Resistencia a SQL Injection y tipado estricto (400 Bad Request / 404, nunca 500 DB error).
  4. Prevención de Mass Assignment (protección de campos privilegiados o de pertenencia).
  5. Aislamiento estricto de datos entre usuarios (Multi-tenant data leak prevention).
  6. Manejo seguro de payloads de texto / XSS sin excepciones de servidor.
"""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import PreferenciaNotificacion, DispositivoRegistrado, FeedbackMovil


class SecurityApiTests(APITestCase):

    def setUp(self):
        # Crear dos usuarios distintos (simulando dos representantes)
        self.usuario_a = User.objects.create_user(
            username='representante_a',
            password='passwordA123!',
            email='rep_a@example.com'
        )
        self.usuario_b = User.objects.create_user(
            username='representante_b',
            password='passwordB123!',
            email='rep_b@example.com'
        )    

        self.estudiante_hijo_a = 1001
        self.estudiante_ajeno_b = 2002
        self.periodo_valido = 6
        self.materia_valida = 45

    # =========================================================================
    # 1. PRUEBAS DE AUTENTICACIÓN (Rechazo a Peticiones Anónimas -> 401)
    # =========================================================================

    def test_endpoints_estudiantes_exigen_autenticacion(self):
        """Usuarios anónimos no pueden acceder a ningún registro de estudiantes."""
        endpoints = [
            reverse('movil-representative-student-grades', kwargs={'student_id': self.estudiante_hijo_a}),
            reverse('movil-representative-student-attendance', kwargs={'student_id': self.estudiante_hijo_a}),
            reverse('movil-representative-student-schedule', kwargs={'student_id': self.estudiante_hijo_a}),
            reverse('movil-representative-student-summary', kwargs={'student_id': self.estudiante_hijo_a}),
        ]

        for url in endpoints:
            response = self.client.get(
                url,
                HTTP_X_PERIOD_ID=str(self.periodo_valido),
                data={'materia_asignada_id': self.materia_valida}
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"El endpoint protegido {url} permitió acceso anónimo (esperado 401)."
            )

    def test_endpoints_usuario_exigen_autenticacion(self):
        """Endpoints de preferencias, registro de dispositivos y feedback exigen autenticación."""
        # GET y PUT en preferencias
        url_prefs = reverse('movil-notification-preferences')
        self.assertEqual(self.client.get(url_prefs).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.put(url_prefs, {'push_enabled': False}).status_code, status.HTTP_401_UNAUTHORIZED)

        # POST registro de dispositivo
        url_device = reverse('movil-device-register')
        self.assertEqual(
            self.client.post(url_device, {'token': 'xyz', 'plataforma': 'android'}).status_code,
            status.HTTP_401_UNAUTHORIZED
        )

        # POST feedback
        url_feedback = reverse('movil-feedback')
        self.assertEqual(
            self.client.post(url_feedback, {'tipo': 'SUGERENCIA', 'mensaje': 'hola'}).status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    # =========================================================================
    # 2. PRUEBAS DE AUTORIZACIÓN / BOLA / IDOR (403 Forbidden)
    # =========================================================================

    def test_idor_representante_bloqueado_al_consultar_estudiante_ajeno(self):
        """
        Un representante autenticado NO debe poder consultar notas, asistencia,
        horario o resumen de un estudiante con el que no tenga parentesco activo.
        """
        self.client.force_authenticate(user=self.usuario_a)

        endpoints = [
            (reverse('movil-representative-student-grades', kwargs={'student_id': self.estudiante_ajeno_b}), {'materia_asignada_id': self.materia_valida}),
            (reverse('movil-representative-student-attendance', kwargs={'student_id': self.estudiante_ajeno_b}), {}),
            (reverse('movil-representative-student-schedule', kwargs={'student_id': self.estudiante_ajeno_b}), {}),
            (reverse('movil-representative-student-summary', kwargs={'student_id': self.estudiante_ajeno_b}), {}),
        ]

        # Simulamos que portal.representa_a confirma que usuario_a NO representa a estudiante_ajeno_b
        with patch('sige_ports.portal.representa_a', return_value=False):
            for url, params in endpoints:
                response = self.client.get(
                    url,
                    data=params,
                    HTTP_X_PERIOD_ID=str(self.periodo_valido)
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_403_FORBIDDEN,
                    f"Vulnerabilidad BOLA/IDOR detectada en {url}: retornó {response.status_code} en vez de 403."
                )
                self.assertIn('detail', response.data)

    # =========================================================================
    # 3. PRUEBAS DE INYECCIÓN SQL Y FUZZING DE ENTRADAS
    # =========================================================================

    def test_sql_injection_en_headers_y_query_params_rechazado_con_400(self):
        """
        Payloads clásicos de SQLi en parámetros numéricos o headers deben ser rechazados
        por la validación de tipos con 400 Bad Request, NUNCA causar error 500 de base de datos.
        """
        self.client.force_authenticate(user=self.usuario_a)
        url = reverse('movil-representative-student-grades', kwargs={'student_id': self.estudiante_hijo_a})

        payloads_sqli = [
            "1' OR '1'='1",
            "1; DROP TABLE auth_user; --",
            "1 UNION SELECT null, username, password FROM auth_user--",
            "'",
            "admin'--",
            "sleep(5)#"
        ]

        with patch('sige_ports.portal.representa_a', return_value=True):
            for payload in payloads_sqli:
                # Intento en Header X-Period-ID
                r_header = self.client.get(
                    url,
                    HTTP_X_PERIOD_ID=payload,
                    data={'materia_asignada_id': self.materia_valida}
                )
                self.assertEqual(
                    r_header.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    f"Fallo al validar X-Period-ID con payload '{payload}'"
                )
                self.assertFalse(r_header.data.get('isSuccess', True))

                # Intento en Query Param materia_asignada_id
                r_param = self.client.get(
                    url,
                    HTTP_X_PERIOD_ID=str(self.periodo_valido),
                    data={'materia_asignada_id': payload}
                )
                self.assertEqual(
                    r_param.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    f"Fallo al validar materia_asignada_id con payload '{payload}'"
                )
                self.assertFalse(r_param.data.get('isSuccess', True))

    def test_sql_injection_en_url_capturado_por_enrutador(self):
        """
        Intentos de inyectar SQL directamente en el path /students/<student_id>/
        deben ser descartados en la capa URL con 404 Not Found gracias a <int:student_id>.
        """
        self.client.force_authenticate(user=self.usuario_a)
        url_maliciosa = "/api/v1.0.0/movil/representative/students/1' OR '1'='1/grades/"

        response = self.client.get(url_maliciosa, HTTP_X_PERIOD_ID=str(self.periodo_valido))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 4. PREVENCIÓN DE MASS ASSIGNMENT (Parámetros No Autorizados)
    # =========================================================================

    def test_mass_assignment_en_preferencias_no_permite_escalar_privilegios(self):
        """
        Intentar enviar atributos privilegiados como is_staff, is_superuser o usuario_id
        no debe alterar el modelo User ni cambiar la propiedad de la preferencia.
        """
        self.client.force_authenticate(user=self.usuario_a)
        url = reverse('movil-notification-preferences')

        payload_malicioso = {
            'push_enabled': False,
            'is_staff': True,
            'is_superuser': True,
            'usuario_id': self.usuario_b.id,
            'usuario': self.usuario_b.id
        }

        response = self.client.put(url, payload_malicioso, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Recargar usuario y preferencia desde BD
        self.usuario_a.refresh_from_db()
        pref = PreferenciaNotificacion.objects.get(usuario=self.usuario_a)

        self.assertFalse(self.usuario_a.is_staff, "Vulnerabilidad: usuario escaló a staff.")
        self.assertFalse(self.usuario_a.is_superuser, "Vulnerabilidad: usuario escaló a superuser.")
        self.assertEqual(pref.usuario, self.usuario_a, "Vulnerabilidad: se cambió el usuario propietario.")

    def test_mass_assignment_en_dispositivo_no_asigna_a_otro_usuario(self):
        """
        El registro de dispositivo siempre debe asociarse al usuario autenticado,
        ignorando cualquier id o username ajeno enviado en el payload.
        """
        self.client.force_authenticate(user=self.usuario_a)
        url = reverse('movil-device-register')

        payload = {
            'token': 'token-seguro-dispositivo-1',
            'plataforma': 'android',
            'usuario_id': self.usuario_b.id,
            'usuario': self.usuario_b.id,
            'activo': True
        }

        response = self.client.post(url, payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        disp = DispositivoRegistrado.objects.get(token='token-seguro-dispositivo-1')
        self.assertEqual(disp.usuario, self.usuario_a)
        self.assertNotEqual(disp.usuario, self.usuario_b)

    # =========================================================================
    # 5. AISLAMIENTO ESTRICTO DE DATOS ENTRE USUARIOS (Multi-tenancy)
    # =========================================================================

    def test_preferencias_totalmente_aisladas_entre_usuarios(self):
        """Modificar las preferencias del Usuario A no debe alterar las del Usuario B."""
        # Usuario A desactiva todo
        self.client.force_authenticate(user=self.usuario_a)
        url = reverse('movil-notification-preferences')
        self.client.put(url, {'push_enabled': False, 'grades': False}, format='json')

        # Usuario B consulta sus preferencias
        self.client.force_authenticate(user=self.usuario_b)
        response_b = self.client.get(url)

        self.assertEqual(response_b.status_code, status.HTTP_200_OK)
        # Las preferencias de B deben mantenerse intactas (por defecto en True)
        self.assertTrue(response_b.data['data']['push_enabled'])
        self.assertTrue(response_b.data['data']['grades'])

    # =========================================================================
    # 6. RESISTENCIA A PAYLOADS XSS / CARACTERES ESPECIALES EN TEXTO
    # =========================================================================

    def test_xss_en_feedback_almacenado_como_texto_plano(self):
        """
        Scripts maliciosos enviados en campos de texto (ej. feedback) se deben
        procesar y almacenar como texto literal sin provocar excepciones del servidor.
        """
        self.client.force_authenticate(user=self.usuario_a)
        url = reverse('movil-feedback')

        payload_xss = {
            'tipo': FeedbackMovil.SUGERENCIA,
            'mensaje': '<script>alert("XSS Attack!");</script><img src="x" onerror="alert(1)">'
        }

        response = self.client.post(url, payload_xss, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['isSuccess'])

        fb = FeedbackMovil.objects.get(usuario=self.usuario_a)
        self.assertEqual(fb.mensaje, payload_xss['mensaje'])
