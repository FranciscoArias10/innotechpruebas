import re
# -*- coding: utf-8 -*-
"""
Puertos de datos del estudiante contra la base de datos real (SIGE UNIEBEC).

Consultas directas a PostgreSQL respetando el esquema real:
  - ctr_persona (nombres, apellido_1, apellido_2)
  - ctr_estudiante (persona_id)
  - ctr_matricula (estudiante_id, periodolectivo_id, nivel_id, paralelo_id)
  - ctr_periodolectivo -> ctr_periodo (periodo_id)
  - ctr_nivelmatriculdo (matricula_id)
  - ctr_materiaasignada (nivelmatriculado_id, materia_id, notafinal, asistenciafinal)
  - ctr_materia -> ctr_asignaturamallacurricular -> ctr_asignatura (nombre, color)
  - ctr_clase (materia_id, dia, inicio, fin, aula_id)
"""
from django.db import connection


def _query_one(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        if not c.description:
            return None
        cols = [d[0] for d in c.description]
        row = c.fetchone()
        return dict(zip(cols, row)) if row else None


def _query_all(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        if not c.description:
            return []
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, r)) for r in c.fetchall()]


def obtener_estudiante_de_usuario(user):
    """
    Obtiene la informacion del estudiante vinculado al usuario de Django.
    Retorna dict con datos o None si el usuario no es estudiante.
    """
    sql = """
        SELECT e.id as estudiante_id, p.id as persona_id,
               p.nombres, p.apellido_1, p.apellido_2,
               TRIM(p.nombres || ' ' || p.apellido_1 || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo,
               p.cedula, p.correo_institucional
        FROM ctr_persona p
        JOIN ctr_estudiante e ON e.persona_id = p.id
        WHERE p.usuario_id = %s AND e.status = TRUE
        LIMIT 1
    """
    return _query_one(sql, [user.id])


def obtener_resumen_estudiante(persona_id, periodo_id):
    """
    Metricas consolidadas del tablero del estudiante para un periodo especifico.
    Retorna el diccionario con la estructura esperada:
      total_subjects, attendance_percentage, pending_activities, enrollment, period
    """
    # 1. Buscar matricula del estudiante en el periodo dado
    sql_mat = """
        SELECT m.id as matricula_id,
               COALESCE(m.porcentaje_asistencia, 0.0) as mat_asistencia,
               COALESCE(n.nombre, 'Sin nivel') as level,
               COALESCE(n.alias, 'N/D') as level_alias,
               COALESCE(par.nombre, 'A') as parallel,
               per.id as period_id, per.nombre as period_name
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        LEFT JOIN ctr_nivel n ON n.id = m.nivel_id
        LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
        WHERE e.persona_id = %s AND per.id = %s
        ORDER BY m.id DESC
        LIMIT 1
    """
    mat = _query_one(sql_mat, [persona_id, periodo_id])
    if not mat:
        raise LookupError("El estudiante no registra matricula activa en el periodo especificado.")

    matricula_id = mat['matricula_id']

    # 2. Contar asignaturas y calcular promedio de asistencia
    sql_materias = """
        SELECT COUNT(ma.id) as total_subjects,
               COALESCE(AVG(ma.asistenciafinal), 0.0) as avg_asistencia
        FROM ctr_nivelmatriculdo nm
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        WHERE nm.matricula_id = %s AND nm.status = TRUE
    """
    stats_mat = _query_one(sql_materias, [matricula_id]) or {'total_subjects': 0, 'avg_asistencia': 0.0}

    # 3. Contar actividades pendientes
    sql_pendientes = """
        SELECT COUNT(DISTINCT act.id) as pending_activities
        FROM ctr_nivelmatriculdo nm
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_cronogramamateria cm ON cm.materia_id = mat.id AND cm.status = TRUE
        JOIN ctr_actividad act ON act.cronogramamateria_id = cm.id AND act.status = TRUE
        LEFT JOIN ctr_entregaactividad ea ON ea.actividad_id = act.id AND ea.materiaasignada_id = ma.id AND ea.status = TRUE
        WHERE nm.matricula_id = %s AND ea.id IS NULL
    """
    try:
        pend_row = _query_one(sql_pendientes, [matricula_id])
        pendientes = pend_row['pending_activities'] if pend_row else 0
    except Exception:
        pendientes = 0

    asistencia_pct = float(mat['mat_asistencia']) if mat['mat_asistencia'] > 0 else float(stats_mat['avg_asistencia'])

    return {
        'total_subjects': int(stats_mat['total_subjects']),
        'attendance_percentage': round(asistencia_pct, 1),
        'pending_activities': int(pendientes),
        'enrollment': {
            'id': mat['matricula_id'],
            'level': mat['level'],
            'level_alias': mat['level_alias'],
            'parallel': mat['parallel'],
        },
        'period': {
            'id': mat['period_id'],
            'name': mat['period_name'],
        }
    }


