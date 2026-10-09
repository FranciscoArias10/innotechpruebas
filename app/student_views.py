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

        est = _obtener_estudiante_actual(request, respuesta)
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

        est = _obtener_estudiante_actual(request, respuesta)
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


class StudentScheduleView(APIView):
    """
    GET /api/v1.0.0/movil/student/schedule/

    Retorna el horario semanal de clases del estudiante para el periodo.
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
