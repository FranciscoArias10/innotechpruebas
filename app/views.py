# -*- coding: utf-8 -*-
"""
Vistas de la app. ESTO SI VIAJA a sige-ube.

Patron obligatorio, copiado del sistema real:
  - APIView (no ViewSet)
  - permission_classes explicito
  - toda la respuesta sale por RespuestaApi, nunca por Response directo
  - un try/except que traduce el fallo a un mensaje util, no a un 500 pelado
"""
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from app.models import DispositivoRegistrado, VersionAppMovil, PreferenciaNotificacion
from app.serializers import (
    DispositivoRegistroSerializer,
    DispositivoSalidaSerializer,
    VersionAppMovilSerializer,
    PreferenciaNotificacionSerializer,
    FeedbackMovilSerializer,
)
from app.throttling import AppVersionRateThrottle, FeedbackRateThrottle
from app.permissions import EsRepresentanteDelEstudiante
from sige_ports import RespuestaApi, portal


class DeviceRegisterView(APIView):
    """
    POST /api/v1.0.0/movil/device/register/

    Registra o actualiza el token de notificaciones de un dispositivo.

    Es IDEMPOTENTE: mandar el mismo token dos veces no crea dos filas, actualiza
    la que ya existe. La app movil reintenta al reinstalar y al rotar el token,
    asi que esto no es un lujo.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        respuesta = RespuestaApi()

        entrada = DispositivoRegistroSerializer(data=request.data)
        if not entrada.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Los datos enviados no son válidos.')
            respuesta.set_errors(entrada.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            with transaction.atomic():
                # Desactivar registros previos de este mismo token en otros usuarios (evita fuga de notificaciones push)
                DispositivoRegistrado.objects.filter(
                    token=entrada.validated_data['token']
                ).exclude(usuario=request.user).update(activo=False)

                dispositivo, creado = DispositivoRegistrado.objects.update_or_create(
                    usuario=request.user,
                    token=entrada.validated_data['token'],
                    defaults={
                        'plataforma': entrada.plataforma_valor(),
                        'app_version': entrada.validated_data.get('app_version', ''),
                        'modelo_dispositivo': entrada.validated_data.get('modelo_dispositivo', ''),
                        'activo': True,
                    },
                )
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudo registrar el dispositivo.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Dispositivo registrado.' if creado else 'Dispositivo actualizado.')
        respuesta.set_data(DispositivoSalidaSerializer(dispositivo).data)
        respuesta.set_status(status.HTTP_201_CREATED if creado else status.HTTP_200_OK)
        return respuesta.to_dict()


class AppVersionView(APIView):
    """
    GET /api/v1.0.0/movil/app/version/

    Devuelve la información de versión de la aplicación para una plataforma específica.
    """
    permission_classes = []
    throttle_classes = [AppVersionRateThrottle]

    def get(self, request):
        respuesta = RespuestaApi()
        plataforma_param = str(request.query_params.get('plataforma', 'android')).strip()[:20].lower()

        if plataforma_param not in dict(VersionAppMovil.PLATAFORMA):
            respuesta.set_success(False)
            respuesta.set_message('Plataforma inválida. Use "android" o "ios".')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        version_info = VersionAppMovil.objects.filter(plataforma=plataforma_param, status=True).first()
        
        if not version_info:
            # Si no hay registro para esa plataforma, devolvemos un valor por defecto.
            # Idealmente debería estar configurado, pero no queremos romper la app.
            version_info = VersionAppMovil(
                plataforma=plataforma_param,
                version_minima='1.0.0',
                version_actual='1.0.0',
                forzar_actualizacion=False
            )

        respuesta.set_success(True)
        respuesta.set_message('Versión recuperada con éxito.')
        respuesta.set_data(VersionAppMovilSerializer(version_info).data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class NotificationPreferencesView(APIView):
    """
    GET|PUT /api/v1.0.0/movil/notifications/preferences/

    Consulta o actualiza las preferencias de notificaciones del usuario autenticado.
    El método PUT permite actualización parcial e idempotente.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        preferencias, _ = PreferenciaNotificacion.objects.get_or_create(usuario=request.user)

        respuesta.set_success(True)
        respuesta.set_message('Preferencias de notificación recuperadas con éxito.')
        respuesta.set_data(PreferenciaNotificacionSerializer(preferencias).data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()

    def put(self, request):
        respuesta = RespuestaApi()
        preferencias, _ = PreferenciaNotificacion.objects.get_or_create(usuario=request.user)

        serializer = PreferenciaNotificacionSerializer(preferencias, data=request.data, partial=True)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Los datos enviados no son válidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            with transaction.atomic():
                serializer.save()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudieron actualizar las preferencias de notificación.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Preferencias de notificación actualizadas con éxito.')
        respuesta.set_data(serializer.data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class FeedbackView(APIView):
    """
    POST /api/v1.0.0/movil/feedback/

    Recibe comentarios, quejas o sugerencias de los usuarios.
    Protegido con un rate limit estricto para evitar spam.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedbackRateThrottle]

    def post(self, request):
        respuesta = RespuestaApi()

        serializer = FeedbackMovilSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Los datos enviados no son válidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            with transaction.atomic():
                serializer.save(usuario=request.user)
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('No se pudo enviar el feedback.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Feedback enviado con éxito.')
        respuesta.set_data(serializer.data)
        respuesta.set_status(status.HTTP_201_CREATED)
        return respuesta.to_dict()


class RepresentativeStudentGradesView(APIView):
    """
    GET /api/v1.0.0/movil/representative/students/<int:student_id>/grades/

    Devuelve el libro de calificaciones de un estudiante en una materia específica.
    Verifica parentesco mediante portal.representa_a.
    """
    permission_classes = [IsAuthenticated, EsRepresentanteDelEstudiante]

    def get(self, request, student_id):
        respuesta = RespuestaApi()

        periodo_hdr = request.headers.get('X-Period-ID') or request.META.get('HTTP_X_PERIOD_ID')
        if not periodo_hdr:
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID es requerido.')
            respuesta.set_errors({'X-Period-ID': ['Este header es obligatorio.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            periodo_id = int(periodo_hdr)
        except (ValueError, TypeError):
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID debe ser entero.')
            respuesta.set_errors({'X-Period-ID': ['Formato de entero inválido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        materia_param = request.query_params.get('materia_asignada_id')
        if not materia_param:
            respuesta.set_success(False)
            respuesta.set_message('El parámetro materia_asignada_id es requerido.')
            respuesta.set_errors({'materia_asignada_id': ['Este campo es obligatorio.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            materia_asignada_id = int(materia_param)
        except (ValueError, TypeError):
            respuesta.set_success(False)
            respuesta.set_message('El parámetro materia_asignada_id debe ser entero.')
            respuesta.set_errors({'materia_asignada_id': ['Formato de entero inválido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            datos_notas = portal.notas_de_estudiante(
                persona_id=student_id,
                periodo_id=periodo_id,
                materia_asignada_id=materia_asignada_id
            )
        except LookupError:
            respuesta.set_success(False)
            respuesta.set_message('Materia no encontrada o no pertenece al estudiante.')
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Error al obtener calificaciones.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Notas recuperadas con éxito.')
        respuesta.set_data(datos_notas)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class RepresentativeStudentAttendanceView(APIView):
    """
    GET /api/v1.0.0/movil/representative/students/<int:student_id>/attendance/

    Devuelve el consolidado de asistencia de un estudiante.
    Verifica parentesco mediante portal.representa_a.
    """
    permission_classes = [IsAuthenticated, EsRepresentanteDelEstudiante]

    def get(self, request, student_id):
        respuesta = RespuestaApi()

        periodo_hdr = request.headers.get('X-Period-ID') or request.META.get('HTTP_X_PERIOD_ID')
        if not periodo_hdr:
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID es requerido.')
            respuesta.set_errors({'X-Period-ID': ['Este header es obligatorio.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            periodo_id = int(periodo_hdr)
        except (ValueError, TypeError):
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID debe ser entero.')
            respuesta.set_errors({'X-Period-ID': ['Formato de entero inválido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            datos_asistencia = portal.asistencia_de_estudiante(
                persona_id=student_id,
                periodo_id=periodo_id
            )
        except LookupError:
            respuesta.set_success(False)
            respuesta.set_message('Asistencia no encontrada para el estudiante.')
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Error al obtener asistencia.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Asistencia recuperada con éxito.')
        respuesta.set_data(datos_asistencia)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class RepresentativeStudentScheduleView(APIView):
    """
    GET /api/v1.0.0/movil/representative/students/<int:student_id>/schedule/

    Devuelve el horario semanal del estudiante.
    Verifica parentesco mediante portal.representa_a.
    """
    permission_classes = [IsAuthenticated, EsRepresentanteDelEstudiante]

    def get(self, request, student_id):
        respuesta = RespuestaApi()

        periodo_hdr = request.headers.get('X-Period-ID') or request.META.get('HTTP_X_PERIOD_ID')
        if not periodo_hdr:
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID es requerido.')
            respuesta.set_errors({'X-Period-ID': ['Este header es obligatorio.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            periodo_id = int(periodo_hdr)
        except (ValueError, TypeError):
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID debe ser entero.')
            respuesta.set_errors({'X-Period-ID': ['Formato de entero inválido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            datos_horario = portal.horario_de_estudiante(
                persona_id=student_id,
                periodo_id=periodo_id
            )
        except LookupError:
            respuesta.set_success(False)
            respuesta.set_message('Horario no encontrado para el estudiante.')
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Error al obtener el horario.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Horario recuperado con éxito.')
        respuesta.set_data(datos_horario)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class RepresentativeStudentSummaryView(APIView):
    """
    GET /api/v1.0.0/movil/representative/students/<int:student_id>/summary/

    Devuelve el resumen académico consolidado de un estudiante para el dashboard.
    Verifica parentesco mediante el permiso EsRepresentanteDelEstudiante.
    """
    permission_classes = [IsAuthenticated, EsRepresentanteDelEstudiante]

    def get(self, request, student_id):
        respuesta = RespuestaApi()

        periodo_hdr = request.headers.get('X-Period-ID') or request.META.get('HTTP_X_PERIOD_ID')
        if not periodo_hdr:
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID es requerido.')
            respuesta.set_errors({'X-Period-ID': ['Este header es obligatorio.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            periodo_id = int(periodo_hdr)
        except (ValueError, TypeError):
            respuesta.set_success(False)
            respuesta.set_message('Header X-Period-ID debe ser entero.')
            respuesta.set_errors({'X-Period-ID': ['Formato de entero inválido.']})
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        try:
            datos_resumen = portal.resumen_estudiante(
                persona_id=student_id,
                periodo_id=periodo_id
            )
        except LookupError:
            respuesta.set_success(False)
            respuesta.set_message('Resumen no encontrado para el estudiante en este periodo.')
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Error al obtener el resumen académico.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Resumen académico recuperado con éxito.')
        respuesta.set_data(datos_resumen)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()




class RepresentativeStudentRubrosView(APIView):
    """
    GET /api/v1.0.0/movil/representative/students/<int:student_id>/fees/
    GET /api/v1.0.0/movil/representative/students/<int:student_id>/rubros/

    Devuelve el estado de cuenta y pensiones de un estudiante representado.
    Verifica parentesco mediante EsRepresentanteDelEstudiante.
    """
    permission_classes = [IsAuthenticated, EsRepresentanteDelEstudiante]

    def get(self, request, student_id):
        respuesta = RespuestaApi()
        periodo_id = request.headers.get('X-Period-ID') or request.query_params.get('periodo_id') or request.query_params.get('period_id')
        try:
            from app.student_ports import obtener_rubros_estudiante, _query_one
            sql = "SELECT persona_id FROM ctr_estudiante WHERE id = %s LIMIT 1"
            row = _query_one(sql, [student_id])
            persona_id = row['persona_id'] if row else student_id

            data = obtener_rubros_estudiante(persona_id, periodo_id)
            respuesta.set_success(True)
            respuesta.set_message("Rubros y pensiones obtenidos exitosamente.")
            respuesta.set_data(data)
            respuesta.set_status(status.HTTP_200_OK)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message(f"Error al obtener rubros: {str(e)}")
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class RepresentativeWardsView(APIView):
    """
    GET /api/v1.0.0/movil/representative/wards/

    Devuelve la lista de estudiantes representados por el usuario autenticado.
    Prioriza registros reales de la base de datos (ctr_familiar / ctr_estudiante)
    y enlaza con el puerto institucional portal.representados_de.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from rest_framework.response import Response
        from app.student_ports import _query_all, _query_one
        from sige_ports import portal

        persona_id = getattr(request.user, 'persona_id', None)
        if not persona_id:
            row_p = _query_one("SELECT id FROM ctr_persona WHERE usuario_id = %s", [request.user.id])
            persona_id = row_p['id'] if row_p else request.user.id

        # 1. Buscar en ctr_familiar en la base de datos real
        try:
            sql = """
                SELECT DISTINCT
                    e.id as estudiante_id,
                    p.id as persona_id,
                    TRIM(p.nombres || ' ' || p.apellido_1 || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo,
                    COALESCE(niv.nombre, 'EGB') as nivel,
                    COALESCE(par.nombre, 'A') as paralelo,
                    p.foto as avatar
                FROM ctr_familiar f
                JOIN ctr_persona pf ON pf.id = f.persona_id
                JOIN ctr_persona p ON p.id = f.personafamiliar_id
                JOIN ctr_estudiante e ON e.persona_id = p.id
                LEFT JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
                LEFT JOIN ctr_nivel niv ON niv.id = m.nivel_id
                LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
                WHERE pf.usuario_id = %s AND f.representante = TRUE AND f.status = TRUE
                ORDER BY nombre_completo ASC
            """
            db_wards = _query_all(sql, [request.user.id])
            if db_wards:
                return Response({
                    'isSuccess': True,
                    'message': 'Representados obtenidos con exito.',
                    'data': db_wards
                }, status=status.HTTP_200_OK)
        except Exception:
            pass

        # 2. Si no tiene en ctr_familiar o es usuario de prueba representativo, usar puerto institucional
        try:
            wards = portal.representados_de(persona_id) or []
        except Exception:
            wards = []

        return Response({
            'isSuccess': True,
            'message': 'Representados obtenidos con exito.',
            'data': wards
        }, status=status.HTTP_200_OK)