def obtener_materias_estudiante(persona_id, periodo_id):
    """
    Retorna la lista de asignaturas del estudiante para el periodo con profesor,
    color, notas y porcentaje de asistencia.
    """
    sql = """
        SELECT 
            ma.id as materia_asignada_id,
            mat.id as materia_id,
            asig.nombre as name,
            COALESCE(NULLIF(asig.color, ''), '#0073bc') as color,
            COALESCE(n.nombre, '') as level,
            COALESCE(par.nombre, 'A') as parallel,
            ROUND(CAST(COALESCE(ma.notafinal, 0) AS numeric), 2) as final_grade,
            ROUND(CAST(COALESCE(ma.asistenciafinal, 0) AS numeric), 1) as attendance_percentage,
            TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as teacher
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = m.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_nivel n ON n.id = m.nivel_id
        LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE e.persona_id = %s AND per.id = %s
        ORDER BY asig.nombre ASC
    """
    rows = _query_all(sql, [persona_id, periodo_id])
    if not rows:
        raise LookupError("No se encontraron materias asignadas para este estudiante en el periodo.")

    for r in rows:
        r['final_grade'] = float(r['final_grade'])
        r['attendance_percentage'] = float(r['attendance_percentage'])
        r['pending_activities'] = 0

    return {'subjects': rows}


def obtener_calificaciones_estudiante(persona_id, periodo_id):
    """
    Lista de calificaciones generales por materia para el periodo.
    """
    materias_res = obtener_materias_estudiante(persona_id, periodo_id)
    lista = []
    for m in materias_res['subjects']:
        nota = m['final_grade']
        estado = 'aprobado' if nota >= 7.0 else ('reprobado' if nota > 0 else 'en_curso')
        lista.append({
            'materia_asignada_id': m['materia_asignada_id'],
            'materia_nombre': m['name'],
            'color': m['color'],
            'profesor': m['teacher'],
            'nota_final': nota,
            'estado': estado,
            'asistencia_porcentaje': m['attendance_percentage'],
        })
    return {'periodo_id': periodo_id, 'calificaciones': lista}


def obtener_detalle_notas_materia(persona_id, periodo_id, materia_asignada_id):
    """
    Detalle jerarquico de calificaciones para una materia especifica.
    Consulta ctr_notaitenevaluativomateriaasignada y el modelo evaluativo.
    """
    # Verificar pertenencia de la materia asignada al estudiante y al periodo
    sql_check = """
        SELECT ma.id, asig.nombre as subject_name,
               COALESCE(n.nombre, '') as level, COALESCE(par.nombre, 'A') as parallel,
               mat.fechainicio as start_date, mat.fechafin as end_date,
               mat.escuantitativa as is_quantitative,
               mat.modeloevaluativo_id
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = m.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_nivel n ON n.id = m.nivel_id
        LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
        WHERE e.persona_id = %s AND per.id = %s AND ma.id = %s
        LIMIT 1
    """
    materia_info = _query_one(sql_check, [persona_id, periodo_id, materia_asignada_id])
    if not materia_info:
        raise LookupError("La materia asignada no existe o no pertenece al estudiante en este periodo.")

    # Consultar notas de items evaluativos
    sql_items = """
        SELECT n.id, n.nota, n.promedionota,
               ie.nombre as item_name, ie.alias,
               ime.notamaxima as max_score, ime.porcentaje as total_percentage
        FROM ctr_notaitenevaluativomateriaasignada n
        JOIN ctr_itemmodeloevaluativo ime ON ime.id = n.itemevaluativo_id
        JOIN ctr_itemevaluacion ie ON ie.id = ime.itemevaluacion_id
        WHERE n.materiaasignada_id = %s AND n.status = TRUE
        ORDER BY ime.orden ASC, n.id ASC
    """
    items_rows = _query_all(sql_items, [materia_asignada_id])

    items_list = []
    for it in items_rows:
        nota = float(it['nota']) if it['nota'] is not None else None
        items_list.append({
            'id': it['id'],
            'name': it['item_name'],
            'alias': it['alias'] or it['item_name'][:3].upper(),
            'max_score': float(it['max_score'] or 10.0),
            'total_percentage': float(it['total_percentage'] or 100.0),
            'grade': nota,
            'grade_letter': None,
            'grading_books': []
        })

    return {
        'subject': {
            'id': materia_info['id'],
            'name': materia_info['subject_name'],
            'level': materia_info['level'],
            'parallel': materia_info['parallel'],
            'start_date': str(materia_info['start_date'] or ''),
            'end_date': str(materia_info['end_date'] or ''),
            'total_weeks': 40,
            'pending_activities': 0
        },
        'evaluation_model': {
            'id': materia_info['modeloevaluativo_id'] or 1,
            'name': 'Modelo Evaluativo Institucional',
            'is_quantitative': bool(materia_info['is_quantitative']),
            'items': items_list
        }
    }


