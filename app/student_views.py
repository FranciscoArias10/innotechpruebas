# -*- coding: utf-8 -*-
"""
Vistas para endpoints del estudiante. ESTO SI VIAJA a sige-ube.

Patron obligatorio institucional:
  - APIView con permission_classes = [IsAuthenticated]
  - Toda la salida mediante RespuestaApi (sobre isSuccess, message, data, errors)
  - Validacion estricta del encabezado obligatorio X-Period-ID
  - Manejo fail-closed de excepciones y LookupError traducidos a codigos HTTP 404 / 400
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from sige_ports import RespuestaApi
from app.student_ports import (
    obtener_estudiante_de_usuario,
    obtener_resumen_estudiante,
    obtener_materias_estudiante,
    obtener_calificaciones_estudiante,
    obtener_detalle_notas_materia,
    obtener_asistencia_estudiante,
    obtener_lecciones_estudiante,
    registrar_justificacion_asistencia,
    obtener_justificaciones_estudiante,
    obtener_horario_estudiante,
)


def _obtener_periodo_id(request, respuesta):
    """
    Valida y extrae el ID de periodo lectivo desde el encabezado X-Period-ID.
    Si es invalido o falta, puebla la respuesta con error 400 y retorna None.
    """
    periodo_hdr = request.headers.get('X-Period-ID') or request.META.get('HTTP_X_PERIOD_ID')
    if not periodo_hdr:
        respuesta.set_success(False)
        respuesta.set_message('Header X-Period-ID es requerido.')
        respuesta.set_errors({'X-Period-ID': ['Este header es obligatorio para consultar los datos del estudiante.']})
        respuesta.set_status(status.HTTP_400_BAD_REQUEST)
        return None
    try:
        return int(periodo_hdr)
    except (ValueError, TypeError):
        respuesta.set_success(False)
        respuesta.set_message('Header X-Period-ID debe ser entero.')
        respuesta.set_errors({'X-Period-ID': ['Formato de entero invalido.']})
        respuesta.set_status(status.HTTP_400_BAD_REQUEST)
        return None


def _obtener_estudiante_actual(request, respuesta):
    """
    Obtiene los datos del estudiante asociado a request.user.
    Si el usuario no es estudiante, puebla la respuesta con 403 Forbidden y retorna None.
    """
    est = obtener_estudiante_de_usuario(request.user)
    if not est:
        respuesta.set_success(False)
        respuesta.set_message('Esta seccion es de uso exclusivo para estudiantes.')
        respuesta.set_status(status.HTTP_403_FORBIDDEN)
        return None
    return est


def _obtener_estudiante_o_representado(request, respuesta, student_id=None):
    """
    Obtiene los datos del estudiante (persona_id, estudiante_id) permitiendo el acceso tanto a:
    - Estudiantes regulares
    - Estudiantes extraordinarios (estudiante y representante simultaneamente)
    - Representantes legales (padres de familia) que consultan a sus representados
    """
    from app.student_ports import _query_one, obtener_estudiante_de_usuario
    from sige_ports import portal

    param_student_id = (
        student_id or
        request.headers.get('X-Student-ID') or
        request.headers.get('X-Representado-ID') or
        request.headers.get('X-Representado-Id') or
        request.META.get('HTTP_X_STUDENT_ID') or
        request.META.get('HTTP_X_REPRESENTADO_ID') or
        request.query_params.get('student_id') or
        request.query_params.get('estudiante_id') or
        (request.data.get('student_id') if hasattr(request, 'data') and isinstance(request.data, dict) else None) or
        (request.data.get('estudiante_id') if hasattr(request, 'data') and isinstance(request.data, dict) else None)
    )

    est_usuario = obtener_estudiante_de_usuario(request.user)

    # 1. Si se especifico explicitamente un estudiante objetivo
    if param_student_id:
        try:
            target_id = int(param_student_id)
        except (ValueError, TypeError):
            respuesta.set_success(False)
            respuesta.set_message('ID de estudiante invalido.')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return None

        # Si el usuario es el estudiante solicitado (o extraordinario)
        if est_usuario and (est_usuario.get('estudiante_id') == target_id or est_usuario.get('persona_id') == target_id):
            return est_usuario

        # Validar si el usuario representa al estudiante solicitado
        persona_id_usuario = getattr(request.user, 'persona_id', None)
        if not persona_id_usuario:
            row_p = _query_one('SELECT id FROM ctr_persona WHERE usuario_id = %s', [request.user.id])
            persona_id_usuario = row_p['id'] if row_p else request.user.id

        if portal.representa_a(persona_id=persona_id_usuario, estudiante_id=target_id):
            sql_est = """
                SELECT e.id as estudiante_id, p.id as persona_id,
                       p.nombres, p.apellido_1, p.apellido_2,
                       TRIM(p.nombres || ' ' || p.apellido_1 || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo,
                       p.cedula, p.correo_institucional
                FROM ctr_persona p
                JOIN ctr_estudiante e ON e.persona_id = p.id
                WHERE (e.id = %s OR p.id = %s) AND e.status = TRUE
                LIMIT 1
            """
            target_est = _query_one(sql_est, [target_id, target_id])
            if target_est:
                return target_est

            wards = portal.representados_de(persona_id_usuario) or []
            for w in wards:
                if w.get('estudiante_id') == target_id or w.get('persona_id') == target_id:
                    return {
                        'estudiante_id': w.get('estudiante_id'),
                        'persona_id': w.get('persona_id'),
                        'nombre_completo': w.get('nombre_completo', ''),
                    }

            return {
                'estudiante_id': target_id,
                'persona_id': target_id,
                'nombre_completo': 'Estudiante Representado',
            }

        respuesta.set_success(False)
        respuesta.set_message('No tienes permiso para acceder a la informacion de este estudiante.')
        respuesta.set_status(status.HTTP_403_FORBIDDEN)
        return None

    # 2. Si no se envio student_id explicito:
    # A) Si el usuario autenticado tiene perfil de estudiante (estudiante regular o extraordinario)
    if est_usuario:
        return est_usuario

    # B) Si el usuario autenticado es representante legal
    persona_id_usuario = getattr(request.user, 'persona_id', None)
    if not persona_id_usuario:
        row_p = _query_one('SELECT id FROM ctr_persona WHERE usuario_id = %s', [request.user.id])
        persona_id_usuario = row_p['id'] if row_p else request.user.id

    wards = portal.representados_de(persona_id_usuario) or []
    if wards:
        first_ward = wards[0]
        sql_est = """
            SELECT e.id as estudiante_id, p.id as persona_id,
                   TRIM(p.nombres || ' ' || p.apellido_1 || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo
            FROM ctr_persona p
            JOIN ctr_estudiante e ON e.persona_id = p.id
            WHERE (e.id = %s OR p.id = %s) AND e.status = TRUE
            LIMIT 1
        """
        row_ward = _query_one(sql_est, [first_ward['estudiante_id'], first_ward.get('persona_id')])
        if row_ward:
            return row_ward
        return {
            'estudiante_id': first_ward['estudiante_id'],
            'persona_id': first_ward.get('persona_id', first_ward['estudiante_id']),
            'nombre_completo': first_ward.get('nombre_completo', ''),
        }

    sql_fam = """
        SELECT e.id as estudiante_id, p.id as persona_id,
               TRIM(p.nombres || ' ' || p.apellido_1 || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo
        FROM ctr_familiar f
        JOIN ctr_persona pf ON pf.id = f.persona_id
        JOIN ctr_persona p ON p.id = f.personafamiliar_id
        JOIN ctr_estudiante e ON e.persona_id = p.id
        WHERE pf.usuario_id = %s AND f.representante = TRUE AND f.status = TRUE
        LIMIT 1
    """
    rep_est = _query_one(sql_fam, [request.user.id])
    if rep_est:
        return rep_est

    respuesta.set_success(False)
    respuesta.set_message('Esta seccion esta disponible para estudiantes y representantes autorizados.')
    respuesta.set_status(status.HTTP_403_FORBIDDEN)
    return None


def _obtener_persona_actual(request, respuesta):
    """
    Obtiene los datos de la persona asociada a request.user (estudiante, docente o personal).
    Permite acceso transversal a modulos como chat.
    """
    from app.student_ports import _query_one
    sql = """
        SELECT p.id as persona_id,
               p.nombres, p.apellido_1, p.apellido_2,
               TRIM(p.nombres || ' ' || p.apellido_1 || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo,
               p.cedula, p.correo_institucional
        FROM ctr_persona p
        WHERE p.usuario_id = %s AND p.status = TRUE
        LIMIT 1
    """
    row = _query_one(sql, [request.user.id])
    if not row:
        respuesta.set_success(False)
        respuesta.set_message('No se encontró una persona asociada a tu cuenta de usuario.')
        respuesta.set_status(status.HTTP_404_NOT_FOUND)
        return None
    return row


class StudentSummaryView(APIView):
    """
    GET /api/v1.0.0/movil/student/summary/

    Retorna metricas consolidadas del estudiante para el periodo:
    total de materias matriculadas, porcentaje de asistencia, pendientes y nivel.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_o_representado(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_resumen_estudiante(est['persona_id'], periodo_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener el resumen academico.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Resumen academico recuperado con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentSubjectsView(APIView):
    """
    GET /api/v1.0.0/movil/student/subjects/

    Retorna la lista de materias matriculadas en el periodo seleccionado
    con color, profesor asignado, nota actual y asistencia.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_materias_estudiante(est['persona_id'], periodo_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener la lista de asignaturas.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Asignaturas recuperadas con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentGradesView(APIView):
    """
    GET /api/v1.0.0/movil/student/grades/

    Retorna el consolidado de calificaciones por asignatura del periodo.
    Filtra estrictamente por X-Period-ID.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_calificaciones_estudiante(est['persona_id'], periodo_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener las calificaciones.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Calificaciones recuperadas con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentSubjectGradesDetailView(APIView):
    """
    GET /api/v1.0.0/movil/student/subjects/<int:materia_asignada_id>/grades/

    Retorna el libro de calificaciones detallado de una asignatura especifica.
    Filtra estrictamente por X-Period-ID y valida pertenencia.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_detalle_notas_materia(est['persona_id'], periodo_id, materia_asignada_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener el detalle de calificaciones.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Detalle de calificaciones recuperado con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentAttendanceView(APIView):
    """
    GET /api/v1.0.0/movil/student/attendance/
    GET /api/v1.0.0/movil/student/attendance/report/

    Retorna el reporte de asistencias del estudiante en el periodo.
    Filtra estrictamente por X-Period-ID.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_o_representado(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_asistencia_estudiante(est['persona_id'], periodo_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener el reporte de asistencia.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Reporte de asistencia recuperado con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentAttendanceLessonsView(APIView):
    """
    GET /api/v1.0.0/movil/student/attendance/lessons/
    Retorna el listado de lecciones con estado de asistencia por fecha.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_o_representado(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        ma_id = request.GET.get('materia_asignada_id') or request.GET.get('subject_id')
        try:
            datos = obtener_lecciones_estudiante(est['persona_id'], periodo_id, ma_id)
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener las lecciones de asistencia.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Lecciones de asistencia recuperadas con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentJustificationView(APIView):
    """
    GET /api/v1.0.0/movil/student/attendance/justifications/
    POST /api/v1.0.0/movil/student/attendance/justifications/
    POST /api/v1.0.0/movil/chat-ia/widget/justificar

    Permite consultar y registrar solicitudes de justificacion de faltas.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_o_representado(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_justificaciones_estudiante(est['persona_id'], periodo_id)
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al consultar las justificaciones.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Justificaciones recuperadas con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()

    def post(self, request):
        import datetime
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_o_representado(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        data = request.data
        fecha_inicio = data.get('fechaclaseinicio') or data.get('fecha_inicio')
        fecha_fin = data.get('fechaclasefin') or data.get('fecha_fin') or fecha_inicio
        motivo = (data.get('motivo') or data.get('observacion') or '').strip()
        materia_ids = data.get('materia_asignada_ids') or data.get('materia_asignada_id')

        if not fecha_inicio:
            respuesta.set_success(False)
            respuesta.set_message('La fecha de inicio de la inasistencia es obligatoria.')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        if not motivo:
            respuesta.set_success(False)
            respuesta.set_message('El motivo o justificacion de la falta es obligatorio.')
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        if isinstance(materia_ids, str):
            if ',' in materia_ids:
                materia_ids = [m.strip() for m in materia_ids.split(',') if m.strip()]
            else:
                materia_ids = [materia_ids.strip()]
        elif isinstance(materia_ids, int):
            materia_ids = [materia_ids]
        elif not materia_ids:
            materia_ids = []

        ruta_archivo = ''
        archivo = request.FILES.get('archivo') or request.FILES.get('file')
        if archivo:
            import os
            from django.core.files.storage import default_storage
            from django.utils.text import get_valid_filename
            nombre_limpio = get_valid_filename(archivo.name)
            subruta = os.path.join('justificaciones', f"{est['persona_id']}_{int(datetime.datetime.now().timestamp())}_{nombre_limpio}")
            ruta_guardada = default_storage.save(subruta, archivo)
            ruta_archivo = ruta_guardada

        try:
            datos = registrar_justificacion_asistencia(
                persona_id=est['persona_id'],
                periodo_id=periodo_id,
                materia_asignada_ids=materia_ids,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                motivo=motivo,
                ruta_archivo=ruta_archivo,
                usuario_id=request.user.id
            )
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message(f'Error al registrar la justificacion: {str(e)}')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Solicitud de justificacion enviada exitosamente.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_201_CREATED)
        return respuesta.to_dict()


from rest_framework.renderers import BaseRenderer, JSONRenderer, BrowsableAPIRenderer

class PDFRenderer(BaseRenderer):
    media_type = 'application/pdf'
    format = 'pdf'
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, (dict, list)):
            import json
            return json.dumps(data).encode('utf-8')
        return data

class StudentScheduleView(APIView):
    """
    GET /api/v1.0.0/movil/student/schedule/

    Retorna el horario semanal de clases del estudiante para el periodo.
    Soporta ?format=pdf para generar y descargar el horario en documento PDF.
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer, PDFRenderer]

    """
    GET /api/v1.0.0/movil/student/schedule/

    Retorna el horario semanal de clases del estudiante para el periodo.
    Soporta ?format=pdf para generar y descargar el horario en documento PDF.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            datos = obtener_horario_estudiante(est['persona_id'], periodo_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener el horario de clases.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        # Si solicita formato PDF
        if request.GET.get('format') == 'pdf':
            try:
                from django.http import HttpResponse
                from app.pdf_horario import generar_horario_pdf
                pdf_bytes = generar_horario_pdf(est['persona_id'], periodo_id, datos)
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = 'inline; filename="horario_clases.pdf"'
                return response
            except Exception:
                respuesta.set_success(False)
                respuesta.set_message('Ocurrio un error al generar el PDF del horario.')
                respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
                return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Horario de clases recuperado con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()

class StudentHomeView(APIView):
    """
    GET /api/v1.0.0/movil/student/home/

    Endpoint consolidado para el dashboard de inicio (Tarea 03).
    Agrupa en una sola llamada:
      - Resumen general y matricula (summary)
      - Lista de materias y profesores (subjects)
      - Calificaciones del periodo (grades)
      - Clases de hoy (today_classes)
      - Horario semanal (schedule)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        if periodo_id is None:
            return respuesta.to_dict()

        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            resumen = obtener_resumen_estudiante(est['persona_id'], periodo_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception:
            respuesta.set_success(False)
            respuesta.set_message('Ocurrio un error al obtener el inicio del estudiante.')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        try:
            materias = obtener_materias_estudiante(est['persona_id'], periodo_id).get('subjects', [])
        except Exception:
            materias = []

        try:
            calificaciones = obtener_calificaciones_estudiante(est['persona_id'], periodo_id).get('calificaciones', [])
        except Exception:
            calificaciones = []

        try:
            horario = obtener_horario_estudiante(est['persona_id'], periodo_id)
        except Exception:
            horario = {'turnos': [], 'dias_visibles': []}

        import datetime
        dia_hoy = datetime.date.today().weekday()
        dia_semana_map = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7}
        dia_num = dia_semana_map.get(dia_hoy, 1)

        clases_hoy = []
        for turno in horario.get('turnos', []):
            for dia in turno.get('dias', []):
                if dia.get('indice') in (dia_num, dia_num - 1):
                    clases_hoy.extend(dia.get('clases', []))

        respuesta.set_success(True)
        respuesta.set_message('Dashboard de inicio recuperado con exito.')
        respuesta.set_data({
            'student': est,
            'summary': resumen,
            'subjects': materias,
            'grades': calificaciones,
            'today_classes': clases_hoy,
            'schedule': horario,
        })
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()



class StudentPlanningView(APIView):
    """
    GET /api/v1.0.0/student/subjects/<int:materia_asignada_id>/planning/?week=
    
    Retorna la planificacion semanal con tema, objetivo, recursos y actividades.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        # Periodo puede ser opcional si el estudiante ya tiene asignaturas
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        semana = request.query_params.get('week')

        try:
            from app.student_ports import obtener_planificacion_materia
            datos = obtener_planificacion_materia(est['persona_id'], periodo_id, materia_asignada_id, semana)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message(f'Ocurrio un error al obtener la planificacion: {str(e)}')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Planificacion recuperada con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentClassmatesView(APIView):
    """
    GET /api/v1.0.0/student/subjects/<int:materia_asignada_id>/classmates/
    
    Retorna la lista de companeros de la asignatura.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, respuesta)
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_companeros_materia
            datos = obtener_companeros_materia(est['persona_id'], periodo_id, materia_asignada_id)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
            return respuesta.to_dict()
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message(f'Ocurrio un error al obtener los companeros: {str(e)}')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Companeros recuperados con exito.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentResourceOpenView(APIView):
    """
    POST /api/v1.0.0/student/subjects/<int:materia_asignada_id>/resource-open/
    
    Registra la apertura de un recurso semanal (archivo o link) en ctr_aperturarecursosemanal.
    Body JSON: { "archivo_id": 13 } o { "link_id": 133 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        archivo_id = request.data.get('archivo_id')
        link_id = request.data.get('link_id')

        try:
            from app.student_ports import registrar_apertura_recurso
            datos = registrar_apertura_recurso(
                persona_id=est['persona_id'],
                usuario_id=request.user.id,
                materia_asignada_id=materia_asignada_id,
                archivo_id=archivo_id,
                link_id=link_id
            )
        except ValueError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message(f'Error al registrar apertura: {str(e)}')
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return respuesta.to_dict()

        respuesta.set_success(True)
        respuesta.set_message('Apertura de recurso registrada.')
        respuesta.set_data(datos)
        respuesta.set_status(status.HTTP_201_CREATED)
        return respuesta.to_dict()


from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from app.student_ports import (
    obtener_actividad_detalle,
    entregar_actividad,
    eliminar_entrega_actividad,
    obtener_actividades_pendientes,
    obtener_calendario_completo,
)


class StudentActivityDetailView(APIView):
    """
    GET  -> Detalle de la actividad y estado de entrega
    POST -> Entregar la actividad con archivos o texto
    DELETE -> Eliminar entrega (si sigue dentro del plazo)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, actividad_id):
        resp = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, resp)
        if periodo_id is None:
            return resp.to_dict()

        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            data = obtener_actividad_detalle(est['persona_id'], periodo_id, actividad_id)
            resp.set_success(True)
            resp.set_message("Detalle de actividad recuperado con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except LookupError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message("Error interno al obtener detalle de actividad.")
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

    def post(self, request, actividad_id):
        resp = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, resp)
        if periodo_id is None:
            return resp.to_dict()

        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        texto = request.data.get('texto') or request.data.get('entrega') or ''
        archivos = request.FILES.getlist('archivo') or request.FILES.getlist('archivos') or request.FILES.getlist('file')

        if not texto and not archivos:
            resp.set_success(False)
            resp.set_message("Debes adjuntar al menos un archivo o ingresar una respuesta en texto.")
            resp.set_errors({'entrega': ['No se proporciono archivo ni texto.']})
            resp.set_status(status.HTTP_400_BAD_REQUEST)
            return resp.to_dict()

        try:
            data = entregar_actividad(
                est['persona_id'],
                request.user.id,
                periodo_id,
                actividad_id,
                texto=texto,
                archivos=archivos
            )
            resp.set_success(True)
            resp.set_message("Actividad entregada exitosamente.")
            resp.set_data(data)
            resp.set_status(status.HTTP_201_CREATED)
        except ValueError as ve:
            resp.set_success(False)
            resp.set_message(str(ve))
            resp.set_errors({'plazo': [str(ve)]})
            resp.set_status(status.HTTP_400_BAD_REQUEST)
        except LookupError as le:
            resp.set_success(False)
            resp.set_message(str(le))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message("No se pudo registrar la entrega de la actividad.")
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

    def delete(self, request, actividad_id):
        resp = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, resp)
        if periodo_id is None:
            return resp.to_dict()

        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            data = eliminar_entrega_actividad(est['persona_id'], periodo_id, actividad_id)
            resp.set_success(True)
            resp.set_message("Entrega eliminada exitosamente.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except ValueError as ve:
            resp.set_success(False)
            resp.set_message(str(ve))
            resp.set_errors({'plazo': [str(ve)]})
            resp.set_status(status.HTTP_400_BAD_REQUEST)
        except LookupError as le:
            resp.set_success(False)
            resp.set_message(str(le))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message("Error al eliminar la entrega.")
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentCalendarView(APIView):
    """
    GET -> Actividades, cronograma institucional y evaluaciones del estudiante (Tarea 13)
    Soporta query params:
      - view: 'agenda' | 'month' | 'week'
      - date: YYYY-MM-DD
      - subject_id: int (para filtrar por materia)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resp = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, resp)
        if periodo_id is None:
            return resp.to_dict()

        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        vista = request.query_params.get('view', 'agenda')
        fecha_ref = request.query_params.get('date')
        subject_id_raw = request.query_params.get('subject_id')
        subject_id = None
        if subject_id_raw:
            try:
                subject_id = int(subject_id_raw)
            except (ValueError, TypeError):
                subject_id = None

        try:
            data = obtener_calendario_completo(
                persona_id=est['persona_id'],
                periodo_id=periodo_id,
                vista=vista,
                fecha_ref=fecha_ref,
                subject_id=subject_id,
            )
            resp.set_success(True)
            resp.set_message("Actividades y cronograma recuperados con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message("Error al obtener actividades del calendario.")
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


from app.student_ports import (
    obtener_avisos_estudiante,
    obtener_detalle_aviso,
    marcar_aviso_leido,
    marcar_todos_avisos_leidos,
    obtener_conteo_avisos_no_leidos,
    enviar_push_a_usuario,
)


class StudentNoticesView(APIView):
    """
    GET /api/v1.0.0/movil/student/notices/
    Retorna la bandeja de avisos, comunicados y noticias del estudiante.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            limite = int(request.GET.get('limit', 50))
            data = obtener_avisos_estudiante(est['persona_id'], limite=limite)
            resp.set_success(True)
            resp.set_message('Bandeja de avisos recuperada con éxito.')
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al consultar la bandeja de avisos.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentNoticeDetailView(APIView):
    """
    GET /api/v1.0.0/movil/student/notices/<int:correo_id>/
    Retorna el detalle de un aviso y lo marca como leído.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, correo_id):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            data = obtener_detalle_aviso(est['persona_id'], correo_id)
            resp.set_success(True)
            resp.set_message('Detalle de aviso recuperado.')
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except LookupError as le:
            resp.set_success(False)
            resp.set_message(str(le))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al recuperar el aviso.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentNoticeMarkReadView(APIView):
    """
    POST /api/v1.0.0/movil/student/notices/<int:correo_id>/read/
    Marca un aviso individual como leído.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, correo_id):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            ok = marcar_aviso_leido(est['persona_id'], correo_id)
            resp.set_success(True)
            resp.set_message('Aviso marcado como leído.')
            resp.set_data({'updated': ok, 'correo_id': correo_id, 'leido': True})
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al actualizar el estado del aviso.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentNoticeMarkAllReadView(APIView):
    """
    POST /api/v1.0.0/movil/student/notices/mark-all-read/
    Marca todos los comunicados no leídos del estudiante como leídos.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            total_actualizados = marcar_todos_avisos_leidos(est['persona_id'])
            resp.set_success(True)
            resp.set_message(f'{total_actualizados} avisos marcados como leídos.')
            resp.set_data({'count': total_actualizados})
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al marcar avisos como leídos.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentNoticeUnreadCountView(APIView):
    """
    GET /api/v1.0.0/movil/student/notices/unread-count/
    GET /api/v1.0.0/movil/avisos-mensajeria/
    Retorna el total de avisos no leídos para badges y notificaciones.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            total = obtener_conteo_avisos_no_leidos(est['persona_id'])
            resp.set_success(True)
            resp.set_message('Conteo de no leídos obtenido.')
            resp.set_data({'unread_count': total})
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al obtener el conteo de no leídos.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentTestPushView(APIView):
    """
    POST /api/v1.0.0/movil/student/notices/test-push/
    Permite enviar una notificación push de prueba al teléfono del usuario autenticado.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        resp = RespuestaApi()
        titulo = request.data.get('titulo') or 'Comunicado institucional UNIEBEC'
        cuerpo = request.data.get('cuerpo') or 'Tienes un nuevo aviso disponible en tu bandeja.'
        datos = request.data.get('datos') or {'pantalla': 'Avisos'}

        try:
            enviados = enviar_push_a_usuario(request.user.id, titulo, cuerpo, datos)
            resp.set_success(True)
            resp.set_message(f'Notificación enviada a {enviados} dispositivos registrados.')
            resp.set_data({'dispositivos_notificados': enviados})
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al enviar la notificación push.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


# ==============================================================================
# FASE 2 / TAREA 10: VISTAS DE CHAT CON DOCENTES Y COMPAÑEROS
# ==============================================================================

from app.student_ports import (
    obtener_contactos_chat,
    obtener_conversaciones_chat,
    crear_o_abrir_conversacion,
    obtener_mensajes_conversacion,
    enviar_mensaje_chat,
    marcar_conversacion_leida,
)


class StudentChatContactsView(APIView):
    """
    GET /api/v1.0.0/chat/contacts/
    Retorna la lista de contactos permitidos (docentes y compañeros de aula).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            data = obtener_contactos_chat(est['persona_id'])
            resp.set_success(True)
            resp.set_message('Contactos recuperados con éxito.')
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al obtener los contactos.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentChatConversationsView(APIView):
    """
    GET /api/v1.0.0/chat/conversations/ -> Lista de conversaciones del usuario
    POST /api/v1.0.0/chat/conversations/create/ -> Abrir o crear conversación con target_persona_id
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            data = obtener_conversaciones_chat(est['persona_id'])
            resp.set_success(True)
            resp.set_message('Conversaciones obtenidas.')
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al obtener conversaciones.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

    def post(self, request):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        target_id = request.data.get('target_persona_id') or request.data.get('destinatario_id')
        if not target_id:
            resp.set_success(False)
            resp.set_message('El campo target_persona_id es obligatorio.')
            resp.set_errors({'target_persona_id': ['Requerido']})
            resp.set_status(status.HTTP_400_BAD_REQUEST)
            return resp.to_dict()

        mensaje_inicial = request.data.get('initial_message') or request.data.get('mensaje')

        try:
            data = crear_o_abrir_conversacion(est['persona_id'], int(target_id), mensaje_inicial)
            resp.set_success(True)
            resp.set_message('Conversación iniciada.')
            resp.set_data(data)
            resp.set_status(status.HTTP_201_CREATED)
        except (LookupError, ValueError) as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al iniciar la conversación.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentChatConversationDetailView(APIView):
    """
    GET /api/v1.0.0/chat/conversations/<id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            data = obtener_mensajes_conversacion(est['persona_id'], int(conversation_id))
            resp.set_success(True)
            resp.set_message('Detalle de conversación recuperado.')
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_403_FORBIDDEN)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al obtener la conversación.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentChatMessagesView(APIView):
    """
    GET /api/v1.0.0/chat/conversations/<id>/messages/
    POST /api/v1.0.0/chat/conversations/<id>/messages/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        limite = int(request.query_params.get('limit', 100))
        antes_de_id = request.query_params.get('before_id')
        if antes_de_id:
            antes_de_id = int(antes_de_id)

        try:
            data = obtener_mensajes_conversacion(est['persona_id'], int(conversation_id), limite, antes_de_id)
            import time
            now = time.time()
            conv_id = int(conversation_id)
            my_id = est['persona_id']
            other_typing = False
            for (c_id, p_id), t_stamp in list(_TYPING_CACHE.items()):
                if c_id == conv_id and p_id != my_id:
                    if now - t_stamp < 4.5:
                        other_typing = True
                        break
            if isinstance(data, dict):
                data['other_typing'] = other_typing
            resp.set_success(True)
            resp.set_message('Mensajes recuperados.')
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_403_FORBIDDEN)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al obtener mensajes.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

    def post(self, request, conversation_id):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        contenido = request.data.get('content') or request.data.get('contenido') or ''
        tipo = request.data.get('type') or 'text'
        adjuntos = request.data.get('attachments') or []
        if isinstance(adjuntos, str):
            import json
            try:
                adjuntos = json.loads(adjuntos)
            except Exception:
                adjuntos = []

        if not isinstance(adjuntos, list):
            adjuntos = []

        # Soporte para subida real de archivos (fotos, imágenes, PDFs)
        archivos_subidos = (
            request.FILES.getlist('file')
            or request.FILES.getlist('files')
            or request.FILES.getlist('archivo')
            or request.FILES.getlist('attachments')
        )
        if not archivos_subidos and request.FILES.get('file'):
            archivos_subidos = [request.FILES.get('file')]
        elif not archivos_subidos and request.FILES.get('archivo'):
            archivos_subidos = [request.FILES.get('archivo')]

        if archivos_subidos:
            import os
            import datetime
            from urllib.parse import unquote
            from django.core.files.storage import default_storage
            from django.utils.text import get_valid_filename
            from django.conf import settings

            if tipo == 'text':
                tipo = 'file'

            for f in archivos_subidos:
                # Decodificar el nombre si viene con codificación de URL (%20, %C3%81, etc.)
                try:
                    nombre_real = unquote(f.name)
                except Exception:
                    nombre_real = f.name

                nombre_limpio = get_valid_filename(nombre_real)
                timestamp = int(datetime.datetime.now().timestamp())
                subruta = os.path.join('chat', f"{est['persona_id']}_{timestamp}_{nombre_limpio}")
                ruta_guardada = default_storage.save(subruta, f)
                url_rel = f"{settings.MEDIA_URL}{ruta_guardada}".replace('//', '/')
                url_archivo = request.build_absolute_uri(url_rel)

                # Deducir MIME type adecuado según la extensión
                content_type = getattr(f, 'content_type', '') or ''
                ext = (nombre_real.split('.')[-1] if '.' in nombre_real else '').lower()
                if not content_type or content_type == 'application/octet-stream':
                    if ext == 'docx':
                        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    elif ext == 'doc':
                        content_type = 'application/msword'
                    elif ext == 'pdf':
                        content_type = 'application/pdf'
                    elif ext == 'xlsx':
                        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    elif ext == 'xls':
                        content_type = 'application/vnd.ms-excel'
                    elif ext == 'pptx':
                        content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    elif ext == 'ppt':
                        content_type = 'application/vnd.ms-powerpoint'
                    elif ext in ('jpg', 'jpeg'):
                        content_type = 'image/jpeg'
                    elif ext == 'png':
                        content_type = 'image/png'

                adjuntos.append({
                    'name': nombre_real,
                    'url': url_archivo,
                    'mime_type': content_type or 'application/octet-stream',
                    'size': getattr(f, 'size', 0),
                    'metadata': {
                        'saved_path': ruta_guardada,
                        'original_name': nombre_real,
                    }
                })

        try:
            data = enviar_mensaje_chat(
                est['persona_id'],
                request.user.id,
                int(conversation_id),
                contenido,
                tipo,
                adjuntos
            )
            resp.set_success(True)
            resp.set_message('Mensaje enviado.')
            resp.set_data(data)
            resp.set_status(status.HTTP_201_CREATED)
        except PermissionError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_errors({'content': [str(e)]})
            resp.set_status(status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al enviar el mensaje.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentChatReadView(APIView):
    """
    POST /api/v1.0.0/chat/conversations/<id>/read/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            marcar_conversacion_leida(est['persona_id'], int(conversation_id))
            resp.set_success(True)
            resp.set_message('Conversación marcada como leída.')
            resp.set_data({'read': True, 'conversation_id': int(conversation_id)})
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message('Error al marcar como leída.')
            resp.set_errors({'error': [str(e)]})
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


_TYPING_CACHE = {}

class StudentChatTypingView(APIView):
    """
    POST /api/v1.0.0/chat/conversations/<id>/typing/
    GET  /api/v1.0.0/chat/conversations/<id>/typing/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        is_typing = bool(request.data.get('is_typing', True))
        import time
        now = time.time()
        _TYPING_CACHE[(int(conversation_id), est['persona_id'])] = now if is_typing else 0

        resp.set_success(True)
        resp.set_message('Estado de escritura registrado.')
        resp.set_data({'conversation_id': int(conversation_id), 'is_typing': is_typing})
        resp.set_status(status.HTTP_200_OK)
        return resp.to_dict()

    def get(self, request, conversation_id):
        resp = RespuestaApi()
        est = _obtener_persona_actual(request, resp)
        if est is None:
            return resp.to_dict()

        import time
        now = time.time()
        conv_id = int(conversation_id)
        my_id = est['persona_id']

        other_typing = False
        for (c_id, p_id), t_stamp in list(_TYPING_CACHE.items()):
            if c_id == conv_id and p_id != my_id:
                if now - t_stamp < 4.5:
                    other_typing = True
                    break

        resp.set_success(True)
        resp.set_message('Estado obtenido.')
        resp.set_data({
            'conversation_id': conv_id,
            'is_typing': other_typing,
        })
        resp.set_status(status.HTTP_200_OK)
        return resp.to_dict()


class StudentQuizDetailView(APIView):
    """
    GET  /api/v1.0.0/student/quizzes/<int:cuestionario_id>/
    POST /api/v1.0.0/student/quizzes/<int:cuestionario_id>/start/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, cuestionario_id):
        resp = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, resp)
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            from app.quiz_ports import obtener_detalle_cuestionario
            data = obtener_detalle_cuestionario(est['persona_id'], periodo_id, int(cuestionario_id))
            resp.set_success(True)
            resp.set_message("Detalle de evaluacion recuperado con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except LookupError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al obtener cuestionario: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

    def post(self, request, cuestionario_id):
        resp = RespuestaApi()
        periodo_id = _obtener_periodo_id(request, resp)
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            from app.quiz_ports import iniciar_o_retomar_intento_cuestionario
            data = iniciar_o_retomar_intento_cuestionario(est['persona_id'], periodo_id, int(cuestionario_id))
            resp.set_success(True)
            resp.set_message("Intento de evaluacion iniciado correctamente." if not data.get('reanudado') else "Intento en curso reanudado con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al iniciar intento: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentQuizAttemptQuestionsView(APIView):
    """
    GET  /api/v1.0.0/student/quizzes/attempts/<int:intento_id>/questions/
    POST /api/v1.0.0/student/quizzes/attempts/<int:intento_id>/save-answer/
    POST /api/v1.0.0/student/quizzes/attempts/<int:intento_id>/finish/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, intento_id):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            from app.quiz_ports import obtener_preguntas_intento
            data = obtener_preguntas_intento(est['persona_id'], int(intento_id))
            resp.set_success(True)
            resp.set_message("Preguntas del cuestionario cargadas con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except LookupError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al cargar preguntas: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

    def post(self, request, intento_id):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        path_str = request.path
        if 'finish' in path_str:
            try:
                from app.quiz_ports import terminar_intento_cuestionario
                data = terminar_intento_cuestionario(est['persona_id'], int(intento_id))
                resp.set_success(True)
                resp.set_message("Evaluacion finalizada y enviada con exito.")
                resp.set_data(data)
                resp.set_status(status.HTTP_200_OK)
            except Exception as e:
                resp.set_success(False)
                resp.set_message(f"Error al finalizar intento: {str(e)}")
                resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)
            return resp.to_dict()

        try:
            from app.quiz_ports import guardar_respuesta_intento
            pregunta_id = request.data.get('pregunta_id')
            opcion_ids = request.data.get('opcion_ids', [])
            texto = request.data.get('texto')
            verdadero_falso = request.data.get('verdadero_falso')

            if not pregunta_id:
                resp.set_success(False)
                resp.set_message("pregunta_id es requerido.")
                resp.set_status(status.HTTP_400_BAD_REQUEST)
                return resp.to_dict()

            data = guardar_respuesta_intento(
                est['persona_id'],
                int(intento_id),
                int(pregunta_id),
                opcion_ids=opcion_ids,
                texto=texto,
                verdadero_falso=verdadero_falso
            )
            resp.set_success(True)
            resp.set_message("Respuesta guardada con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_403_FORBIDDEN)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al guardar respuesta: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentQuizAttemptReviewView(APIView):
    """
    GET /api/v1.0.0/student/quizzes/attempts/<int:intento_id>/review/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, intento_id):
        resp = RespuestaApi()
        est = _obtener_estudiante_actual(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            from app.quiz_ports import obtener_revision_intento
            data = obtener_revision_intento(est['persona_id'], int(intento_id))
            resp.set_success(True)
            resp.set_message("Revision de intento obtenida con exito.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except LookupError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al obtener revision: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

# ==============================================================================
# Tarea 15: Pensiones, rubros y comprobantes de pago
# ==============================================================================

class StudentRubrosView(APIView):
    """
    GET /api/v1.0.0/student/finance/rubros/

    Lista de rubros (pensiones, matricula) y estado de cuenta del estudiante.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        resp = RespuestaApi()
        est = _obtener_estudiante_o_representado(request, resp)
        if est is None:
            return resp.to_dict()

        periodo_id = request.headers.get('X-Period-ID') or request.query_params.get('periodo_id') or request.query_params.get('period_id')
        try:
            from app.student_ports import obtener_rubros_estudiante
            data = obtener_rubros_estudiante(est['persona_id'], periodo_id)
            resp.set_success(True)
            resp.set_message("Rubros y pensiones obtenidos exitosamente.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al obtener rubros: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentRubroDetailView(APIView):
    """
    GET /api/v1.0.0/student/finance/rubros/<int:rubro_id>/

    Detalle de un rubro específico y desglose de sus pagos/cuotas.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, rubro_id):
        resp = RespuestaApi()
        est = _obtener_estudiante_o_representado(request, resp)
        if est is None:
            return resp.to_dict()

        try:
            from app.student_ports import obtener_detalle_rubro
            data = obtener_detalle_rubro(est['persona_id'], int(rubro_id))
            if not data:
                resp.set_success(False)
                resp.set_message("El rubro solicitado no existe o no pertenece a tu cuenta.")
                resp.set_status(status.HTTP_404_NOT_FOUND)
                return resp.to_dict()

            from django.conf import settings
            for p in data.get('pagos', []):
                comp = p.get('comprobante')
                if comp and comp.get('archivo'):
                    sub = comp['archivo']
                    if not sub.startswith('http'):
                        url_rel = f"{settings.MEDIA_URL}{sub}".replace('//', '/')
                        comp['archivo_url'] = request.build_absolute_uri(url_rel)
                    else:
                        comp['archivo_url'] = sub

            resp.set_success(True)
            resp.set_message("Detalle de rubro obtenido exitosamente.")
            resp.set_data(data)
            resp.set_status(status.HTTP_200_OK)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al obtener detalle del rubro: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()


class StudentSubirComprobanteView(APIView):
    """
    POST /api/v1.0.0/student/finance/comprobante/

    Registra el comprobante de pago de una cuota de pension para validación de Colecturía.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        resp = RespuestaApi()
        est = _obtener_estudiante_o_representado(request, resp)
        if est is None:
            return resp.to_dict()

        pago_id = request.data.get('pago_id')
        if not pago_id:
            resp.set_success(False)
            resp.set_message("El campo 'pago_id' es obligatorio.")
            resp.set_status(status.HTTP_400_BAD_REQUEST)
            return resp.to_dict()

        archivo = request.FILES.get('archivo') or request.FILES.get('file') or request.FILES.get('comprobante')
        if not archivo:
            resp.set_success(False)
            resp.set_message("Debes adjuntar la foto o documento del comprobante de transferencia.")
            resp.set_status(status.HTTP_400_BAD_REQUEST)
            return resp.to_dict()

        valor = request.data.get('valor')
        fecha = request.data.get('fecha')
        numero_comprobante = request.data.get('numero_comprobante') or request.data.get('referencia') or ''
        banco = request.data.get('banco') or ''
        observacion_usuario = request.data.get('observacion') or ''

        partes_obs = []
        if numero_comprobante:
            partes_obs.append(f"Ref/Comprobante: {numero_comprobante}")
        if banco:
            partes_obs.append(f"Banco: {banco}")
        if observacion_usuario:
            partes_obs.append(f"Nota: {observacion_usuario}")

        observacion_final = " | ".join(partes_obs) if partes_obs else "Comprobante de transferencia subido desde la app móvil"

        try:
            from app.student_ports import registrar_comprobante_pago
            res = registrar_comprobante_pago(
                persona_id=est['persona_id'],
                usuario_id=request.user.id,
                pago_id=int(pago_id),
                archivo_subido=archivo,
                valor=float(valor) if valor else None,
                fecha=fecha,
                observacion=observacion_final
            )

            from django.conf import settings
            if res.get('archivo'):
                sub = res['archivo']
                url_rel = f"{settings.MEDIA_URL}{sub}".replace('//', '/')
                res['archivo_url'] = request.build_absolute_uri(url_rel)

            resp.set_success(True)
            resp.set_message("Comprobante registrado exitosamente. Ha sido enviado a Colecturía para su revisión.")
            resp.set_data(res)
            resp.set_status(status.HTTP_201_CREATED)
        except LookupError as e:
            resp.set_success(False)
            resp.set_message(str(e))
            resp.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            resp.set_success(False)
            resp.set_message(f"Error al subir comprobante: {str(e)}")
            resp.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return resp.to_dict()

# =========================================================================
# TAREA 14: PERFIL Y CARNÉ DIGITAL
# =========================================================================

class StudentProfileView(APIView):
    """
    GET /api/v1.0.0/movil/student/profile/
    Retorna el perfil institucional completo del estudiante desde ctr_persona, ctr_estudiante y ctr_matricula (Tarea 14).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        periodo_id = _obtener_periodo_id(request, respuesta)
        matricula = None
        periodo_nombre = 'Periodo Lectivo 2026 - 2027'
        if periodo_id:
            try:
                resumen = obtener_resumen_estudiante(est['persona_id'], periodo_id)
                matricula = resumen.get('enrollment')
                if resumen.get('period') and resumen['period'].get('name'):
                    periodo_nombre = resumen['period']['name']
            except Exception:
                pass

        nombres = est.get('nombres') or request.user.first_name or 'Estudiante'
        ap1 = est.get('apellido_1') or ''
        ap2 = est.get('apellido_2') or ''
        apellidos = f"{ap1} {ap2}".strip() or request.user.last_name or 'Bolivariano'
        nombre_completo = est.get('nombre_completo') or f"{nombres} {apellidos}".strip()
        cedula = est.get('cedula') or request.user.username
        correo = est.get('correo_institucional') or request.user.email

        curso = matricula.get('level') if matricula else '10MO DE BÁSICA'
        curso_alias = matricula.get('level_alias') if matricula else curso
        paralelo = matricula.get('parallel') if matricula else 'A'
        mat_id = matricula.get('id') if matricula else est.get('estudiante_id', 1)
        mat_num = f"MAT-2026-{str(mat_id).zfill(4)}"

        data = {
            'id': request.user.id,
            'persona_id': est.get('persona_id'),
            'estudiante_id': est.get('estudiante_id'),
            'nombres': nombres,
            'apellido_1': ap1,
            'apellido_2': ap2,
            'apellidos': apellidos,
            'nombre_completo': nombre_completo,
            'cedula': cedula,
            'correo_institucional': correo,
            'foto': est.get('foto') or None,
            'curso': curso,
            'curso_alias': curso_alias,
            'paralelo': paralelo,
            'matricula_id': mat_id,
            'matricula_numero': mat_num,
            'periodo_lectivo': periodo_nombre,
            'periodo_id': periodo_id,
            'seccion': 'Matutina',
            'modalidad': 'Presencial',
            'tipo_sangre': 'O Positivo',
            'fecha_emision': '02/05/2026',
            'fecha_vigencia': '31/03/2027',
            'codigo_qr': f"UNIEBEC|EST|{cedula}|{mat_num}|{periodo_nombre}|VALIDO",
            'codigo_barras': f"786{cedula.replace('-', '').replace(' ', '')}",
            'rol': 'ALUMNO REGULAR',
            'estado_matricula': 'ACTIVA'
        }

        respuesta.set_success(True)
        respuesta.set_message('Perfil del estudiante recuperado con éxito.')
        respuesta.set_data(data)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


class StudentCarnetView(APIView):
    """
    GET /api/v1.0.0/movil/student/carnet/ (o estudiante/carnet, action=generate)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import datetime
        view_perfil = StudentProfileView()
        res_perfil = view_perfil.get(request)
        datos_resp = getattr(res_perfil, 'data', {})
        if isinstance(datos_resp, dict) and not datos_resp.get('isSuccess'):
            return res_perfil
        elif not isinstance(datos_resp, dict) and hasattr(res_perfil, 'get') and not res_perfil.get('isSuccess'):
            return res_perfil

        perfil = (datos_resp.get('data') if isinstance(datos_resp, dict) else None) or {}
        carne = {
            'estudiante': perfil,
            'institucion': {
                'nombre': 'UNIDAD EDUCATIVA BOLIVARIANA',
                'siglas': 'UNIEBEC',
                'lema': 'Excelencia, Innovación y Valores'
            },
            'codigo_qr': perfil.get('codigo_qr'),
            'codigo_barras': perfil.get('codigo_barras'),
            'generado_el': datetime.date.today().strftime('%d/%m/%Y'),
            'valido_hasta': perfil.get('fecha_vigencia', '31/03/2027')
        }
        respuesta = RespuestaApi()
        respuesta.set_success(True)
        respuesta.set_message('Carné digital generado exitosamente.')
        respuesta.set_data(carne)
        respuesta.set_status(status.HTTP_200_OK)
        return respuesta.to_dict()


# =========================================================================
# TAREA 12: FOROS DE DISCUSIÓN Y CONSULTAS AL DOCENTE
# =========================================================================

class StudentSubjectForumsView(APIView):
    """
    GET /api/v1.0.0/student/subjects/<int:materia_asignada_id>/forums/

    Lista todos los foros de discusión activos correspondientes a la materia asignada.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_foros_materia
            datos = obtener_foros_materia(est['persona_id'], materia_asignada_id)
            respuesta.set_success(True)
            respuesta.set_message('Foros de la materia recuperados con éxito.')
            respuesta.set_data(datos)
            respuesta.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al consultar los foros de la materia.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentForumDetailView(APIView):
    """
    GET /api/v1.0.0/student/forums/<int:foro_id>/

    Retorna la información cabecera del foro e historial de aportes de la discusión.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, foro_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_detalle_foro
            datos = obtener_detalle_foro(est['persona_id'], request.user.id, foro_id)
            respuesta.set_success(True)
            respuesta.set_message('Detalle del foro recuperado con éxito.')
            respuesta.set_data(datos)
            respuesta.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al consultar el detalle del foro.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentForumPostCreateView(APIView):
    """
    POST /api/v1.0.0/student/forums/<int:foro_id>/posts/

    Publica un nuevo aporte en el foro. Valida que el foro esté abierto.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, foro_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        from app.serializers import ForoPostMensajeSerializer
        serializer = ForoPostMensajeSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Datos del aporte inválidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        mensaje = serializer.validated_data['mensaje']

        try:
            from app.student_ports import publicar_post_foro
            nuevo_post = publicar_post_foro(est['persona_id'], request.user.id, foro_id, mensaje)
            respuesta.set_success(True)
            respuesta.set_message('Aporte publicado en el foro con éxito.')
            respuesta.set_data(nuevo_post)
            respuesta.set_status(status.HTTP_201_CREATED)
        except ValueError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al publicar el aporte en el foro.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentForumPostActionView(APIView):
    """
    PUT /api/v1.0.0/student/forums/posts/<int:post_id>/
    DELETE /api/v1.0.0/student/forums/posts/<int:post_id>/

    Permite editar o eliminar un aporte propio en el foro.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, post_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        from app.serializers import ForoPostMensajeSerializer
        serializer = ForoPostMensajeSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Datos del aporte inválidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        mensaje = serializer.validated_data['mensaje']

        try:
            from app.student_ports import editar_post_foro
            post_editado = editar_post_foro(est['persona_id'], request.user.id, post_id, mensaje)
            respuesta.set_success(True)
            respuesta.set_message('Aporte actualizado con éxito.')
            respuesta.set_data(post_editado)
            respuesta.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al actualizar el aporte.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()

    def delete(self, request, post_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import eliminar_post_foro
            resultado = eliminar_post_foro(est['persona_id'], request.user.id, post_id)
            respuesta.set_success(True)
            respuesta.set_message('Aporte eliminado con éxito.')
            respuesta.set_data(resultado)
            respuesta.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al eliminar el aporte.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentSubjectInquiriesView(APIView):
    """
    GET /api/v1.0.0/student/subjects/<int:materia_asignada_id>/inquiries/
    POST /api/v1.0.0/student/subjects/<int:materia_asignada_id>/inquiries/

    Lista las consultas privadas del estudiante al docente de la materia y permite enviar nuevas inquietudes.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_consultas_docente
            datos = obtener_consultas_docente(est['persona_id'], materia_asignada_id)
            respuesta.set_success(True)
            respuesta.set_message('Consultas al docente recuperadas con éxito.')
            respuesta.set_data(datos)
            respuesta.set_status(status.HTTP_200_OK)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al consultar las inquietudes al docente.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()

    def post(self, request, materia_asignada_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        from app.serializers import ConsultaDocenteCrearSerializer
        serializer = ConsultaDocenteCrearSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message('Datos de la consulta inválidos.')
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        asunto = serializer.validated_data['asunto']
        pregunta = serializer.validated_data['pregunta']

        try:
            from app.student_ports import crear_consulta_docente
            nueva_consulta = crear_consulta_docente(
                est['persona_id'],
                request.user.id,
                materia_asignada_id,
                asunto,
                pregunta
            )
            respuesta.set_success(True)
            respuesta.set_message('Consulta enviada al docente con éxito.')
            respuesta.set_data(nueva_consulta)
            respuesta.set_status(status.HTTP_201_CREATED)
        except PermissionError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_403_FORBIDDEN)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message('Error al enviar la consulta al docente.')
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


# ==============================================================================
# TAREA 16: BALCÓN DE SERVICIOS Y DOCUMENTOS ESTUDIANTILES
# ==============================================================================

class StudentServiceTypesView(APIView):
    """
    GET /api/v1.0.0/student/services/types/

    Retorna el catálogo disponible de certificados, tipos de trámites y materias
    para crear nuevas solicitudes en el Balcón de Servicios.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_catalogo_servicios_estudiante
            data = obtener_catalogo_servicios_estudiante(est['persona_id'])
            respuesta.set_success(True)
            respuesta.set_message("Catálogo de servicios y trámites obtenido exitosamente.")
            respuesta.set_data(data)
            respuesta.set_status(status.HTTP_200_OK)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message("Error al obtener catálogo de servicios.")
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentServiceRequestsView(APIView):
    """
    GET /api/v1.0.0/student/services/requests/
    POST /api/v1.0.0/student/services/requests/

    Lista las solicitudes del estudiante con filtros y permite registrar una nueva solicitud
    en ctr_solicitudservicio con adjuntos opcionales.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        estado = request.query_params.get('estado')
        tipo = request.query_params.get('tipo')

        try:
            from app.student_ports import obtener_solicitudes_servicio_estudiante
            data = obtener_solicitudes_servicio_estudiante(est['persona_id'], estado=estado, tipo=tipo)
            respuesta.set_success(True)
            respuesta.set_message("Solicitudes de servicio obtenidas exitosamente.")
            respuesta.set_data(data)
            respuesta.set_status(status.HTTP_200_OK)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message("Error al consultar las solicitudes de servicio.")
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()

    def post(self, request):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        from app.serializers import SolicitudServicioCrearSerializer
        serializer = SolicitudServicioCrearSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message("Datos de solicitud inválidos.")
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        archivos = (
            request.FILES.getlist('adjuntos')
            or request.FILES.getlist('archivo')
            or request.FILES.getlist('files')
            or request.FILES.getlist('file')
        )
        if not archivos and request.FILES.get('archivo'):
            archivos = [request.FILES.get('archivo')]
        elif not archivos and request.FILES.get('file'):
            archivos = [request.FILES.get('file')]

        try:
            from app.student_ports import crear_solicitud_servicio_estudiante
            nueva_sol = crear_solicitud_servicio_estudiante(
                est['persona_id'],
                request.user.id,
                serializer.validated_data,
                archivos_adjuntos=archivos
            )
            respuesta.set_success(True)
            respuesta.set_message("Solicitud de servicio registrada exitosamente. Secretaría atenderá tu trámite.")
            respuesta.set_data(nueva_sol)
            respuesta.set_status(status.HTTP_201_CREATED)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message("Error al registrar la solicitud de servicio.")
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentServiceRequestDetailView(APIView):
    """
    GET /api/v1.0.0/student/services/requests/<int:solicitud_id>/

    Detalle exhaustivo de una solicitud, estado de atención, adjuntos y descarga de certificado final.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, solicitud_id):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_detalle_solicitud_servicio
            data = obtener_detalle_solicitud_servicio(est['persona_id'], int(solicitud_id))
            respuesta.set_success(True)
            respuesta.set_message("Detalle de la solicitud recuperado con éxito.")
            respuesta.set_data(data)
            respuesta.set_status(status.HTTP_200_OK)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message("Error al obtener detalle de la solicitud.")
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentDocumentsView(APIView):
    """
    GET /api/v1.0.0/student/documents/

    Retorna los requerimientos documentales asignados por Secretaría,
    el historial de documentos cargados y el catálogo de tipos de documento.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        try:
            from app.student_ports import obtener_documentos_y_requerimientos_estudiante
            data = obtener_documentos_y_requerimientos_estudiante(est['persona_id'])
            respuesta.set_success(True)
            respuesta.set_message("Documentos y requerimientos recuperados exitosamente.")
            respuesta.set_data(data)
            respuesta.set_status(status.HTTP_200_OK)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message("Error al consultar documentos del estudiante.")
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()


class StudentDocumentUploadView(APIView):
    """
    POST /api/v1.0.0/student/documents/upload/

    Permite al estudiante cargar un archivo para atender un requerimiento de Secretaría.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        respuesta = RespuestaApi()
        est = _obtener_estudiante_actual(request, respuesta)
        if est is None:
            return respuesta.to_dict()

        from app.serializers import DocumentoEstudianteSubirSerializer
        serializer = DocumentoEstudianteSubirSerializer(data=request.data)
        if not serializer.is_valid():
            respuesta.set_success(False)
            respuesta.set_message("Datos de carga de documento inválidos.")
            respuesta.set_errors(serializer.errors)
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        archivo = request.FILES.get('archivo') or request.FILES.get('file') or request.FILES.get('documento')
        if not archivo:
            respuesta.set_success(False)
            respuesta.set_message("Debes adjuntar el archivo del documento (PDF o imagen).")
            respuesta.set_status(status.HTTP_400_BAD_REQUEST)
            return respuesta.to_dict()

        tipo_id = serializer.validated_data['tipo_id']
        observacion = serializer.validated_data.get('observacion', '')

        try:
            from app.student_ports import subir_documento_estudiante
            nuevo_doc = subir_documento_estudiante(
                est['persona_id'],
                request.user.id,
                tipo_id,
                archivo,
                observacion=observacion
            )
            respuesta.set_success(True)
            respuesta.set_message("Documento subido exitosamente. Secretaría revisará tu entrega.")
            respuesta.set_data(nuevo_doc)
            respuesta.set_status(status.HTTP_201_CREATED)
        except LookupError as e:
            respuesta.set_success(False)
            respuesta.set_message(str(e))
            respuesta.set_status(status.HTTP_404_NOT_FOUND)
        except Exception as e:
            respuesta.set_success(False)
            respuesta.set_message("Error al subir el documento institucional.")
            respuesta.set_errors({'error': [str(e)]})
            respuesta.set_status(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return respuesta.to_dict()