def obtener_asistencia_estudiante(persona_id, periodo_id):
    """
    Reporte consolidado de asistencia por asignatura para el estudiante en el periodo.
    """
    sql = """
        SELECT 
            ma.id as cronograma_id,
            asig.nombre as name,
            COALESCE(ma.asist_presente, 0) as attended_hours,
            COALESCE(ma.falta_justificada_dia, 0) as justified_hours,
            COALESCE(ma.asist_pendiente, 0) as pending_hours,
            COALESCE(ma.falta_injustificada_dia, 0) as absent_hours,
            COALESCE(ma.asist_total, 0) as total_hours,
            ROUND(CAST(COALESCE(ma.asistenciafinal, 0) AS numeric), 1) as percentage
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = m.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        WHERE e.persona_id = %s AND per.id = %s
        ORDER BY asig.nombre ASC
    """
    rows = _query_all(sql, [persona_id, periodo_id])
    if not rows:
        raise LookupError("No se encontraron registros de asistencia para este periodo.")

    subjects = []
    for r in rows:
        pct = float(r['percentage'])
        total_h = r['total_hours'] if r['total_hours'] > 0 else (r['attended_hours'] + r['absent_hours'])
        if pct >= 90:
            st = 'excelente'
        elif pct >= 75:
            st = 'normal'
        else:
            st = 'riesgo'

        subjects.append({
            'cronograma_id': r['cronograma_id'],
            'name': r['name'],
            'by_hours': {
                'attended': r['attended_hours'],
                'justified': r['justified_hours'],
                'pending': r['pending_hours'],
                'absent': r['absent_hours'],
                'total': total_h,
                'percentage': pct,
            },
            'by_days': {
                'attended': r['attended_hours'],
                'justified': r['justified_hours'],
                'pending': r['pending_hours'],
                'absent': r['absent_hours'],
                'total': total_h,
                'percentage': pct,
            },
            'status': st
        })

    return {'subjects': subjects}


def obtener_horario_estudiante(persona_id, periodo_id):
    """
    Horario semanal de clases del estudiante para el periodo lectivo.
    """
    sql = """
        SELECT 
            cl.dia,
            COALESCE(TO_CHAR(t.comienza, 'HH24:MI'), TO_CHAR(cl.inicio, 'HH24:MI'), '08:00') as inicio,
            COALESCE(TO_CHAR(t.termina, 'HH24:MI'), TO_CHAR(cl.fin, 'HH24:MI'), '08:45') as fin,
            asig.nombre as materia,
            COALESCE(NULLIF(asig.color, ''), '#0073bc') as color,
            COALESCE(au.nombre, 'Aula Virtual') as aula,
            COALESCE(par.nombre, 'A') as paralelo,
            TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as profesor,
            COALESCE(cl.modalidad, 1) as modalidad,
            COALESCE(cl.zoom_join_url, '') as zoom_join_url,
            COALESCE(cl.zoom_meeting_id, '') as zoom_meeting_id,
            COALESCE(cl.zoom_password, '') as zoom_password,
            t.id as turno_id,
            COALESCE(t.nombre, 'MATUTINO') as turno_nombre,
            COALESCE(CAST(t.turno AS text), 'MAT') as turno_corto,
            COALESCE(t.aplicaasistencia, TRUE) as turno_asistencia
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = m.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_clase cl ON cl.materia_id = ma.materia_id AND cl.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_aula au ON au.id = cl.aula_id
        LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
        LEFT JOIN ctr_profesor prof ON prof.id = cl.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        LEFT JOIN ctr_turno t ON t.id = cl.turno_id
        WHERE e.persona_id = %s AND per.id = %s
        ORDER BY cl.dia ASC, t.comienza ASC
    """
    rows = _query_all(sql, [persona_id, periodo_id])

    # En BD ctr_clase.dia va de 0 a 4 (0=LUNES, 1=MARTES, 2=MIERCOLES, 3=JUEVES, 4=VIERNES)
    # Estandarizamos indice 1: LUNES ... 5: VIERNES
    dias_nombres_map = {
        0: (1, 'LUNES'),
        1: (2, 'MARTES'),
        2: (3, 'MIERCOLES'),
        3: (4, 'JUEVES'),
        4: (5, 'VIERNES'),
        5: (6, 'SABADO'),
        6: (7, 'DOMINGO')
    }

    # Grilla base para dias_visibles
    dias_visibles = [
        {'indice': 1, 'nombre': 'LUNES', 'clases': []},
        {'indice': 2, 'nombre': 'MARTES', 'clases': []},
        {'indice': 3, 'nombre': 'MIERCOLES', 'clases': []},
        {'indice': 4, 'nombre': 'JUEVES', 'clases': []},
        {'indice': 5, 'nombre': 'VIERNES', 'clases': []},
    ]
    dias_visibles_map = {d['indice']: d for d in dias_visibles}

    turnos_dict = {}
    for r in rows:
        t_id = r['turno_id'] or 1
        if t_id not in turnos_dict:
            turnos_dict[t_id] = {
                'id': t_id,
                'nombre': r['turno_nombre'],
                'nombre_corto': r['turno_corto'],
                'aplica_asistencia': r['turno_asistencia'],
                'dias_map': {}
            }

        dia_raw = r['dia']
        if dia_raw in dias_nombres_map:
            indice_dia, nombre_dia = dias_nombres_map[dia_raw]
        elif dia_raw in (1, 2, 3, 4, 5, 6, 7):
            indice_dia = dia_raw
            nombre_dia = dias_visibles_map.get(dia_raw, {}).get('nombre', 'LUNES')
        else:
            indice_dia = 1
            nombre_dia = 'LUNES'

        clase_item = {
            'nombre': r['materia'],
            'paralelo': r['paralelo'],
            'aula': r['aula'],
            'profesor': r['profesor'] or 'Docente Asignado',
            'inicio': str(r['inicio']),
            'fin': str(r['fin']),
            'color': r['color'],
            'modalidad': r['modalidad'],
            'zoom_join_url': r['zoom_join_url'],
            'zoom_meeting_id': r['zoom_meeting_id'],
            'zoom_password': r['zoom_password']
        }

        # Agregar al mapa de turnos
        if indice_dia not in turnos_dict[t_id]['dias_map']:
            turnos_dict[t_id]['dias_map'][indice_dia] = {
                'indice': indice_dia,
                'nombre': nombre_dia,
                'clases': []
            }
        turnos_dict[t_id]['dias_map'][indice_dia]['clases'].append(clase_item)

        # Agregar a dias_visibles si corresponde (1 a 5)
        if indice_dia in dias_visibles_map:
            dias_visibles_map[indice_dia]['clases'].append(clase_item)

    turnos_salida = []
    for t_data in turnos_dict.values():
        dias_lista = sorted(t_data['dias_map'].values(), key=lambda d: d['indice'])
        turnos_salida.append({
            'id': t_data['id'],
            'nombre': t_data['nombre'],
            'nombre_corto': t_data['nombre_corto'],
            'aplica_asistencia': t_data['aplica_asistencia'],
            'dias': dias_lista
        })

    if not turnos_salida:
        turnos_salida = [{
            'id': 1,
            'nombre': 'MATUTINO',
            'nombre_corto': 'MAT',
            'aplica_asistencia': True,
            'dias': []
        }]

    return {
        'turnos': turnos_salida,
        'dias_visibles': dias_visibles
    }

def obtener_planificacion_materia(persona_id, periodo_id, materia_asignada_id, semana=None):
    """
    Retorna la planificacion semanal completa o filtrada por semana para la materia asignada.
    Incluye datos de la asignatura (color, profesor, nombre), semanas con unidades,
    temas, subtemas, archivos, enlaces y actividades, indicando si los recursos fueron abiertos.
    """
    sql_materia = """
        SELECT ma.id as materia_asignada_id, mat.id as materia_id, asig.nombre as name,
               COALESCE(NULLIF(asig.color, ''), '#0073bc') as color,
               COALESCE(n.nombre, '') as level,
               COALESCE(par.nombre, 'A') as parallel,
               ROUND(CAST(COALESCE(ma.notafinal, 0) AS numeric), 2) as final_grade,
               ROUND(CAST(COALESCE(ma.asistenciafinal, 0) AS numeric), 1) as attendance_percentage,
               TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as teacher
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = m.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_nivel n ON n.id = m.nivel_id
        LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE e.persona_id = %s AND (ma.id = %s OR mat.id = %s)
        LIMIT 1
    """
    materia = _query_one(sql_materia, [persona_id, materia_asignada_id, materia_asignada_id])
    if not materia:
        raise LookupError("Materia no encontrada para este estudiante.")

    materia['final_grade'] = float(materia['final_grade'])
    materia['attendance_percentage'] = float(materia['attendance_percentage'])
    real_ma_id = materia['materia_asignada_id']
    mat_id = materia['materia_id']

    # Recursos abiertos por este estudiante
    aperturas = _query_all("""
        SELECT archivo_id, link_id 
        FROM ctr_aperturarecursosemanal 
        WHERE materiaasignada_id = %s AND persona_id = %s AND status = TRUE
    """, [real_ma_id, persona_id])
    archivos_abiertos = {a['archivo_id'] for a in aperturas if a['archivo_id'] is not None}
    links_abiertos = {a['link_id'] for a in aperturas if a['link_id'] is not None}

    # Plannings
    plans = _query_all("""
        SELECT psc.id, psc.inicio, psc.fin, psc.destreza, psc.estado
        FROM ctr_planificacionsemanalcontenido psc
        WHERE psc.materia_id = %s AND psc.status = TRUE
        ORDER BY psc.inicio ASC
    """, [mat_id])

    semanas_lista = []
    for idx, p in enumerate(plans):
        pid = p['id']
        num_semana = idx + 1

        unidades = _query_all("""
            SELECT id, nombre, objetivo 
            FROM ctr_unidadsemanalclase 
            WHERE planificacionsemanal_id = %s AND status = TRUE
        """, [pid])

        temas = _query_all("""
            SELECT t.id, t.nombre, t.contenido, t.unidad_id 
            FROM ctr_temasemanalclase t 
            JOIN ctr_unidadsemanalclase u ON u.id = t.unidad_id 
            WHERE u.planificacionsemanal_id = %s AND t.status = TRUE
        """, [pid])

        subtemas = _query_all("""
            SELECT st.id, st.nombre, st.contenido, st.tema_id 
            FROM ctr_subtemasemanalclase st 
            JOIN ctr_temasemanalclase t ON t.id = st.tema_id 
            JOIN ctr_unidadsemanalclase u ON u.id = t.unidad_id 
            WHERE u.planificacionsemanal_id = %s AND st.status = TRUE
        """, [pid])

        archivos = _query_all("""
            SELECT a.id, a.nombre, a.archivo 
            FROM ctr_archivosemanalclase a 
            WHERE a.planificacionsemanal_id = %s AND a.status = TRUE AND (a.ocultar = FALSE OR a.ocultar IS NULL)
        """, [pid])
        for arch in archivos:
            arch['abierto'] = arch['id'] in archivos_abiertos

        links = _query_all("""
            SELECT l.id, l.nombre, l.link 
            FROM ctr_linksemanalclase l 
            WHERE l.planificacionsemanal_id = %s AND l.status = TRUE AND (l.ocultar = FALSE OR l.ocultar IS NULL)
        """, [pid])
        for lk in links:
            lk['abierto'] = lk['id'] in links_abiertos

        actividades = _query_all("""
            SELECT act.id, act.nombre, act.descripcion, act.fechainicio, act.fechafin, act.archivo, act.cerrada 
            FROM ctr_actividad act 
            WHERE act.planificacionsemanal_id = %s AND act.status = TRUE AND (act.oculto = FALSE OR act.oculto IS NULL)
        """, [pid])
        for act in actividades:
            if act['fechainicio']:
                act['fechainicio'] = str(act['fechainicio'])
            if act['fechafin']:
                act['fechafin'] = str(act['fechafin'])

        semanas_lista.append({
            'semana_numero': num_semana,
            'plan_id': pid,
            'inicio': str(p['inicio']) if p['inicio'] else None,
            'fin': str(p['fin']) if p['fin'] else None,
            'destreza': p['destreza'] or '',
            'unidades': unidades,
            'temas': temas,
            'subtemas': subtemas,
            'archivos': archivos,
            'links': links,
            'actividades': actividades,
        })

    # Si se especifico filtro por semana (ej. week=1)
    semana_seleccionada = None
    if semana is not None:
        try:
            s_num = int(semana)
            for s in semanas_lista:
                if s['semana_numero'] == s_num or s['plan_id'] == s_num:
                    semana_seleccionada = s
                    break
        except (ValueError, TypeError):
            pass

    return {
        'subject': materia,
        'weeks': semanas_lista,
        'current_week': semana_seleccionada or (semanas_lista[0] if semanas_lista else None),
        'total_weeks': len(semanas_lista)
    }


def obtener_companeros_materia(persona_id, periodo_id, materia_asignada_id):
    """
    Lista de companeros de clase del estudiante matriculados en la misma materia.
    """
    sql_mat = """
        SELECT ma.materia_id
        FROM ctr_materiaasignada ma
        WHERE ma.id = %s OR ma.materia_id = %s
        LIMIT 1
    """
    mat = _query_one(sql_mat, [materia_asignada_id, materia_asignada_id])
    if not mat:
        raise LookupError("Materia no encontrada.")

    materia_id = mat['materia_id']

    sql_classmates = """
        SELECT p.id as persona_id, 
               TRIM(COALESCE(p.apellido_1, '') || ' ' || COALESCE(p.apellido_2, '') || ' ' || COALESCE(p.nombres, '')) as nombre_completo,
               COALESCE(p.correo, '') as correo,
               COALESCE(p.movil, '') as movil,
               COALESCE(p.foto, '') as foto
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_estudiante e ON e.id = m.estudiante_id
        JOIN ctr_persona p ON p.id = e.persona_id
        WHERE ma.materia_id = %s AND ma.status = TRUE
        ORDER BY nombre_completo ASC
    """
    classmates = _query_all(sql_classmates, [materia_id])
    return {
        'materia_id': materia_id,
        'classmates': classmates,
        'total': len(classmates)
    }


def registrar_apertura_recurso(persona_id, usuario_id, materia_asignada_id, archivo_id=None, link_id=None):
    """
    Registra en ctr_aperturarecursosemanal la apertura de un recurso (archivo o link)
    por parte de un estudiante en su materia asignada.
    """
    if not archivo_id and not link_id:
        raise ValueError("Debe proporcionar archivo_id o link_id.")

    # Resolver materiaasignada_id real si se envio materia_id
    sql_ma = """
        SELECT ma.id 
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_estudiante e ON e.id = m.estudiante_id
        WHERE e.persona_id = %s AND (ma.id = %s OR ma.materia_id = %s) AND ma.status = TRUE
        LIMIT 1
    """
    ma_row = _query_one(sql_ma, [persona_id, materia_asignada_id, materia_asignada_id])
    real_ma_id = ma_row['id'] if ma_row else materia_asignada_id

    sql_insert = """
        INSERT INTO ctr_aperturarecursosemanal 
            (fecha_creacion, fecha_modificacion, status, archivo_id, link_id, materiaasignada_id, persona_id, usuario_creacion_id)
        VALUES 
            (NOW(), NOW(), TRUE, %s, %s, %s, %s, %s)
        RETURNING id
    """
    row = _query_one(sql_insert, [archivo_id, link_id, real_ma_id, persona_id, usuario_id])
    return {
        'id': row['id'] if row else None,
        'registrado': True,
        'archivo_id': archivo_id,
        'link_id': link_id,
        'materia_asignada_id': real_ma_id
    }


def obtener_actividad_detalle(persona_id, periodo_id, actividad_id):
    """
    Obtiene el detalle completo de una actividad y el estado de la entrega del estudiante.
    """
    from django.utils import timezone
    from django.conf import settings

    # 1. Consultar datos de la actividad y la materia a la que pertenece
    sql_act = """
        SELECT a.id, a.nombre, a.descripcion, a.fechainicio, a.fechafin,
               a.cerrada, a.ponderacion, a.tipoentrega, a.tipocalificacion,
               COALESCE(a.archivo, '') as archivo, a.planificacionsemanal_id,
               asig.id as asignatura_id, asig.nombre as materia_nombre,
               COALESCE(asig.color, '#0b3b60') as materia_color,
               pl.materia_id
        FROM ctr_actividad a
        JOIN ctr_planificacionsemanalcontenido pl ON pl.id = a.planificacionsemanal_id
        JOIN ctr_materia m ON m.id = pl.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = m.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        WHERE a.id = %s AND a.status = TRUE
        LIMIT 1
    """
    act = _query_one(sql_act, [actividad_id])
    if not act:
        raise LookupError("Actividad no encontrada.")

    # 2. Obtener la materia asignada del estudiante para esta materia
    sql_ma = """
        SELECT ma.id as materia_asignada_id
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_estudiante e ON e.id = m.estudiante_id
        WHERE e.persona_id = %s AND per.id = %s AND ma.materia_id = %s AND ma.status = TRUE
        LIMIT 1
    """
    ma_row = _query_one(sql_ma, [persona_id, periodo_id, act['materia_id']])
    ma_id = ma_row['materia_asignada_id'] if ma_row else None

    now = timezone.now()
    fechafin_dt = act['fechafin']
    is_expired = bool(act['cerrada']) or (fechafin_dt is not None and fechafin_dt < now)

    archivo_url = None
    if act['archivo']:
        archivo_url = f"{settings.MEDIA_URL}{act['archivo']}" if not act['archivo'].startswith('http') else act['archivo']

    # 3. Buscar si el estudiante ya tiene una entrega registrada
    submission = None
    if ma_id:
        sql_entrega = """
            SELECT e.id, e.fecha, e.observacion, e.entrega, e.es_tardia, e.fecha_creacion
            FROM ctr_entregaactividad e
            WHERE e.actividad_id = %s AND e.materiaasignada_id = %s AND e.status = TRUE
            ORDER BY e.id DESC
            LIMIT 1
        """
        entrega_row = _query_one(sql_entrega, [actividad_id, ma_id])
        if entrega_row:
            # Buscar archivos adjuntos de la entrega
            sql_archivos = """
                SELECT a.id, a.archivo, a.observacion, a.fecha
                FROM ctr_entregaactividadarchivo a
                WHERE a.entregaactividad_id = %s AND a.status = TRUE
                ORDER BY a.id ASC
            """
            archivos_entrega = _query_all(sql_archivos, [entrega_row['id']])
            for arch in archivos_entrega:
                if arch['archivo'] and not arch['archivo'].startswith('http'):
                    arch['url'] = f"{settings.MEDIA_URL}{arch['archivo']}"
                else:
                    arch['url'] = arch['archivo']
                if arch['fecha']:
                    arch['fecha'] = str(arch['fecha'])

            # Buscar textos de la entrega
            sql_textos = """
                SELECT t.id, t.texto, t.observacion, t.fecha
                FROM ctr_entregaactividadtexto t
                WHERE t.entregaactividad_id = %s AND t.status = TRUE
                ORDER BY t.id ASC
            """
            textos_entrega = _query_all(sql_textos, [entrega_row['id']])
            for txt in textos_entrega:
                if txt['fecha']:
                    txt['fecha'] = str(txt['fecha'])

            # Buscar nota / calificación y retroalimentación del docente
            sql_nota = """
                SELECT n.id, n.nota, n.observacion, n.fecha
                FROM ctr_notaactividad n
                WHERE n.actividad_id = %s AND n.materiaasignada_id = %s AND n.status = TRUE
                ORDER BY n.id DESC
                LIMIT 1
            """
            nota_row = _query_one(sql_nota, [actividad_id, ma_id])
            nota_info = None
            if nota_row:
                nota_info = {
                    'nota': float(nota_row['nota']) if nota_row['nota'] is not None else None,
                    'observacion': nota_row['observacion'] or '',
                    'fecha': str(nota_row['fecha']) if nota_row['fecha'] else None,
                }

            submission = {
                'id': entrega_row['id'],
                'fecha': str(entrega_row['fecha']) if entrega_row['fecha'] else str(entrega_row['fecha_creacion']),
                'observacion': entrega_row['observacion'] or '',
                'texto': entrega_row['entrega'] or '',
                'es_tardia': bool(entrega_row['es_tardia']),
                'archivos': archivos_entrega,
                'textos': textos_entrega,
                'grade': nota_info,
            }

    return {
        'activity': {
            'id': act['id'],
            'nombre': act['nombre'],
            'descripcion': act['descripcion'] or '',
            'fechainicio': str(act['fechainicio']) if act['fechainicio'] else None,
            'fechafin': str(act['fechafin']) if act['fechafin'] else None,
            'cerrada': bool(act['cerrada']),
            'ponderacion': float(act['ponderacion']) if act['ponderacion'] is not None else 10.0,
            'tipoentrega': act['tipoentrega'] or 1,
            'tipocalificacion': act['tipocalificacion'] or 1,
            'archivo': act['archivo'],
            'archivo_url': archivo_url,
            'materia': {
                'id': act['materia_id'],
                'materia_asignada_id': ma_id,
                'name': act['materia_nombre'],
                'color': act['materia_color'],
            }
        },
        'is_expired': is_expired,
        'has_submission': submission is not None,
        'submission': submission,
    }


def entregar_actividad(persona_id, usuario_id, periodo_id, actividad_id, texto=None, archivos=None):
    import re
    import urllib.parse
    from django.db import transaction
    """
    Registra o actualiza la entrega de una actividad por parte del estudiante.
    Valida plazos, tipos y almacena archivos físicos y/o texto.
    """
    from django.utils import timezone
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os

    # 1. Verificar estado de la actividad
    sql_act = """
        SELECT a.id, a.fechafin, a.cerrada, pl.materia_id
        FROM ctr_actividad a
        JOIN ctr_planificacionsemanalcontenido pl ON pl.id = a.planificacionsemanal_id
        WHERE a.id = %s AND a.status = TRUE
        LIMIT 1
    """
    act = _query_one(sql_act, [actividad_id])
    if not act:
        raise LookupError("Actividad no encontrada.")

    now = timezone.now()
    if act['cerrada']:
        raise ValueError("La actividad está cerrada por el docente y no admite entregas.")

    if act['fechafin'] and act['fechafin'] < now:
        raise ValueError("El plazo para entregar esta actividad ha vencido.")

    # 2. Localizar materiaasignada_id del estudiante
    sql_ma = """
        SELECT ma.id as materia_asignada_id
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_estudiante e ON e.id = m.estudiante_id
        WHERE e.persona_id = %s AND per.id = %s AND ma.materia_id = %s AND ma.status = TRUE
        LIMIT 1
    """
    ma_row = _query_one(sql_ma, [persona_id, periodo_id, act['materia_id']])
    if not ma_row:
        raise LookupError("El estudiante no está matriculado en esta materia en el periodo activo.")
    ma_id = ma_row['materia_asignada_id']

    # 3. Verificar si ya existe una entrega (activa o inactiva por reintento)
    sql_existente = """
        SELECT id, status FROM ctr_entregaactividad
        WHERE actividad_id = %s AND materiaasignada_id = %s
        ORDER BY id DESC LIMIT 1
    """
    existente = _query_one(sql_existente, [actividad_id, ma_id])

    texto_val = texto.strip() if texto else ''
    es_tardia = False

    if existente:
        entrega_id = existente['id']
        sql_upd = """
            UPDATE ctr_entregaactividad
            SET status = TRUE, fecha_modificacion = NOW(), fecha = NOW(), entrega = %s,
                usuario_modificacion_id = %s
            WHERE id = %s
        """
        with connection.cursor() as cur:
            cur.execute(sql_upd, [texto_val, usuario_id, entrega_id])
    else:
        sql_ins = """
            INSERT INTO ctr_entregaactividad
                (fecha_creacion, fecha_modificacion, status, nombre, observacion,
                 entrega, fecha, actividad_id, materiaasignada_id,
                 usuario_creacion_id, es_tardia)
            VALUES
                (NOW(), NOW(), TRUE, 'Entrega móvil', '',
                 %s, NOW(), %s, %s, %s, %s)
            RETURNING id
        """
        row = _query_one(sql_ins, [texto_val, actividad_id, ma_id, usuario_id, es_tardia])
        entrega_id = row['id']

    # 4. Procesar texto en ctr_entregaactividadtexto
    if texto_val:
        sql_txt_exist = "SELECT id FROM ctr_entregaactividadtexto WHERE entregaactividad_id = %s AND status = TRUE LIMIT 1"
        txt_row = _query_one(sql_txt_exist, [entrega_id])
        if txt_row:
            with connection.cursor() as cur:
                cur.execute("UPDATE ctr_entregaactividadtexto SET texto = %s, fecha_modificacion = NOW() WHERE id = %s", [texto_val, txt_row['id']])
        else:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO ctr_entregaactividadtexto
                        (fecha_creacion, fecha_modificacion, status, texto, observacion, fecha, entregaactividad_id, usuario_creacion_id)
                    VALUES
                        (NOW(), NOW(), TRUE, %s, '', NOW(), %s, %s)
                """, [texto_val, entrega_id, usuario_id])

    # 5. Guardar archivos subidos
    archivos_guardados = []
    if archivos:
        carpeta_destino = 'aulavirtual/entregas'
        for archivo_obj in archivos:
            import re
            import urllib.parse
            nombre_raw = urllib.parse.unquote(getattr(archivo_obj, 'name', 'entrega_adjunto'))
            nombre_limpio = re.sub(r'[^a-zA-Z0-9._-]', '_', nombre_raw)
            ruta_relativa = default_storage.save(f"{carpeta_destino}/{entrega_id}_{now.strftime('%Y%m%d%H%M%S')}_{nombre_limpio}", archivo_obj)
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO ctr_entregaactividadarchivo
                        (fecha_creacion, fecha_modificacion, status, observacion, archivo, fecha, entregaactividad_id, usuario_creacion_id)
                    VALUES
                        (NOW(), NOW(), TRUE, %s, %s, NOW(), %s, %s)
                    RETURNING id
                """, [nombre_limpio, ruta_relativa, entrega_id, usuario_id])
                arch_id = cur.fetchone()[0]
                archivos_guardados.append({'id': arch_id, 'archivo': ruta_relativa, 'nombre': nombre_limpio})

    return {
        'entrega_id': entrega_id,
        'actividad_id': actividad_id,
        'archivos_guardados': archivos_guardados,
        'texto': texto_val,
        'fecha': str(now)
    }


def eliminar_entrega_actividad(persona_id, periodo_id, actividad_id):
    """
    Elimina la entrega de una actividad (status = FALSE) mientras el plazo siga abierto.
    """
    from django.utils import timezone

    sql_act = """
        SELECT a.id, a.fechafin, a.cerrada, pl.materia_id
        FROM ctr_actividad a
        JOIN ctr_planificacionsemanalcontenido pl ON pl.id = a.planificacionsemanal_id
        WHERE a.id = %s AND a.status = TRUE
        LIMIT 1
    """
    act = _query_one(sql_act, [actividad_id])
    if not act:
        raise LookupError("Actividad no encontrada.")

    now = timezone.now()
    if act['cerrada']:
        raise ValueError("La actividad está cerrada. No se puede eliminar la entrega.")
    if act['fechafin'] and act['fechafin'] < now:
        raise ValueError("El plazo ha vencido. No se puede eliminar la entrega.")

    sql_ma = """
        SELECT ma.id as materia_asignada_id
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_estudiante e ON e.id = m.estudiante_id
        WHERE e.persona_id = %s AND per.id = %s AND ma.materia_id = %s AND ma.status = TRUE
        LIMIT 1
    """
    ma_row = _query_one(sql_ma, [persona_id, periodo_id, act['materia_id']])
    if not ma_row:
        raise LookupError("Estudiante no matriculado en esta materia.")

    ma_id = ma_row['materia_asignada_id']

    with connection.cursor() as cur:
        # Desactivar entrega y sus archivos/textos
        cur.execute("""
            UPDATE ctr_entregaactividad
            SET status = FALSE, fecha_modificacion = NOW()
            WHERE actividad_id = %s AND materiaasignada_id = %s AND status = TRUE
            RETURNING id
        """, [actividad_id, ma_id])
        rows = cur.fetchall()
        for r in rows:
            ent_id = r[0]
            cur.execute("UPDATE ctr_entregaactividadarchivo SET status = FALSE WHERE entregaactividad_id = %s", [ent_id])
            cur.execute("UPDATE ctr_entregaactividadtexto SET status = FALSE WHERE entregaactividad_id = %s", [ent_id])

    return {'eliminada': True, 'actividad_id': actividad_id}


def obtener_actividades_pendientes(persona_id, periodo_id):
    """
    Lista todas las actividades de las materias matriculadas en el periodo actual,
    ordenadas cronologicamente por fecha de cierre.
    """
    from django.utils import timezone
    now = timezone.now()

    sql = """
        SELECT a.id, a.nombre, a.descripcion, a.fechainicio, a.fechafin,
               a.cerrada, a.ponderacion, a.tipoentrega,
               m.id as materia_id, ma.id as materia_asignada_id,
               asig.nombre as materia_nombre, COALESCE(asig.color, '#0b3b60') as materia_color,
               e_act.id as entrega_id, e_act.fecha as fecha_entrega,
               n_act.nota
        FROM ctr_estudiante est
        JOIN ctr_matricula mat ON mat.estudiante_id = est.id AND mat.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = mat.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = mat.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia m ON m.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = m.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        JOIN ctr_planificacionsemanalcontenido plan ON plan.materia_id = m.id AND plan.status = TRUE
        JOIN ctr_actividad a ON a.planificacionsemanal_id = plan.id AND a.status = TRUE AND (a.oculto = FALSE OR a.oculto IS NULL)
        LEFT JOIN ctr_entregaactividad e_act ON e_act.actividad_id = a.id AND e_act.materiaasignada_id = ma.id AND e_act.status = TRUE
        LEFT JOIN ctr_notaactividad n_act ON n_act.actividad_id = a.id AND n_act.materiaasignada_id = ma.id AND n_act.status = TRUE
        WHERE est.persona_id = %s AND per.id = %s
        ORDER BY a.fechafin ASC NULLS LAST, a.id DESC
    """
    rows = _query_all(sql, [persona_id, periodo_id])
    actividades = []
    for r in rows:
        fechafin_dt = r['fechafin']
        is_expired = bool(r['cerrada']) or (fechafin_dt is not None and fechafin_dt < now)
        actividades.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'descripcion': r['descripcion'] or '',
            'fechainicio': str(r['fechainicio']) if r['fechainicio'] else None,
            'fechafin': str(r['fechafin']) if r['fechafin'] else None,
            'cerrada': bool(r['cerrada']),
            'ponderacion': float(r['ponderacion']) if r['ponderacion'] is not None else 10.0,
            'tipoentrega': r['tipoentrega'] or 1,
            'materia_id': r['materia_id'],
            'materia_asignada_id': r['materia_asignada_id'],
            'materia_nombre': r['materia_nombre'],
            'materia_color': r['materia_color'],
            'entregada': r['entrega_id'] is not None,
            'fecha_entrega': str(r['fecha_entrega']) if r['fecha_entrega'] else None,
            'nota': float(r['nota']) if r['nota'] is not None else None,
            'vencida': is_expired and r['entrega_id'] is None,
        })
    return {
        'activities': actividades,
        'total': len(actividades),
        'pending_count': len([a for a in actividades if not a['entregada'] and not a['vencida']])
    }
