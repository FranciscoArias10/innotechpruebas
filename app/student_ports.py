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
from django.db import connection, transaction


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

    # Consultar actividades con o sin nota y su retroalimentacion docente
    sql_actividades = """
        SELECT a.id, a.nombre as name, a.fechainicio, a.fechafin,
               ROUND(CAST(COALESCE(a.ponderacion, 10) AS numeric), 2) as max_score,
               na.id as grade_id, na.nota as grade, na.observacion as feedback, na.fecha as grade_date
        FROM ctr_actividad a
        JOIN ctr_planificacionsemanalcontenido psc ON psc.id = a.planificacionsemanal_id AND psc.status = TRUE
        JOIN ctr_materia mat ON mat.id = psc.materia_id
        JOIN ctr_materiaasignada ma ON ma.materia_id = mat.id AND ma.id = %s
        LEFT JOIN ctr_notaactividad na ON na.actividad_id = a.id AND na.materiaasignada_id = ma.id AND na.status = TRUE
        WHERE a.status = TRUE
        ORDER BY a.fechafin DESC NULLS LAST, a.id DESC
    """
    actividades_rows = _query_all(sql_actividades, [materia_asignada_id])
    actividades_list = []
    for a in actividades_rows:
        actividades_list.append({
            'id': a['id'],
            'name': a['name'],
            'max_score': float(a['max_score'] or 10.0),
            'grade': float(a['grade']) if a['grade'] is not None else None,
            'feedback': a['feedback'] or '',
            'grade_date': str(a['grade_date']) if a['grade_date'] else None,
            'due_date': str(a['fechafin']) if a['fechafin'] else None,
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
        },
        'graded_activities': actividades_list
    }


def obtener_asistencia_estudiante(persona_id, periodo_id):
    """
    Reporte consolidado de asistencia por asignatura para el estudiante en el periodo.
    """
    sql = """
        SELECT 
            ma.id as materia_asignada_id,
            ma.id as cronograma_id,
            asig.id as subject_id,
            asig.nombre as name,
            COALESCE(NULLIF(asig.color, ''), '#0073bc') as color,
            COALESCE(ma.asist_presente, 0) as attended_hours,
            COALESCE(ma.falta_justificada_dia, 0) as justified_hours,
            COALESCE(ma.asist_pendiente, 0) as pending_hours,
            COALESCE(ma.falta_injustificada_dia, 0) as absent_hours,
            COALESCE(ma.asist_total, 0) as total_hours,
            ROUND(CAST(COALESCE(ma.asistenciafinal, 0) AS numeric), 1) as percentage,
            TRIM(COALESCE(p.nombres, '') || ' ' || COALESCE(p.apellido_1, '')) as student_name,
            per.nombre as period_name
        FROM ctr_estudiante e
        JOIN ctr_persona p ON p.id = e.persona_id
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
    student_name = rows[0]['student_name'] if rows else ''
    period_name = rows[0]['period_name'] if rows else ''

    for r in rows:
        pct = float(r['percentage'])
        total_h = r['total_hours'] if r['total_hours'] > 0 else (r['attended_hours'] + r['absent_hours'])
        if pct == 0.0 and total_h > 0 and (r['attended_hours'] + r['justified_hours']) > 0:
            pct = round(((r['attended_hours'] + r['justified_hours']) / total_h) * 100, 1)

        if pct >= 90:
            st = 'excelente'
        elif pct >= 75:
            st = 'normal'
        else:
            st = 'riesgo'

        subjects.append({
            'materia_asignada_id': r['materia_asignada_id'],
            'cronograma_id': r['cronograma_id'],
            'subject_id': r['subject_id'],
            'name': r['name'],
            'color': r['color'],
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

    return {
        'student': {
            'id': persona_id,
            'full_name': student_name
        },
        'period': {
            'id': periodo_id,
            'name': period_name
        },
        'subjects': subjects
    }


def obtener_lecciones_estudiante(persona_id, periodo_id, materia_asignada_id=None):
    """
    Lista detallada de lecciones y registros de asistencia por fecha para el estudiante.
    """
    params = [persona_id, periodo_id]
    filtro_ma = ""
    if materia_asignada_id:
        filtro_ma = " AND ma.id = %s "
        params.append(materia_asignada_id)

    sql = f"""
        SELECT 
            l.id as id,
            al.id as asistencia_id,
            ma.id as materia_asignada_id,
            asig.nombre as materia_nombre,
            COALESCE(NULLIF(asig.color, ''), '#0073bc') as materia_color,
            TO_CHAR(l.fecha, 'YYYY-MM-DD') as fecha,
            COALESCE(TO_CHAR(l.horaentrada, 'HH24:MI'), TO_CHAR(t.comienza, 'HH24:MI'), '08:00') as hora_inicio,
            COALESCE(TO_CHAR(l.horasalida, 'HH24:MI'), TO_CHAR(t.termina, 'HH24:MI'), '08:45') as hora_fin,
            al.asistio,
            COALESCE(l.observacion, '') as observacion,
            TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as profesor,
            CASE 
                WHEN jad.id IS NOT NULL THEN 'justificada'
                WHEN al.asistio = FALSE THEN 'falta'
                WHEN l.observacion ILIKE '%%atraso%%' THEN 'atraso'
                ELSE 'presente'
            END as estado,
            (jad.id IS NOT NULL) as justificada
        FROM ctr_asistencialeccion al
        JOIN ctr_leccion l ON l.id = al.leccion_id AND l.status = TRUE
        JOIN ctr_clase cl ON cl.id = l.clase_id AND cl.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.id = al.materiaasignada_id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_estudiante e ON e.id = m.estudiante_id
        LEFT JOIN ctr_turno t ON t.id = cl.turno_id
        LEFT JOIN ctr_profesor prof ON prof.id = cl.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        LEFT JOIN ctr_justificacionasistenciadetalle jad ON jad.asistencialeccion_id = al.id AND jad.status = TRUE
        WHERE e.persona_id = %s AND per.id = %s {filtro_ma}
        ORDER BY l.fecha DESC, hora_inicio DESC
    """
    rows = _query_all(sql, params)
    return {'lessons': rows}


def registrar_justificacion_asistencia(persona_id, periodo_id, materia_asignada_ids, fecha_inicio, fecha_fin, motivo, ruta_archivo='', usuario_id=None):
    """
    Registra una solicitud de justificación de inasistencia en ctr_justificacionasistencia.
    """
    sql_mat = """
        SELECT m.id as matricula_id 
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        WHERE e.persona_id = %s AND pl.periodo_id = %s
        LIMIT 1
    """
    m_row = _query_one(sql_mat, [persona_id, periodo_id])
    if not m_row:
        raise LookupError("No se encontró matrícula activa para este periodo.")

    matricula_id = m_row['matricula_id']

    from django.db import connection, transaction
    with connection.cursor() as cur:
        cur.execute("""
            INSERT INTO ctr_justificacionasistencia (
                fecha_creacion, fecha_modificacion, status, fechaclaseinicio, fechaclasefin,
                observacion, archivo, fecha, estado, matricula_id, persona_id, usuario_creacion_id
            ) VALUES (
                NOW(), NOW(), TRUE, %s, %s, %s, %s, NOW(), 1, %s, %s, %s
            ) RETURNING id
        """, [fecha_inicio, fecha_fin, motivo, ruta_archivo, matricula_id, persona_id, usuario_id])
        justificacion_id = cur.fetchone()[0]

        if isinstance(materia_asignada_ids, (int, str)):
            materia_asignada_ids = [materia_asignada_ids]

        for ma_id in (materia_asignada_ids or []):
            try:
                ma_int = int(ma_id)
            except (ValueError, TypeError):
                continue
            cur.execute("""
                INSERT INTO ctr_justificacionasistenciama (
                    fecha_creacion, fecha_modificacion, status, justificacionasistencia_id, materiaasignada_id, usuario_creacion_id
                ) VALUES (
                    NOW(), NOW(), TRUE, %s, %s, %s
                ) RETURNING id
            """, [justificacion_id, ma_int, usuario_id])
            just_ma_id = cur.fetchone()[0]

            cur.execute("""
                SELECT al.id FROM ctr_asistencialeccion al
                JOIN ctr_leccion l ON l.id = al.leccion_id
                WHERE al.materiaasignada_id = %s 
                  AND l.fecha >= %s AND l.fecha <= %s
                  AND al.asistio = FALSE
            """, [ma_int, fecha_inicio, fecha_fin])
            faltas = cur.fetchall()
            for f in faltas:
                al_id = f[0]
                cur.execute("""
                    INSERT INTO ctr_justificacionasistenciadetalle (
                        fecha_creacion, fecha_modificacion, status, asistio, asistencialeccion_id, justificacionamateriaasignada_id, usuario_creacion_id
                    ) VALUES (
                        NOW(), NOW(), TRUE, TRUE, %s, %s, %s
                    )
                """, [al_id, just_ma_id, usuario_id])

    return {
        'id': justificacion_id,
        'estado': 1,
        'estado_texto': 'Pendiente de revisión',
        'fechaclaseinicio': str(fecha_inicio),
        'fechaclasefin': str(fecha_fin),
        'motivo': motivo,
        'archivo': ruta_archivo
    }


def obtener_justificaciones_estudiante(persona_id, periodo_id):
    """
    Retorna el historial de solicitudes de justificación del estudiante en el periodo.
    """
    sql = """
        SELECT 
            ja.id,
            TO_CHAR(ja.fecha, 'YYYY-MM-DD HH24:MI') as fecha_solicitud,
            TO_CHAR(ja.fechaclaseinicio, 'YYYY-MM-DD') as fechaclaseinicio,
            TO_CHAR(ja.fechaclasefin, 'YYYY-MM-DD') as fechaclasefin,
            ja.observacion as motivo,
            COALESCE(ja.archivo, '') as archivo,
            ja.estado,
            CASE 
                WHEN ja.estado = 3 THEN 'Aprobada'
                WHEN ja.estado IN (2, 4) THEN 'Rechazada'
                ELSE 'Pendiente de revisión'
            END as estado_texto,
            COALESCE(string_agg(DISTINCT asig.nombre, ', '), 'Varias materias') as materias
        FROM ctr_justificacionasistencia ja
        JOIN ctr_matricula m ON m.id = ja.matricula_id
        JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        LEFT JOIN ctr_justificacionasistenciama jma ON jma.justificacionasistencia_id = ja.id AND jma.status = TRUE
        LEFT JOIN ctr_materiaasignada ma ON ma.id = jma.materiaasignada_id
        LEFT JOIN ctr_materia mat ON mat.id = ma.materia_id
        LEFT JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        LEFT JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        WHERE ja.persona_id = %s AND pl.periodo_id = %s AND ja.status = TRUE
        GROUP BY ja.id, ja.fecha, ja.fechaclaseinicio, ja.fechaclasefin, ja.observacion, ja.archivo, ja.estado
        ORDER BY ja.fecha DESC
    """
    rows = _query_all(sql, [persona_id, periodo_id])
    return {'justifications': rows}


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
        WHERE e.persona_id = %s AND (per.id = %s OR pl.id = %s)
        ORDER BY cl.dia ASC, t.comienza ASC
    """
    rows = _query_all(sql, [persona_id, periodo_id, periodo_id])

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
            'docente': r['profesor'] or 'Docente Asignado',
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
            SELECT act.id, act.nombre, act.descripcion, act.fechainicio, act.fechafin, act.archivo, act.cerrada,
                   c.id as cuestionario_id
            FROM ctr_actividad act 
            LEFT JOIN ctr_cuestionario c ON c.actividad_id = act.id AND c.status = TRUE
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


def obtener_avisos_estudiante(persona_id, limite=50):
    """
    Obtiene la lista de comunicados y correos dirigidos al estudiante desde ctr_correopara y ctr_correo,
    asi como las noticias institucionales activas en ctr_noticia.
    """
    import re

    sql_correos = """
        SELECT 
            cp.id AS correopara_id,
            c.id AS correo_id,
            c.asunto,
            c.contenido,
            c.fecha,
            cp.estado,
            c.origen,
            p.id AS remitente_persona_id,
            p.nombres AS remitente_nombres,
            p.apellido_1 AS remitente_ap1,
            p.apellido_2 AS remitente_ap2,
            p.foto AS remitente_foto
        FROM ctr_correopara cp
        JOIN ctr_correo c ON c.id = cp.correo_id
        LEFT JOIN ctr_persona p ON p.id = c.persona_id
        WHERE cp.persona_id = %s
        ORDER BY c.fecha DESC
        LIMIT %s
    """
    rows = _query_all(sql_correos, [persona_id, limite])

    avisos = []
    for r in rows:
        asunto = r['asunto'] or 'Comunicado sin asunto'
        contenido = r['contenido'] or ''
        leido = (r['estado'] == 2)

        # Determinar remitente
        if r['remitente_nombres']:
            remitente = f"{r['remitente_nombres']} {r['remitente_ap1'] or ''}".strip()
        elif r['origen'] == 'BALCON':
            remitente = 'Balcón de Servicios Académicos'
        elif r['origen'] == 'DECE':
            remitente = 'Departamento DECE'
        elif r['origen'] == 'SECRETARIA':
            remitente = 'Secretaría General UNIEBEC'
        elif r['origen'] == 'RECTORADO':
            remitente = 'Rectorado Institucional'
        else:
            remitente = 'Unidad Educativa Bolivariana'

        # Determinar tipo / categoria
        asunto_l = asunto.lower()
        if 'tarea' in asunto_l or 'actividad' in asunto_l:
            tipo = 'tarea'
        elif 'nota' in asunto_l or 'calificaci' in asunto_l:
            tipo = 'calificacion'
        elif 'asistencia' in asunto_l or 'falta' in asunto_l:
            tipo = 'asistencia'
        elif 'dece' in asunto_l or r['origen'] == 'DECE':
            tipo = 'dece'
        elif r['origen'] in ('BALCON', 'SECRETARIA', 'RECTORADO'):
            tipo = 'institucional'
        elif r['origen'] == 'DOCENTE':
            tipo = 'docente'
        else:
            tipo = 'comunicado'

        # Extraer enlaces y adjuntos del contenido
        adjuntos = []
        links = re.findall(r'<a\s+(?:[^>]*?\s+)?href="([^"]+)"[^>]*>(.*?)</a>', contenido, re.IGNORECASE)
        for href, texto in links:
            nombre_limpio = re.sub(r'<[^>]+>', '', texto).strip() or 'Archivo adjunto'
            es_pdf = '.pdf' in href.lower()
            es_img = any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])
            adjuntos.append({
                'url': href,
                'nombre': nombre_limpio,
                'tipo': 'pdf' if es_pdf else ('imagen' if es_img else 'enlace')
            })

        # Limpiar etiquetas HTML para vista previa en lista
        texto_plano = re.sub(r'<br\s*/?>', chr(10), contenido)
        texto_plano = re.sub(r'</p>', chr(10), texto_plano)
        texto_plano = re.sub(r'<[^>]+>', '', texto_plano)
        texto_plano = re.sub(r'\s+', ' ', texto_plano).strip()

        fecha_val = r['fecha']
        fecha_str = fecha_val.strftime('%Y-%m-%d %H:%M') if fecha_val else ''

        avisos.append({
            'id': r['correopara_id'],
            'correo_id': r['correo_id'],
            'asunto': asunto,
            'contenido_html': contenido,
            'resumen': texto_plano[:160] + ('...' if len(texto_plano) > 160 else ''),
            'fecha': fecha_str,
            'fecha_iso': fecha_val.isoformat() if fecha_val else None,
            'leido': leido,
            'estado': r['estado'],
            'tipo': tipo,
            'origen': r['origen'] or 'INSTITUCION',
            'remitente': remitente,
            'remitente_foto': r['remitente_foto'] or '',
            'adjuntos': adjuntos,
        })

    # Noticias institucionales de ctr_noticia
    sql_noticias = """
        SELECT id, nombre, descripcion, imagen_principal, imagen_secundaria, inicio, fin
        FROM ctr_noticia
        WHERE activo = TRUE
        ORDER BY inicio DESC
        LIMIT 10
    """
    noticias = _query_all(sql_noticias)
    for n in noticias:
        avisos.append({
            'id': 100000 + n['id'],
            'correo_id': None,
            'asunto': n['nombre'],
            'contenido_html': n['descripcion'] or '',
            'resumen': (n['descripcion'] or '')[:160],
            'fecha': str(n['inicio']) if n['inicio'] else '',
            'fecha_iso': str(n['inicio']) if n['inicio'] else None,
            'leido': True,
            'estado': 2,
            'tipo': 'noticia',
            'origen': 'NOTICIA',
            'remitente': 'Dirección General',
            'remitente_foto': '',
            'adjuntos': [
                {'url': n['imagen_principal'], 'nombre': 'Imagen institucional', 'tipo': 'imagen'}
            ] if n.get('imagen_principal') else [],
        })

    return {
        'notices': avisos,
        'total': len(avisos),
        'unread_count': len([a for a in avisos if not a['leido']])
    }


def obtener_detalle_aviso(persona_id, correo_id):
    """
    Retorna el detalle completo de un comunicado y lo marca como leido.
    """
    resumen = obtener_avisos_estudiante(persona_id, limite=100)
    for aviso in resumen['notices']:
        if aviso['correo_id'] == correo_id or aviso['id'] == correo_id:
            marcar_aviso_leido(persona_id, correo_id)
            aviso['leido'] = True
            aviso['estado'] = 2
            return aviso
    raise LookupError(f"No se encontro el aviso con identificador {correo_id}")


def marcar_aviso_leido(persona_id, correo_id):
    """
    Marca como leido un correo en ctr_correopara.
    """
    with connection.cursor() as c:
        c.execute("""
            UPDATE ctr_correopara
            SET estado = 2, fecha_modificacion = NOW()
            WHERE persona_id = %s AND (correo_id = %s OR id = %s)
        """, [persona_id, correo_id, correo_id])
        return c.rowcount > 0


def marcar_todos_avisos_leidos(persona_id):
    """
    Marca todos los comunicados del estudiante como leidos.
    """
    with connection.cursor() as c:
        c.execute("""
            UPDATE ctr_correopara
            SET estado = 2, fecha_modificacion = NOW()
            WHERE persona_id = %s AND estado = 1
        """, [persona_id])
        return c.rowcount


def obtener_conteo_avisos_no_leidos(persona_id):
    """
    Retorna la cantidad de comunicados no leidos para la campana y badge.
    """
    sql = "SELECT COUNT(*) AS total FROM ctr_correopara WHERE persona_id = %s AND estado = 1"
    row = _query_one(sql, [persona_id])
    return row['total'] if row else 0


def enviar_push_a_usuario(usuario_id, titulo, cuerpo, datos=None):
    """
    Envia una notificacion push de Expo a todos los dispositivos activos registrados
    para el usuario especificado.
    """
    from app.models import DispositivoRegistrado
    import json
    import urllib.request

    dispositivos = DispositivoRegistrado.objects.filter(usuario_id=usuario_id, activo=True)
    tokens = [d.token for d in dispositivos if d.token and d.token.startswith('ExponentPushToken')]
    if not tokens:
        return 0

    mensajes = []
    for t in tokens:
        mensajes.append({
            'to': t,
            'sound': 'default',
            'title': titulo,
            'body': cuerpo,
            'data': datos or {},
        })

    try:
        req = urllib.request.Request(
            'https://exp.host/--/api/v2/push/send',
            data=json.dumps(mensajes).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return len(mensajes)
    except Exception as e:
        print(f"Error enviando push expo: {e}")
        return 0


# ==============================================================================
# FASE 2 / TAREA 10: CHAT CON DOCENTES Y COMPAÑEROS
# ==============================================================================

def obtener_contactos_chat(persona_id, periodo_id=None):
    """
    Retorna los contactos autorizados para mensajería:
    - Si es docente: estudiantes que cursan sus materias y colegas docentes.
    - Si es estudiante: docentes de sus asignaturas y compañeros de aula.
    """
    prof_row = _query_one("SELECT id FROM ctr_profesor WHERE persona_id = %s AND status = TRUE LIMIT 1", [persona_id])
    if prof_row:
        sql_alumnos = """
            SELECT DISTINCT
                est_p.id as persona_id,
                TRIM(COALESCE(est_p.nombres, '') || ' ' || COALESCE(est_p.apellido_1, '') || ' ' || COALESCE(est_p.apellido_2, '')) as nombre_completo,
                COALESCE(est_p.correo, '') as correo,
                COALESCE(est_p.foto, '') as foto,
                STRING_AGG(DISTINCT asig.nombre, ', ') as info,
                'companero' as tipo
            FROM ctr_profesor prof
            JOIN ctr_profesormateria pm ON pm.profesor_id = prof.id AND pm.status = TRUE
            JOIN ctr_materia mat ON mat.id = pm.materia_id
            JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
            JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
            JOIN ctr_materiaasignada ma ON ma.materia_id = mat.id AND ma.status = TRUE
            JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
            JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
            JOIN ctr_estudiante e ON e.id = m.estudiante_id AND e.status = TRUE
            JOIN ctr_persona est_p ON est_p.id = e.persona_id
            WHERE prof.persona_id = %s
            GROUP BY est_p.id, est_p.nombres, est_p.apellido_1, est_p.apellido_2, est_p.correo, est_p.foto
            ORDER BY nombre_completo ASC
        """
        alumnos = _query_all(sql_alumnos, [persona_id])

        sql_colegas = """
            SELECT DISTINCT
                p.id as persona_id,
                TRIM(COALESCE(p.nombres, '') || ' ' || COALESCE(p.apellido_1, '') || ' ' || COALESCE(p.apellido_2, '')) as nombre_completo,
                COALESCE(p.correo, '') as correo,
                COALESCE(p.foto, '') as foto,
                'Docente' as info,
                'docente' as tipo
            FROM ctr_profesor pr
            JOIN ctr_persona p ON p.id = pr.persona_id AND p.status = TRUE
            WHERE pr.persona_id != %s AND pr.status = TRUE
            ORDER BY nombre_completo ASC
        """
        colegas = _query_all(sql_colegas, [persona_id])

        todos = colegas + alumnos
        return {
            'total': len(todos),
            'docentes': colegas,
            'companeros': alumnos,
            'contacts': todos
        }

    # 1. Docentes
    sql_docentes = """
        SELECT 
            prof_p.id as persona_id,
            TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '') || ' ' || COALESCE(prof_p.apellido_2, '')) as nombre_completo,
            COALESCE(prof_p.correo, '') as correo,
            COALESCE(prof_p.foto, '') as foto,
            STRING_AGG(DISTINCT asig.nombre, ', ') as info,
            'docente' as tipo
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = m.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE e.persona_id = %s
        GROUP BY prof_p.id, prof_p.nombres, prof_p.apellido_1, prof_p.apellido_2, prof_p.correo, prof_p.foto
        ORDER BY nombre_completo ASC
    """
    docentes = _query_all(sql_docentes, [persona_id])

    # 2. Compañeros de aula
    sql_companeros = """
        SELECT DISTINCT
            comp_p.id as persona_id,
            TRIM(COALESCE(comp_p.nombres, '') || ' ' || COALESCE(comp_p.apellido_1, '') || ' ' || COALESCE(comp_p.apellido_2, '')) as nombre_completo,
            COALESCE(comp_p.correo, '') as correo,
            COALESCE(comp_p.foto, '') as foto,
            COALESCE('Paralelo ' || par.nombre, 'Compañero de aula') as info,
            'companero' as tipo
        FROM ctr_estudiante e
        JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        JOIN ctr_matricula comp_m ON comp_m.nivel_id = m.nivel_id AND comp_m.paralelo_id = m.paralelo_id AND comp_m.periodolectivo_id = m.periodolectivo_id AND comp_m.status = TRUE
        JOIN ctr_estudiante comp_e ON comp_e.id = comp_m.estudiante_id
        JOIN ctr_persona comp_p ON comp_p.id = comp_e.persona_id
        LEFT JOIN ctr_paralelo par ON par.id = comp_m.paralelo_id
        WHERE e.persona_id = %s AND comp_p.id != %s
        ORDER BY nombre_completo ASC
    """
    companeros = _query_all(sql_companeros, [persona_id, persona_id])

    # Unir todos los contactos
    todos = docentes + companeros

    return {
        'total': len(todos),
        'docentes': docentes,
        'companeros': companeros,
        'contacts': todos
    }


def obtener_conversaciones_chat(persona_id):
    """
    Retorna la lista de conversaciones activas del usuario con el último mensaje y no leídos.
    """
    sql = """
        SELECT 
            c.id,
            c.type,
            c.direct_key,
            COALESCE(c.last_message_preview, '') as last_message_preview,
            c.last_message_at,
            c.last_message_sender_id,
            other_p.id as other_id,
            TRIM(COALESCE(other_p.nombres, '') || ' ' || COALESCE(other_p.apellido_1, '') || ' ' || COALESCE(other_p.apellido_2, '')) as other_name,
            COALESCE(other_p.foto, '') as other_photo,
            COALESCE(other_p.correo, '') as other_email,
            COALESCE(other_part.role, 'member') as other_role,
            (
                SELECT COUNT(*) 
                FROM chat_message m 
                WHERE m.conversation_id = c.id 
                  AND m.sender_id != %s 
                  AND (my_part.last_read_at IS NULL OR m.created_at > my_part.last_read_at)
                  AND m.is_deleted = FALSE
            ) as unread_count
        FROM chat_conversation c
        JOIN chat_conversation_participant my_part ON my_part.conversation_id = c.id AND my_part.persona_id = %s AND my_part.is_active = TRUE
        JOIN chat_conversation_participant other_part ON other_part.conversation_id = c.id AND other_part.persona_id != %s
        JOIN ctr_persona other_p ON other_p.id = other_part.persona_id
        ORDER BY c.last_message_at DESC NULLS LAST
    """
    rows = _query_all(sql, [persona_id, persona_id, persona_id])

    items = []
    total_no_leidos = 0
    for r in rows:
        unread = int(r.get('unread_count', 0))
        total_no_leidos += unread
        last_dt = r.get('last_message_at')
        fecha_str = last_dt.strftime('%H:%M') if last_dt else ''
        fecha_iso = last_dt.isoformat() if last_dt else ''

        items.append({
            'id': r['id'],
            'type': r['type'],
            'unread_count': unread,
            'last_message': {
                'content': r['last_message_preview'],
                'sender_id': r['last_message_sender_id'],
                'is_mine': (r['last_message_sender_id'] == persona_id),
                'created_at': fecha_iso,
                'hora': fecha_str,
            },
            'other_participant': {
                'id': r['other_id'],
                'persona_id': r['other_id'],
                'name': r['other_name'],
                'photo': r['other_photo'],
                'email': r['other_email'],
                'role': r['other_role'],
                'tipo': 'docente' if r['other_role'] == 'teacher' else 'companero',
            },
            'updated_at': fecha_iso,
        })

    return {
        'conversations': items,
        'total': len(items),
        'unread_count': total_no_leidos,
    }


def crear_o_abrir_conversacion(persona_id, destinatario_id, mensaje_inicial=None):
    """
    Abre la conversación existente con el destinatario o crea una nueva si no existe.
    """
    if int(persona_id) == int(destinatario_id):
        raise ValueError("No puedes iniciar una conversación contigo mismo.")

    # Verificar que el destinatario sea persona válida
    dest = _query_one("SELECT id, nombres, apellido_1, apellido_2, correo, foto FROM ctr_persona WHERE id = %s", [destinatario_id])
    if not dest:
        raise LookupError("El usuario destinatario no existe.")

    direct_key = f"{min(int(persona_id), int(destinatario_id))}_{max(int(persona_id), int(destinatario_id))}"

    # Buscar conversación existente
    conv = _query_one("SELECT id FROM chat_conversation WHERE direct_key = %s LIMIT 1", [direct_key])

    if conv:
        conv_id = conv['id']
    else:
        # Detectar rol del destinatario (docente o estudiante)
        es_prof = _query_one("SELECT id FROM ctr_profesor WHERE persona_id = %s", [destinatario_id])
        rol_dest = 'teacher' if es_prof else 'student'

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO chat_conversation (type, title, direct_key, created_at, updated_at, last_message_at, last_message_preview)
                VALUES ('direct', %s, %s, NOW(), NOW(), NOW(), %s)
                RETURNING id
            """, [f"Chat {dest['nombres']}", direct_key, (mensaje_inicial or '')[:90]])
            conv_id = cursor.fetchone()[0]

            # Agregar ambos participantes
            cursor.execute("""
                INSERT INTO chat_conversation_participant (conversation_id, persona_id, role, joined_at, is_active, is_muted)
                VALUES (%s, %s, 'student', NOW(), TRUE, FALSE),
                       (%s, %s, %s, NOW(), TRUE, FALSE)
            """, [conv_id, persona_id, conv_id, destinatario_id, rol_dest])

    # Si hay mensaje inicial, enviarlo
    if mensaje_inicial and str(mensaje_inicial).strip():
        enviar_mensaje_chat(persona_id, None, conv_id, mensaje_inicial.strip())

    return {
        'id': conv_id,
        'direct_key': direct_key,
        'destinatario': {
            'persona_id': dest['id'],
            'nombre': f"{dest['nombres']} {dest.get('apellido_1', '')}".strip(),
            'foto': dest.get('foto', ''),
        }
    }


def obtener_mensajes_conversacion(persona_id, conversacion_id, limite=100, antes_de_id=None):
    """
    Retorna el historial de mensajes de la conversación y marca los mensajes como leídos.
    """
    # Verificar acceso
    part = _query_one("""
        SELECT id FROM chat_conversation_participant 
        WHERE conversation_id = %s AND persona_id = %s AND is_active = TRUE
    """, [conversacion_id, persona_id])
    if not part:
        raise PermissionError("No perteneces a esta conversación.")

    params = [conversacion_id]
    filtro_antes = ""
    if antes_de_id:
        filtro_antes = "AND m.id < %s"
        params.append(antes_de_id)

    params.append(limite)

    sql_msgs = f"""
        SELECT 
            m.id,
            m.type,
            m.content,
            m.created_at,
            m.sender_id,
            m.reply_to_id,
            TRIM(COALESCE(p.nombres, '') || ' ' || COALESCE(p.apellido_1, '')) as sender_name,
            COALESCE(p.foto, '') as sender_photo
        FROM chat_message m
        JOIN ctr_persona p ON p.id = m.sender_id
        WHERE m.conversation_id = %s AND m.is_deleted = FALSE {filtro_antes}
        ORDER BY m.created_at ASC
        LIMIT %s
    """
    rows = _query_all(sql_msgs, params)

    # Buscar adjuntos si los hay
    msg_ids = [r['id'] for r in rows]
    adjuntos_por_msg = {}
    if msg_ids:
        placeholders = ', '.join(['%s'] * len(msg_ids))
        sql_adj = f"""
            SELECT id, message_id, file, original_filename, mime_type, size_bytes
            FROM chat_message_attachment
            WHERE message_id IN ({placeholders})
        """
        adj_rows = _query_all(sql_adj, msg_ids)
        for a in adj_rows:
            adjuntos_por_msg.setdefault(a['message_id'], []).append({
                'id': a['id'],
                'url': a['file'],
                'name': a['original_filename'],
                'mime_type': a['mime_type'],
                'size': a['size_bytes'],
            })

    mensajes = []
    max_id = 0
    for r in rows:
        if r['id'] > max_id:
            max_id = r['id']
        dt = r['created_at']
        mensajes.append({
            'id': r['id'],
            'type': r['type'],
            'content': r['content'],
            'created_at': dt.isoformat() if dt else '',
            'hora': dt.strftime('%H:%M') if dt else '',
            'sender_id': r['sender_id'],
            'sender_name': r['sender_name'],
            'sender_photo': r['sender_photo'],
            'is_mine': (r['sender_id'] == persona_id),
            'attachments': adjuntos_por_msg.get(r['id'], []),
        })

    # Marcar como leídos
    if max_id > 0:
        with connection.cursor() as c:
            c.execute("""
                UPDATE chat_conversation_participant 
                SET last_read_at = NOW(), last_read_message_id = %s
                WHERE conversation_id = %s AND persona_id = %s
            """, [max_id, conversacion_id, persona_id])

    return {
        'conversation_id': conversacion_id,
        'messages': mensajes,
        'total': len(mensajes),
    }


def enviar_mensaje_chat(persona_id, usuario_id, conversacion_id, contenido, tipo='text', adjuntos=None):
    """
    Inserta un nuevo mensaje, actualiza la conversación y envía push al otro participante.
    """
    # Validar participante
    part = _query_one("""
        SELECT id FROM chat_conversation_participant 
        WHERE conversation_id = %s AND persona_id = %s AND is_active = TRUE
    """, [conversacion_id, persona_id])
    if not part:
        raise PermissionError("No perteneces a esta conversación.")

    if not contenido and not adjuntos:
        raise ValueError("El mensaje no puede estar vacío.")

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO chat_message (conversation_id, sender_id, type, content, created_at, updated_at, is_deleted)
                VALUES (%s, %s, %s, %s, NOW(), NOW(), FALSE)
                RETURNING id, created_at
            """, [conversacion_id, persona_id, tipo or 'text', (contenido or '').strip()])
            row = cursor.fetchone()
            msg_id, created_at = row[0], row[1]

            # Guardar adjuntos si los hay
            adj_resultado = []
            if adjuntos and isinstance(adjuntos, list):
                import json
                for adj in adjuntos:
                    meta = adj.get('metadata') if isinstance(adj.get('metadata'), dict) else {}
                    url_val = (adj.get('url') or '')[:500]
                    name_val = (adj.get('name') or 'adjunto')[:500]
                    mime_val = (adj.get('mime_type') or 'application/octet-stream')[:127]
                    size_val = adj.get('size', 0) or 0
                    cursor.execute("""
                        INSERT INTO chat_message_attachment (message_id, file, original_filename, mime_type, size_bytes, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        RETURNING id
                    """, [
                        msg_id,
                        url_val,
                        name_val,
                        mime_val,
                        size_val,
                        json.dumps(meta)
                    ])
                    adj_id = cursor.fetchone()[0]
                    adj_resultado.append({
                        'id': adj_id,
                        'url': url_val,
                        'name': name_val,
                        'mime_type': mime_val,
                        'size': size_val,
                    })

            # Actualizar conversación
            nombre_adj = adjuntos[0].get('name') if (adjuntos and isinstance(adjuntos, list) and len(adjuntos) > 0 and adjuntos[0].get('name')) else 'Archivo adjunto'
            vista_previa = (contenido or nombre_adj)[:90]
            cursor.execute("""
                UPDATE chat_conversation
                SET last_message_at = NOW(),
                    last_message_preview = %s,
                    last_message_sender_id = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, [vista_previa, persona_id, conversacion_id])

            # Actualizar último leído para el remitente
            cursor.execute("""
                UPDATE chat_conversation_participant
                SET last_read_at = NOW(), last_read_message_id = %s
                WHERE conversation_id = %s AND persona_id = %s
            """, [msg_id, conversacion_id, persona_id])

    # Enviar push notification al destinatario
    try:
        otro = _query_one("""
            SELECT p.id as persona_id, p.nombres, p.apellido_1, COALESCE(p.usuario_id, u.id) as usuario_id
            FROM chat_conversation_participant ccp
            JOIN ctr_persona p ON p.id = ccp.persona_id
            LEFT JOIN auth_user u ON (u.id = p.usuario_id OR u.username = p.cedula OR u.email = p.correo)
            WHERE ccp.conversation_id = %s AND ccp.persona_id != %s
            LIMIT 1
        """, [conversacion_id, persona_id])

        yo = _query_one("SELECT nombres, apellido_1 FROM ctr_persona WHERE id = %s", [persona_id])
        remitente_nombre = f"{yo['nombres']} {yo.get('apellido_1', '')}".strip() if yo else 'Nuevo mensaje'

        if otro and otro.get('usuario_id'):
            enviar_push_a_usuario(
                otro['usuario_id'],
                f"Mensaje de {remitente_nombre}",
                vista_previa,
                {'pantalla': 'ChatConversacion', 'conversacionId': conversacion_id}
            )
    except Exception as e:
        print(f"Push chat error: {e}")

    return {
        'id': msg_id,
        'conversation_id': conversacion_id,
        'content': contenido,
        'type': tipo,
        'created_at': created_at.isoformat() if created_at else '',
        'hora': created_at.strftime('%H:%M') if created_at else '',
        'sender_id': persona_id,
        'is_mine': True,
        'attachments': adj_resultado,
    }


def marcar_conversacion_leida(persona_id, conversacion_id):
    """
    Marca todos los mensajes de una conversación como leídos para el usuario.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE chat_conversation_participant
            SET last_read_at = NOW(),
                last_read_message_id = COALESCE((SELECT MAX(id) FROM chat_message WHERE conversation_id = %s), 0)
            WHERE conversation_id = %s AND persona_id = %s
        """, [conversacion_id, conversacion_id, persona_id])
    return True


# ==============================================================================
# Tarea 15: Pensiones, rubros y comprobantes de pago
# ==============================================================================

def obtener_rubros_estudiante(persona_id, periodo_id=None):
    """
    Lista de rubros (pensiones, matricula, etc.) y estado de cuenta del estudiante.
    """
    params = [persona_id]
    where_periodo = ""
    if periodo_id:
        try:
            pid = int(periodo_id)
            where_periodo = "AND (pl.periodo_id = %s OR m.periodolectivo_id = %s OR r.matricula_id IS NULL OR r.saldo > 0)"
            params.extend([pid, pid])
        except (ValueError, TypeError):
            pass

    sql = f"""
        SELECT 
            r.id,
            r.nombre,
            COALESCE(tr.nombre, 'RUBRO') as tipo,
            r.cuota,
            r.fecha,
            r.fechavence,
            r.valor,
            r.valoriva,
            r.valortotal,
            r.saldo,
            r.cancelado,
            r.observacion,
            r.matricula_id,
            (SELECT COUNT(*) FROM ctr_pago p WHERE p.rubro_id = r.id AND p.status = TRUE) as total_cuotas,
            (SELECT COUNT(*) FROM ctr_pago p WHERE p.rubro_id = r.id AND p.status = TRUE AND (p.cancelado = TRUE OR p.estado = 3)) as cuotas_pagadas,
            (SELECT COUNT(*) FROM ctr_pago p WHERE p.rubro_id = r.id AND p.status = TRUE AND p.estado = 2) as cuotas_en_revision
        FROM ctr_rubro r
        LEFT JOIN ctr_tiporubro tr ON tr.id = r.tipo_id
        LEFT JOIN ctr_matricula m ON m.id = r.matricula_id
        LEFT JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        WHERE r.persona_id = %s AND r.status = TRUE
        {where_periodo}
        ORDER BY r.fechavence ASC, r.id ASC
    """
    rubros_raw = _query_all(sql, params)

    total_rubros = len(rubros_raw)
    total_facturado = 0.0
    total_saldo = 0.0
    total_pagado = 0.0
    total_vencido = 0.0
    rubros_pendientes = 0
    rubros_pagados = 0

    import datetime
    hoy = datetime.date.today()

    rubros = []
    for r in rubros_raw:
        valortotal = float(r['valortotal'] or 0)
        saldo = float(r['saldo'] or 0)
        pagado = max(0.0, valortotal - saldo)
        fechavence = r['fechavence']
        es_cancelado = bool(r['cancelado']) or saldo <= 0.001

        es_vencido = False
        if not es_cancelado and fechavence and fechavence < hoy:
            es_vencido = True
            total_vencido += saldo

        if es_cancelado:
            estado = 'pagado'
            estado_texto = 'Pagado'
            estado_tono = 'ok'
            rubros_pagados += 1
        elif r.get('cuotas_en_revision', 0) > 0:
            estado = 'en_revision'
            estado_texto = 'En revisión'
            estado_tono = 'info'
            rubros_pendientes += 1
        elif es_vencido:
            estado = 'vencido'
            estado_texto = 'Vencido'
            estado_tono = 'alerta'
            rubros_pendientes += 1
        else:
            estado = 'por_pagar'
            estado_texto = 'Por pagar'
            estado_tono = 'aviso'
            rubros_pendientes += 1

        total_facturado += valortotal
        total_saldo += saldo
        total_pagado += pagado

        rubros.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'tipo': r['tipo'],
            'cuota': r['cuota'],
            'fecha': r['fecha'].isoformat() if r['fecha'] else '',
            'fechavence': fechavence.isoformat() if fechavence else '',
            'valor': float(r['valor'] or 0),
            'valoriva': float(r['valoriva'] or 0),
            'valortotal': valortotal,
            'saldo': saldo,
            'pagado': pagado,
            'cancelado': es_cancelado,
            'observacion': r['observacion'] or '',
            'matricula_id': r['matricula_id'],
            'estado': estado,
            'estado_texto': estado_texto,
            'estado_tono': estado_tono,
            'total_cuotas': r['total_cuotas'],
            'cuotas_pagadas': r['cuotas_pagadas'],
            'cuotas_en_revision': r['cuotas_en_revision'],
        })

    estado_general = 'al_dia'
    if total_vencido > 0:
        estado_general = 'en_mora'
    elif rubros_pendientes > 0:
        estado_general = 'pendiente'

    return {
        'resumen': {
            'total_rubros': total_rubros,
            'total_facturado': round(total_facturado, 2),
            'total_saldo': round(total_saldo, 2),
            'total_pagado': round(total_pagado, 2),
            'total_vencido': round(total_vencido, 2),
            'rubros_pendientes': rubros_pendientes,
            'rubros_pagados': rubros_pagados,
            'estado_general': estado_general,
            'al_dia': total_vencido == 0 and rubros_pendientes == 0,
        },
        'rubros': rubros,
        'cuentas_bancarias': [
            {
                'banco': 'Banco Pichincha',
                'tipo_cuenta': 'Cuenta Corriente',
                'numero_cuenta': '2100234567',
                'titular': 'UNIEBEC - Unidad Educativa Bilingüe',
                'ruc': '0992345678001',
                'correo': 'colecturia@uniebec.edu.ec'
            },
            {
                'banco': 'Banco de Guayaquil',
                'tipo_cuenta': 'Cuenta Corriente',
                'numero_cuenta': '1100987654',
                'titular': 'UNIEBEC - Unidad Educativa Bilingüe',
                'ruc': '0992345678001',
                'correo': 'colecturia@uniebec.edu.ec'
            }
        ]
    }


def obtener_detalle_rubro(persona_id, rubro_id):
    """
    Retorna el detalle completo de un rubro y la lista de sus pagos/cuotas.
    """
    sql_rubro = """
        SELECT 
            r.id,
            r.nombre,
            COALESCE(tr.nombre, 'RUBRO') as tipo,
            r.cuota,
            r.fecha,
            r.fechavence,
            r.valor,
            r.valoriva,
            r.valortotal,
            r.saldo,
            r.cancelado,
            r.observacion,
            r.matricula_id
        FROM ctr_rubro r
        LEFT JOIN ctr_tiporubro tr ON tr.id = r.tipo_id
        WHERE r.id = %s AND r.persona_id = %s AND r.status = TRUE
    """
    rubro = _query_one(sql_rubro, [rubro_id, persona_id])
    if not rubro:
        return None

    import datetime
    hoy = datetime.date.today()

    sql_pagos = """
        SELECT 
            p.id,
            p.rubro_id,
            p.fecha,
            p.fechapago,
            p.codigopago,
            p.valortotal,
            p.valorpago,
            p.cancelado,
            p.estado,
            p.efectivo,
            p.reversado,
            pp.id as comprobante_id,
            pp.estado as comprobante_estado,
            pp.archivo as comprobante_archivo,
            pp.fecha as comprobante_fecha,
            pp.valor as comprobante_valor,
            pp.observacion as comprobante_observacion
        FROM ctr_pago p
        LEFT JOIN (
            SELECT DISTINCT ON (pago_id) *
            FROM ctr_pagopension
            WHERE status = TRUE
            ORDER BY pago_id, id DESC
        ) pp ON pp.pago_id = p.id
        WHERE p.rubro_id = %s AND p.status = TRUE
        ORDER BY p.fecha ASC, p.id ASC
    """
    pagos_raw = _query_all(sql_pagos, [rubro_id])

    pagos = []
    for p in pagos_raw:
        estado_num = p['estado']
        cancelado = bool(p['cancelado'])
        fecha_pago_vence = p['fecha']
        es_vencido = False
        if not cancelado and fecha_pago_vence and fecha_pago_vence < hoy:
            es_vencido = True

        if cancelado or estado_num == 3:
            estado_texto = 'Pagado'
            estado_tono = 'ok'
        elif estado_num == 2 or (p.get('comprobante_id') and p.get('comprobante_estado') == 1):
            estado_texto = 'En revisión'
            estado_tono = 'info'
        elif estado_num == 4:
            estado_texto = 'Rechazado'
            estado_tono = 'peligro'
        elif estado_num == 5 or p['reversado']:
            estado_texto = 'Reversado'
            estado_tono = 'neutro'
        elif es_vencido:
            estado_texto = 'Vencido'
            estado_tono = 'alerta'
        else:
            estado_texto = 'Por pagar'
            estado_tono = 'aviso'

        comprobante = None
        if p.get('comprobante_id'):
            comprobante = {
                'id': p['comprobante_id'],
                'estado': p['comprobante_estado'],
                'estado_texto': 'En revisión' if p['comprobante_estado'] == 1 else 'Aprobado' if p['comprobante_estado'] == 3 else 'Rechazado',
                'archivo': p['comprobante_archivo'] or '',
                'fecha': p['comprobante_fecha'].isoformat() if p['comprobante_fecha'] else '',
                'valor': float(p['comprobante_valor'] or 0),
                'observacion': p['comprobante_observacion'] or '',
            }

        pagos.append({
            'id': p['id'],
            'codigopago': p['codigopago'],
            'valortotal': float(p['valortotal'] or 0),
            'valorpago': float(p['valorpago'] or 0),
            'cancelado': cancelado,
            'estado': estado_num,
            'estado_texto': estado_texto,
            'estado_tono': estado_tono,
            'fecha': fecha_pago_vence.isoformat() if fecha_pago_vence else '',
            'fechapago': p['fechapago'].isoformat() if p['fechapago'] else '',
            'comprobante': comprobante,
        })

    valortotal = float(rubro['valortotal'] or 0)
    saldo = float(rubro['saldo'] or 0)
    pagado = max(0.0, valortotal - saldo)

    return {
        'id': rubro['id'],
        'nombre': rubro['nombre'],
        'tipo': rubro['tipo'],
        'cuota': rubro['cuota'],
        'fecha': rubro['fecha'].isoformat() if rubro['fecha'] else '',
        'fechavence': rubro['fechavence'].isoformat() if rubro['fechavence'] else '',
        'valor': float(rubro['valor'] or 0),
        'valoriva': float(rubro['valoriva'] or 0),
        'valortotal': valortotal,
        'saldo': saldo,
        'pagado': pagado,
        'cancelado': bool(rubro['cancelado']),
        'observacion': rubro['observacion'] or '',
        'pagos': pagos,
    }


def registrar_comprobante_pago(persona_id, usuario_id, pago_id, archivo_subido=None, valor=None, fecha=None, observacion=None):
    """
    Sube y registra el comprobante de pago de una cuota de pensión, quedando en revisión para Colecturía.
    """
    sql_valida = """
        SELECT p.id, p.valortotal, p.valorpago, p.estado, p.cancelado, r.id as rubro_id
        FROM ctr_pago p
        JOIN ctr_rubro r ON r.id = p.rubro_id
        WHERE p.id = %s AND r.persona_id = %s AND p.status = TRUE
    """
    pago = _query_one(sql_valida, [pago_id, persona_id])
    if not pago:
        raise LookupError("El pago seleccionado no existe o no corresponde a tu cuenta.")

    import os
    import datetime
    from django.core.files.storage import default_storage
    from django.utils.text import get_valid_filename

    hoy = datetime.date.today()
    fecha_comprobante = fecha or hoy
    valor_comprobante = valor if valor is not None else float(pago['valortotal'] or 0)

    # Guardar archivo si viene
    ruta_guardada = ""
    if archivo_subido:
        nombre_limpio = get_valid_filename(getattr(archivo_subido, 'name', 'comprobante.jpg'))
        timestamp = int(datetime.datetime.now().timestamp())
        subruta = os.path.join('comprobantes', f"{persona_id}_{pago_id}_{timestamp}_{nombre_limpio}")
        ruta_guardada = default_storage.save(subruta, archivo_subido)

    obs_final = observacion or "Comprobante de transferencia subido desde la app móvil"

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ctr_pagopension (
                pago_id,
                archivo,
                fecha,
                valor,
                observacion,
                estado,
                status,
                fecha_creacion,
                usuario_creacion_id
            ) VALUES (%s, %s, %s, %s, %s, 1, TRUE, NOW(), %s)
            RETURNING id, fecha_creacion
        """, [pago_id, ruta_guardada, fecha_comprobante, valor_comprobante, obs_final, usuario_id])
        pp_id, fecha_creacion = cursor.fetchone()

        # Actualizar estado de ctr_pago a 2 (En revisión por Colecturía)
        cursor.execute("""
            UPDATE ctr_pago
            SET estado = 2,
                fecha_modificacion = NOW(),
                usuario_modificacion_id = %s
            WHERE id = %s
        """, [usuario_id, pago_id])

    return {
        'id': pp_id,
        'pago_id': pago_id,
        'archivo': ruta_guardada,
        'fecha': fecha_comprobante.isoformat() if isinstance(fecha_comprobante, datetime.date) else str(fecha_comprobante),
        'valor': float(valor_comprobante),
        'observacion': obs_final,
        'estado': 1,
        'estado_texto': 'En revisión (esperando validación de Colecturía)',
        'fecha_creacion': fecha_creacion.isoformat() if fecha_creacion else '',
    }


# =========================================================================
# TAREA 12: FOROS DE DISCUSIÓN Y CONSULTAS AL DOCENTE
# =========================================================================

def verificar_matricula_estudiante_materia(persona_id, materia_asignada_id):
    """
    Verifica que el estudiante (persona_id) esté matriculado activamente en la materia_asignada_id.
    Retorna la información básica de la materia asignada o lanza PermissionError / LookupError.
    """
    sql = """
        SELECT ma.id as materia_asignada_id,
               ma.materia_id,
               asig.nombre as materia_nombre,
               e.id as estudiante_id,
               p_est.id as persona_id,
               TRIM(COALESCE(p_est.nombres, '') || ' ' || COALESCE(p_est.apellido_1, '') || ' ' || COALESCE(p_est.apellido_2, '')) as estudiante_nombre,
               TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as docente_nombre,
               prof.id as profesor_id
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_estudiante e ON e.id = m.estudiante_id AND e.status = TRUE
        JOIN ctr_persona p_est ON p_est.id = e.persona_id
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE ma.id = %s AND ma.status = TRUE
        LIMIT 1
    """
    info = _query_one(sql, [materia_asignada_id])
    if not info:
        raise LookupError("La materia asignada no existe o no se encuentra activa.")
    if info['persona_id'] != persona_id:
        raise PermissionError("No tienes permiso para acceder a esta materia.")
    return info



def asegurar_foros_para_materia(materia_id, materia_nombre):
    """
    Garantiza que la materia tenga planificacion semanal y foros de discusion activos
    para que los estudiantes siempre dispongan de espacios de consulta y debate.
    """
    with connection.cursor() as cursor:
        # 1. Asegurar planificacion semanal
        cursor.execute("""
            SELECT id FROM ctr_planificacionsemanalcontenido
            WHERE materia_id = %s AND status = TRUE
            ORDER BY id ASC LIMIT 1;
        """, [materia_id])
        row_psc = cursor.fetchone()
        if not row_psc:
            cursor.execute("""
                INSERT INTO ctr_planificacionsemanalcontenido (
                    fecha_creacion, fecha_modificacion, status,
                    destreza, inicio, fin, estado, materia_id
                ) VALUES (
                    NOW(), NOW(), TRUE,
                    'Planificacion Academica y Espacios de Interaccion',
                    CURRENT_DATE, CURRENT_DATE + INTERVAL '120 days', 1, %s
                ) RETURNING id;
            """, [materia_id])
            psc_id = cursor.fetchone()[0]
        else:
            psc_id = row_psc[0]

        # 2. Sincronizar actividades existentes de tipo foro sin registro en ctr_foro
        cursor.execute("""
            INSERT INTO ctr_foro (
                fecha_creacion, fecha_modificacion, status,
                permite_hilos, moderado, calificable, actividad_id
            )
            SELECT 
                COALESCE(a.fecha_creacion, NOW()), 
                NOW(), 
                TRUE, 
                TRUE, 
                FALSE, 
                FALSE, 
                a.id
            FROM ctr_actividad a
            LEFT JOIN ctr_foro f ON f.actividad_id = a.id
            WHERE a.planificacionsemanal_id = %s
              AND (a.tiporecurso_id = 3 OR a.nombre ILIKE '%%FORO%%')
              AND a.status = TRUE
              AND f.id IS NULL;
        """, [psc_id])

        # 3. Contar foros activos en la materia
        cursor.execute("""
            SELECT count(f.id)
            FROM ctr_foro f
            JOIN ctr_actividad a ON a.id = f.actividad_id AND a.status = TRUE
            JOIN ctr_planificacionsemanalcontenido psc ON psc.id = a.planificacionsemanal_id AND psc.status = TRUE
            WHERE psc.materia_id = %s AND f.status = TRUE;
        """, [materia_id])
        total_foros = cursor.fetchone()[0]

        # 4. Asegurar que existan al menos 2 foros en la materia
        if total_foros == 0:
            # Crear Foro General Abierto
            cursor.execute("""
                INSERT INTO ctr_actividad (
                    fecha_creacion, fecha_modificacion, status,
                    nombre, descripcion, fechainicio, fechafin,
                    tipocalificacion, tipoentrega, oculto, archivo,
                    cerrada, librocategoria_id, planificacionsemanal_id,
                    tiporecurso_id, ponderacion
                ) VALUES (
                    NOW(), NOW(), TRUE,
                    %s, %s, NOW() - INTERVAL '1 day', NOW() + INTERVAL '60 days',
                    1, 1, FALSE, '',
                    FALSE, 1, %s,
                    3, 0
                ) RETURNING id;
            """, [
                f'Foro de Dudas y Debate General - {materia_nombre}',
                f'Bienvenidos al Foro de Dudas y Debate General de la asignatura {materia_nombre}.\n\nEste espacio está destinado a plantear consultas académicas, debatir sobre los contenidos y compartir aportes constructivos con el docente y compañeros.',
                psc_id
            ])
            act_id_1 = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO ctr_foro (
                    fecha_creacion, fecha_modificacion, status,
                    permite_hilos, moderado, calificable, actividad_id
                ) VALUES (
                    NOW(), NOW(), TRUE, TRUE, FALSE, FALSE, %s
                );
            """, [act_id_1])

            # Crear Foro Tematico #1
            cursor.execute("""
                INSERT INTO ctr_actividad (
                    fecha_creacion, fecha_modificacion, status,
                    nombre, descripcion, fechainicio, fechafin,
                    tipocalificacion, tipoentrega, oculto, archivo,
                    cerrada, librocategoria_id, planificacionsemanal_id,
                    tiporecurso_id, ponderacion
                ) VALUES (
                    NOW(), NOW(), TRUE,
                    %s, %s, NOW() - INTERVAL '1 day', NOW() + INTERVAL '30 days',
                    1, 1, FALSE, '',
                    FALSE, 1, %s,
                    3, 10
                ) RETURNING id;
            """, [
                f'FORO #1 - Conceptos Clave de {materia_nombre}',
                f'Tema: Fundamentos e introducción a {materia_nombre}\nObjetivo: Socializar conceptos principales y conocimientos previos.\nPregunta del foro: ¿Cuáles son las aplicaciones prácticas de esta asignatura en el entorno cotidiano o profesional?',
                psc_id
            ])
            act_id_2 = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO ctr_foro (
                    fecha_creacion, fecha_modificacion, status,
                    permite_hilos, moderado, calificable, actividad_id
                ) VALUES (
                    NOW(), NOW(), TRUE, TRUE, FALSE, FALSE, %s
                );
            """, [act_id_2])

        elif total_foros == 1:
            # Si solo tiene 1 foro, agregar el Foro General de Dudas y Aportes
            cursor.execute("""
                INSERT INTO ctr_actividad (
                    fecha_creacion, fecha_modificacion, status,
                    nombre, descripcion, fechainicio, fechafin,
                    tipocalificacion, tipoentrega, oculto, archivo,
                    cerrada, librocategoria_id, planificacionsemanal_id,
                    tiporecurso_id, ponderacion
                ) VALUES (
                    NOW(), NOW(), TRUE,
                    %s, %s, NOW() - INTERVAL '1 day', NOW() + INTERVAL '60 days',
                    1, 1, FALSE, '',
                    FALSE, 1, %s,
                    3, 0
                ) RETURNING id;
            """, [
                f'Foro de Dudas y Novedades - {materia_nombre}',
                f'Espacio abierto permanente para consultas sobre la planificación, tareas y fechas de evaluación en {materia_nombre}.',
                psc_id
            ])
            act_id_gen = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO ctr_foro (
                    fecha_creacion, fecha_modificacion, status,
                    permite_hilos, moderado, calificable, actividad_id
                ) VALUES (
                    NOW(), NOW(), TRUE, TRUE, FALSE, FALSE, %s
                );
            """, [act_id_gen])

def obtener_foros_materia(persona_id, materia_asignada_id):
    """
    Retorna la lista de foros de discusion de una materia asignada para el estudiante.
    Garantiza que la materia cuente con foros de consulta y debate disponibles.
    """
    materia_info = verificar_matricula_estudiante_materia(persona_id, materia_asignada_id)

    # Asegurar que existan foros de debate y consulta para esta materia
    asegurar_foros_para_materia(materia_info['materia_id'], materia_info['materia_nombre'])

    sql = """
        SELECT f.id,
               ma.id as materia_asignada_id,
               asig.nombre as materia_nombre,
               a.nombre as titulo,
               COALESCE(a.descripcion, '') as descripcion,
               COALESCE(a.fechainicio, f.fecha_creacion) as fecha_creacion,
               a.fechafin as fecha_cierre,
               CASE 
                   WHEN a.cerrada = TRUE THEN TRUE
                   WHEN a.fechafin IS NOT NULL AND a.fechafin < NOW() THEN TRUE
                   ELSE FALSE
               END as esta_cerrado,
               TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as docente_nombre,
               COUNT(pf.id) FILTER (WHERE pf.status = TRUE) as total_posts,
               MAX(pf.fecha) FILTER (WHERE pf.status = TRUE) as ultimo_post_fecha
        FROM ctr_foro f
        JOIN ctr_actividad a ON a.id = f.actividad_id AND a.status = TRUE
        JOIN ctr_planificacionsemanalcontenido psc ON psc.id = a.planificacionsemanal_id AND psc.status = TRUE
        JOIN ctr_materia mat ON mat.id = psc.materia_id
        JOIN ctr_materiaasignada ma ON ma.materia_id = mat.id AND ma.id = %s
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        LEFT JOIN ctr_postforo pf ON pf.foro_id = f.id
        WHERE f.status = TRUE
        GROUP BY f.id, ma.id, asig.nombre, a.nombre, a.descripcion, a.fechainicio, a.fechafin, a.cerrada, f.fecha_creacion, prof_p.nombres, prof_p.apellido_1
        ORDER BY a.fechainicio DESC NULLS LAST, f.id DESC
    """
    rows = _query_all(sql, [materia_asignada_id])
    forums = []
    for r in rows:
        forums.append({
            'id': r['id'],
            'materia_asignada_id': r['materia_asignada_id'],
            'materia_nombre': r['materia_nombre'],
            'titulo': r['titulo'],
            'descripcion': r['descripcion'] or '',
            'fecha_creacion': r['fecha_creacion'].isoformat() if r['fecha_creacion'] else None,
            'fecha_cierre': r['fecha_cierre'].isoformat() if r['fecha_cierre'] else None,
            'esta_cerrado': bool(r['esta_cerrado']),
            'docente_nombre': r['docente_nombre'] or materia_info.get('docente_nombre', 'Docente titular'),
            'total_posts': int(r['total_posts'] or 0),
            'ultimo_post_fecha': r['ultimo_post_fecha'].isoformat() if r['ultimo_post_fecha'] else None,
        })
    return {'forums': forums}


def obtener_detalle_foro(persona_id, usuario_id, foro_id):
    """
    Retorna los datos del foro y su hilo de aportes.
    Verifica que el estudiante pertenezca a la materia asignada del foro.
    """
    # 1. Obtener datos del foro y validar si el estudiante está matriculado en la materia
    sql_foro = """
        SELECT f.id,
               ma.id as materia_asignada_id,
               asig.nombre as materia_nombre,
               a.nombre as titulo,
               COALESCE(a.descripcion, '') as descripcion,
               COALESCE(a.fechainicio, f.fecha_creacion) as fecha_creacion,
               a.fechafin as fecha_cierre,
               CASE 
                   WHEN a.cerrada = TRUE THEN TRUE
                   WHEN a.fechafin IS NOT NULL AND a.fechafin < NOW() THEN TRUE
                   ELSE FALSE
               END as esta_cerrado,
               TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as docente_nombre,
               (SELECT COUNT(pf.id) FROM ctr_postforo pf WHERE pf.foro_id = f.id AND pf.status = TRUE) as total_posts,
               e.persona_id as matriculado_persona_id
        FROM ctr_foro f
        JOIN ctr_actividad a ON a.id = f.actividad_id AND a.status = TRUE
        JOIN ctr_planificacionsemanalcontenido psc ON psc.id = a.planificacionsemanal_id AND psc.status = TRUE
        JOIN ctr_materia mat ON mat.id = psc.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        JOIN ctr_materiaasignada ma ON ma.materia_id = mat.id AND ma.status = TRUE
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_estudiante e ON e.id = m.estudiante_id AND e.status = TRUE
        WHERE f.id = %s AND e.persona_id = %s AND f.status = TRUE
        LIMIT 1
    """
    foro = _query_one(sql_foro, [foro_id, persona_id])
    if not foro:
        existe = _query_one("SELECT id FROM ctr_foro WHERE id = %s AND status = TRUE", [foro_id])
        if existe:
            raise PermissionError("No perteneces a la materia correspondiente a este foro.")
        raise LookupError("El foro especificado no existe o no está disponible.")

    # 2. Consultar aportes (posts) del foro
    sql_posts = """
        SELECT pf.id,
               pf.foro_id,
               CASE 
                   WHEN pf.profesor_id IS NOT NULL THEN prof_p.id
                   ELSE COALESCE(p_est.id, pf.usuario_creacion_id)
               END as autor_id,
               CASE 
                   WHEN pf.profesor_id IS NOT NULL THEN TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, ''))
                   ELSE TRIM(COALESCE(p_est.nombres, '') || ' ' || COALESCE(p_est.apellido_1, '') || ' ' || COALESCE(p_est.apellido_2, ''))
               END as autor_nombre,
               CASE 
                   WHEN pf.profesor_id IS NOT NULL THEN TRUE
                   ELSE FALSE
               END as es_docente,
               CASE 
                   WHEN pf.usuario_creacion_id = %s OR p_est.id = %s THEN TRUE
                   ELSE FALSE
               END as es_propio,
               pf.contenido as mensaje,
               pf.fecha,
               pf.fecha_creacion,
               pf.fecha_modificacion
        FROM ctr_postforo pf
        LEFT JOIN ctr_materiaasignada ma ON ma.id = pf.materiaasignada_id
        LEFT JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id
        LEFT JOIN ctr_matricula m ON m.id = nm.matricula_id
        LEFT JOIN ctr_estudiante e ON e.id = m.estudiante_id
        LEFT JOIN ctr_persona p_est ON p_est.id = e.persona_id
        LEFT JOIN ctr_profesor prof ON prof.id = pf.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE pf.foro_id = %s AND pf.status = TRUE
        ORDER BY pf.fecha ASC, pf.id ASC
    """
    post_rows = _query_all(sql_posts, [usuario_id, persona_id, foro_id])
    posts = []
    for p in post_rows:
        fecha_edicion = None
        if p.get('fecha_modificacion') and p.get('fecha_creacion'):
            if (p['fecha_modificacion'] - p['fecha_creacion']).total_seconds() > 2:
                fecha_edicion = p['fecha_modificacion'].isoformat()

        posts.append({
            'id': p['id'],
            'foro_id': p['foro_id'],
            'autor_id': p['autor_id'] or 0,
            'autor_nombre': p['autor_nombre'] or 'Usuario',
            'es_docente': bool(p['es_docente']),
            'es_propio': bool(p['es_propio']),
            'mensaje': p['mensaje'] or '',
            'fecha': p['fecha'].isoformat() if p.get('fecha') else (p['fecha_creacion'].isoformat() if p.get('fecha_creacion') else None),
            'fecha_edicion': fecha_edicion,
        })

    return {
        'forum': {
            'id': foro['id'],
            'materia_asignada_id': foro['materia_asignada_id'],
            'materia_nombre': foro['materia_nombre'],
            'titulo': foro['titulo'],
            'descripcion': foro['descripcion'] or '',
            'fecha_creacion': foro['fecha_creacion'].isoformat() if foro['fecha_creacion'] else None,
            'fecha_cierre': foro['fecha_cierre'].isoformat() if foro['fecha_cierre'] else None,
            'esta_cerrado': bool(foro['esta_cerrado']),
            'docente_nombre': foro['docente_nombre'] or 'Docente titular',
            'total_posts': int(foro['total_posts'] or 0),
        },
        'posts': posts
    }


def publicar_post_foro(persona_id, usuario_id, foro_id, mensaje):
    """
    Inserta un nuevo aporte de estudiante en el foro.
    Valida que el foro no esté cerrado y que el estudiante pertenezca a la materia.
    """
    sql_valida = """
        SELECT f.id,
               a.cerrada,
               a.fechafin,
               ma.id as materia_asignada_id,
               p_est.id as persona_id,
               TRIM(COALESCE(p_est.nombres, '') || ' ' || COALESCE(p_est.apellido_1, '') || ' ' || COALESCE(p_est.apellido_2, '')) as estudiante_nombre
        FROM ctr_foro f
        JOIN ctr_actividad a ON a.id = f.actividad_id AND a.status = TRUE
        JOIN ctr_planificacionsemanalcontenido psc ON psc.id = a.planificacionsemanal_id AND psc.status = TRUE
        JOIN ctr_materia mat ON mat.id = psc.materia_id
        JOIN ctr_materiaasignada ma ON ma.materia_id = mat.id AND ma.status = TRUE
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_estudiante e ON e.id = m.estudiante_id AND e.status = TRUE
        JOIN ctr_persona p_est ON p_est.id = e.persona_id
        WHERE f.id = %s AND e.persona_id = %s AND f.status = TRUE
        LIMIT 1
    """
    row = _query_one(sql_valida, [foro_id, persona_id])
    if not row:
        existe = _query_one("SELECT id FROM ctr_foro WHERE id = %s AND status = TRUE", [foro_id])
        if existe:
            raise PermissionError("No perteneces a la materia de este foro.")
        raise LookupError("El foro especificado no existe.")

    from django.utils import timezone
    now = timezone.now()
    if row.get('cerrada') or (row.get('fechafin') and row['fechafin'] < now):
        raise ValueError("El foro se encuentra cerrado para nuevas publicaciones.")

    materia_asignada_id = row['materia_asignada_id']
    estudiante_nombre = row['estudiante_nombre']

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ctr_postforo (
                fecha_creacion, fecha_modificacion, status, contenido, fecha,
                foro_id, materiaasignada_id, usuario_creacion_id, usuario_modificacion_id
            ) VALUES (
                NOW(), NOW(), TRUE, %s, NOW(),
                %s, %s, %s, %s
            ) RETURNING id, fecha
        """, [mensaje.strip(), foro_id, materia_asignada_id, usuario_id, usuario_id])
        insert_row = cursor.fetchone()
        post_id = insert_row[0]
        fecha_post = insert_row[1]

    return {
        'id': post_id,
        'foro_id': foro_id,
        'autor_id': persona_id,
        'autor_nombre': estudiante_nombre,
        'es_docente': False,
        'es_propio': True,
        'mensaje': mensaje.strip(),
        'fecha': fecha_post.isoformat() if fecha_post else now.isoformat(),
        'fecha_edicion': None,
    }


def editar_post_foro(persona_id, usuario_id, post_id, mensaje):
    """
    Edita un aporte propio en un foro.
    Solo el autor original puede editarlo.
    """
    sql_check = """
        SELECT pf.id, pf.foro_id, pf.usuario_creacion_id, pf.fecha,
               e.persona_id,
               TRIM(COALESCE(p_est.nombres, '') || ' ' || COALESCE(p_est.apellido_1, '') || ' ' || COALESCE(p_est.apellido_2, '')) as estudiante_nombre
        FROM ctr_postforo pf
        LEFT JOIN ctr_materiaasignada ma ON ma.id = pf.materiaasignada_id
        LEFT JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id
        LEFT JOIN ctr_matricula m ON m.id = nm.matricula_id
        LEFT JOIN ctr_estudiante e ON e.id = m.estudiante_id
        LEFT JOIN ctr_persona p_est ON p_est.id = e.persona_id
        WHERE pf.id = %s AND pf.status = TRUE
        LIMIT 1
    """
    post = _query_one(sql_check, [post_id])
    if not post:
        raise LookupError("El aporte especificado no existe o fue eliminado.")

    es_autor = (post['usuario_creacion_id'] == usuario_id) or (post.get('persona_id') == persona_id)
    if not es_autor:
        raise PermissionError("Solo el autor original puede editar este aporte.")

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE ctr_postforo
            SET contenido = %s,
                fecha_modificacion = NOW(),
                usuario_modificacion_id = %s
            WHERE id = %s
            RETURNING id, fecha_modificacion
        """, [mensaje.strip(), usuario_id, post_id])
        upd = cursor.fetchone()
        fecha_edicion = upd[1]

    return {
        'id': post['id'],
        'foro_id': post['foro_id'],
        'autor_id': persona_id,
        'autor_nombre': post['estudiante_nombre'] or 'Estudiante',
        'es_docente': False,
        'es_propio': True,
        'mensaje': mensaje.strip(),
        'fecha': post['fecha'].isoformat() if post.get('fecha') else None,
        'fecha_edicion': fecha_edicion.isoformat() if fecha_edicion else None,
    }


def eliminar_post_foro(persona_id, usuario_id, post_id):
    """
    Elimina (soft delete) un aporte propio en un foro.
    Solo el autor original puede eliminarlo.
    """
    sql_check = """
        SELECT pf.id, pf.usuario_creacion_id, e.persona_id
        FROM ctr_postforo pf
        LEFT JOIN ctr_materiaasignada ma ON ma.id = pf.materiaasignada_id
        LEFT JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id
        LEFT JOIN ctr_matricula m ON m.id = nm.matricula_id
        LEFT JOIN ctr_estudiante e ON e.id = m.estudiante_id
        WHERE pf.id = %s AND pf.status = TRUE
        LIMIT 1
    """
    post = _query_one(sql_check, [post_id])
    if not post:
        raise LookupError("El aporte no existe o ya fue eliminado.")

    es_autor = (post['usuario_creacion_id'] == usuario_id) or (post.get('persona_id') == persona_id)
    if not es_autor:
        raise PermissionError("Solo el autor original puede eliminar este aporte.")

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE ctr_postforo
            SET status = FALSE,
                fecha_modificacion = NOW(),
                usuario_modificacion_id = %s
            WHERE id = %s
        """, [usuario_id, post_id])

    return {'id': post_id}


def _extraer_asunto_y_pregunta(texto):
    """
    Extrae asunto y pregunta del texto almacenado en ctr_consultadocente.
    Soporta formato institucional [Asunto]\nPregunta o texto libre.
    """
    if not texto:
        return 'Consulta al docente', ''
    
    t = texto.strip()
    if t.startswith('[') and ']' in t:
        idx = t.find(']')
        asunto = t[1:idx].strip()
        pregunta = t[idx + 1:].strip()
        return asunto or 'Consulta al docente', pregunta or t
    
    lineas = t.split('\n', 1)
    if len(lineas) > 1 and len(lineas[0]) < 80:
        return lineas[0].strip(), lineas[1].strip()

    return 'Consulta al docente', t


def obtener_consultas_docente(persona_id, materia_asignada_id):
    """
    Lista las consultas privadas del estudiante en una materia y sus respuestas docentes.
    Calcula el total de respuestas nuevas (sin leer).
    """
    materia_info = verificar_matricula_estudiante_materia(persona_id, materia_asignada_id)

    # 1. Obtener todas las preguntas del estudiante (es_docente = FALSE)
    sql_preguntas = """
        SELECT cd.id, cd.texto, cd.fecha_creacion, cd.leido, cd.leido_at
        FROM ctr_consultadocente cd
        WHERE cd.materiaasignada_id = %s AND cd.es_docente = FALSE AND cd.status = TRUE
        ORDER BY cd.fecha_creacion DESC, cd.id DESC
    """
    preguntas = _query_all(sql_preguntas, [materia_asignada_id])

    # 2. Obtener respuestas docentes asociadas (es_docente = TRUE)
    sql_respuestas = """
        SELECT cd.id, cd.texto, cd.fecha_creacion, cd.leido, cd.leido_at
        FROM ctr_consultadocente cd
        WHERE cd.materiaasignada_id = %s AND cd.es_docente = TRUE AND cd.status = TRUE
        ORDER BY cd.fecha_creacion ASC
    """
    respuestas_docente = _query_all(sql_respuestas, [materia_asignada_id])

    inquiries = []
    total_nuevas = 0

    for q in preguntas:
        asunto, pregunta_txt = _extraer_asunto_y_pregunta(q['texto'])
        q_fecha = q['fecha_creacion']

        # Encontrar la respuesta docente posterior a la pregunta
        resp_encontrada = None
        for r in respuestas_docente:
            if r['fecha_creacion'] >= q_fecha:
                resp_encontrada = r
                break

        if resp_encontrada:
            respondida = True
            respuesta_txt = resp_encontrada['texto']
            fecha_resp = resp_encontrada['fecha_creacion'].isoformat()
            leida = bool(resp_encontrada['leido'])
            if not leida:
                total_nuevas += 1
        else:
            respondida = False
            respuesta_txt = None
            fecha_resp = None
            leida = bool(q['leido'])

        inquiries.append({
            'id': q['id'],
            'materia_asignada_id': materia_asignada_id,
            'materia_nombre': materia_info['materia_nombre'],
            'docente_nombre': materia_info['docente_nombre'] or 'Docente titular',
            'estudiante_id': materia_info['estudiante_id'],
            'estudiante_nombre': materia_info['estudiante_nombre'],
            'asunto': asunto,
            'pregunta': pregunta_txt,
            'fecha_pregunta': q['fecha_creacion'].isoformat() if q['fecha_creacion'] else None,
            'respuesta': respuesta_txt,
            'fecha_respuesta': fecha_resp,
            'respondida': respondida,
            'leida': leida,
        })

    return {
        'total_nuevas': total_nuevas,
        'inquiries': inquiries
    }


def crear_consulta_docente(persona_id, usuario_id, materia_asignada_id, asunto, pregunta):
    """
    Registra una nueva consulta privada enviada al docente de la materia.
    """
    materia_info = verificar_matricula_estudiante_materia(persona_id, materia_asignada_id)

    texto_completo = f"[{asunto.strip()}]\n{pregunta.strip()}"

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ctr_consultadocente (
                fecha_creacion, fecha_modificacion, status,
                es_docente, texto, imagen, leido, leido_at,
                autor_id, materiaasignada_id, usuario_creacion_id, usuario_modificacion_id
            ) VALUES (
                NOW(), NOW(), TRUE,
                FALSE, %s, '', FALSE, NULL,
                %s, %s, %s, %s
            ) RETURNING id, fecha_creacion
        """, [texto_completo, persona_id, materia_asignada_id, usuario_id, usuario_id])
        row = cursor.fetchone()
        inquiry_id = row[0]
        fecha_creacion = row[1]

    return {
        'id': inquiry_id,
        'materia_asignada_id': materia_asignada_id,
        'materia_nombre': materia_info['materia_nombre'],
        'docente_nombre': materia_info['docente_nombre'] or 'Docente titular',
        'estudiante_id': materia_info['estudiante_id'],
        'estudiante_nombre': materia_info['estudiante_nombre'],
        'asunto': asunto.strip(),
        'pregunta': pregunta.strip(),
        'fecha_pregunta': fecha_creacion.isoformat() if fecha_creacion else None,
        'respuesta': None,
        'fecha_respuesta': None,
        'respondida': False,
        'leida': False,
    }


# ===========================================================================
# Tarea 13: Calendario y Cronograma Institucional (ctr_actividad, ctr_cronogramaacademico, ctr_semanacronograma, ctr_cronogramaevaluativo)
# ===========================================================================

def obtener_calendario_completo(persona_id, periodo_id, vista='agenda', fecha_ref=None, subject_id=None):
    """
    Obtiene todas las fechas y eventos del estudiante en un solo lugar:
    1. Entregas y tareas de sus materias (ctr_actividad)
    2. Semanas del cronograma academico del periodo (ctr_semanacronograma)
    3. Hitos del cronograma evaluativo institucional (ctr_cronogramaevaluativo / ctr_detallecronogramaevaluativo)
    4. Lista de materias matriculadas para el filtro por asignatura
    """
    from django.utils import timezone
    now = timezone.now()

    # 1. Obtener lista de materias matriculadas para filtro
    sql_materias = """
        SELECT DISTINCT m.id AS materia_id, ma.id AS materia_asignada_id,
               asig.nombre AS materia_nombre, COALESCE(asig.color, '#0b3b60') AS materia_color
        FROM ctr_estudiante est
        JOIN ctr_matricula mat ON mat.estudiante_id = est.id AND mat.status = TRUE
        JOIN ctr_periodolectivo pl ON pl.id = mat.periodolectivo_id
        JOIN ctr_periodo per ON per.id = pl.periodo_id
        JOIN ctr_nivelmatriculdo nm ON nm.matricula_id = mat.id AND nm.status = TRUE
        JOIN ctr_materiaasignada ma ON ma.nivelmatriculado_id = nm.id AND ma.status = TRUE
        JOIN ctr_materia m ON m.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = m.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        WHERE est.persona_id = %s AND per.id = %s
        ORDER BY asig.nombre ASC
    """
    rows_mat = _query_all(sql_materias, [persona_id, periodo_id])
    materias_filtro = [
        {
            'id': r['materia_id'],
            'materia_asignada_id': r['materia_asignada_id'],
            'nombre': r['materia_nombre'],
            'color': r['materia_color'],
        }
        for r in rows_mat
    ]

    # 2. Obtener actividades de las materias
    sql_act = """
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
    """
    params_act = [persona_id, periodo_id]
    if subject_id:
        sql_act += " AND (m.id = %s OR ma.id = %s)"
        params_act.extend([subject_id, subject_id])

    sql_act += " ORDER BY a.fechafin ASC NULLS LAST, a.id DESC"
    rows_act = _query_all(sql_act, params_act)

    items = []
    actividades_retro = []

    for r in rows_act:
        fechafin_dt = r['fechafin']
        is_expired = bool(r['cerrada']) or (fechafin_dt is not None and fechafin_dt < now)
        entregada = r['entrega_id'] is not None
        vencida = is_expired and not entregada

        fecha_str = None
        hora_str = None
        if fechafin_dt:
            if hasattr(fechafin_dt, 'strftime'):
                fecha_str = fechafin_dt.strftime('%Y-%m-%d')
                hora_str = fechafin_dt.strftime('%H:%M')
            else:
                fecha_str = str(fechafin_dt)[:10]

        act_data = {
            'id': f"act-{r['id']}",
            'actividad_id': r['id'],
            'tipo': 'actividad',
            'titulo': r['nombre'],
            'descripcion': r['descripcion'] or '',
            'fecha': fecha_str,
            'hora': hora_str,
            'fecha_inicio': r['fechainicio'].isoformat() if hasattr(r['fechainicio'], 'isoformat') else str(r['fechainicio']) if r['fechainicio'] else None,
            'fecha_fin': fechafin_dt.isoformat() if hasattr(fechafin_dt, 'isoformat') else str(fechafin_dt) if fechafin_dt else None,
            'materia_id': r['materia_id'],
            'materia_asignada_id': r['materia_asignada_id'],
            'materia_nombre': r['materia_nombre'],
            'materia_color': r['materia_color'],
            'entregada': entregada,
            'vencida': vencida,
            'cerrada': bool(r['cerrada']),
            'ponderacion': float(r['ponderacion']) if r['ponderacion'] is not None else 10.0,
            'nota': float(r['nota']) if r['nota'] is not None else None,
            'tipoentrega': r['tipoentrega'] or 1,
        }
        items.append(act_data)

        retro_item = dict(r)
        retro_item['entregada'] = entregada
        retro_item['vencida'] = vencida
        retro_item['ponderacion'] = act_data['ponderacion']
        retro_item['fechainicio'] = act_data['fecha_inicio']
        retro_item['fechafin'] = act_data['fecha_fin']
        retro_item['fecha_entrega'] = r['fecha_entrega'].isoformat() if hasattr(r['fecha_entrega'], 'isoformat') else str(r['fecha_entrega']) if r['fecha_entrega'] else None
        actividades_retro.append(retro_item)

    # 3. Cronograma Academico Institucional (Semanas)
    cronograma_info = None
    sql_crono = """
        SELECT ca.id, ca.nombre, ca.inicio, ca.fin
        FROM ctr_cronogramaacademico ca
        WHERE ca.periodo_id = %s AND ca.status = TRUE
        ORDER BY ca.id DESC LIMIT 1
    """
    rows_crono = _query_all(sql_crono, [periodo_id])
    if rows_crono:
        c_row = rows_crono[0]
        crono_id = c_row['id']
        sql_semanas = """
            SELECT s.id, s.orden, s.nombre, s.inicio, s.fin
            FROM ctr_semanacronograma s
            WHERE s.cronograma_id = %s AND s.status = TRUE
            ORDER BY s.orden ASC
        """
        rows_sem = _query_all(sql_semanas, [crono_id])
        semanas_list = []
        for s in rows_sem:
            sem_inicio = s['inicio'].strftime('%Y-%m-%d') if hasattr(s['inicio'], 'strftime') else str(s['inicio']) if s['inicio'] else None
            sem_fin = s['fin'].strftime('%Y-%m-%d') if hasattr(s['fin'], 'strftime') else str(s['fin']) if s['fin'] else None
            s_dict = {
                'id': s['id'],
                'orden': s['orden'],
                'nombre': s['nombre'],
                'inicio': sem_inicio,
                'fin': sem_fin,
            }
            semanas_list.append(s_dict)

            if not subject_id and sem_inicio:
                items.append({
                    'id': f"sem-{s['id']}",
                    'tipo': 'institucional',
                    'titulo': f"Inicio {s['nombre']}",
                    'descripcion': f"Periodo de clases semanal ({sem_inicio} al {sem_fin})",
                    'fecha': sem_inicio,
                    'hora': '07:00',
                    'fecha_inicio': sem_inicio,
                    'fecha_fin': sem_fin,
                    'materia_id': None,
                    'materia_asignada_id': None,
                    'materia_nombre': 'Institucional',
                    'materia_color': '#0b3b60',
                    'orden': s['orden'],
                })

        cronograma_info = {
            'id': c_row['id'],
            'nombre': c_row['nombre'],
            'inicio': c_row['inicio'].strftime('%Y-%m-%d') if hasattr(c_row['inicio'], 'strftime') else str(c_row['inicio']) if c_row['inicio'] else None,
            'fin': c_row['fin'].strftime('%Y-%m-%d') if hasattr(c_row['fin'], 'strftime') else str(c_row['fin']) if c_row['fin'] else None,
            'semanas': semanas_list,
        }

    # 4. Cronograma Evaluativo Institucional (Bimestres / Evaluaciones)
    sql_eval = """
        SELECT d.id, d.inicio, d.fin, i.nombre as item_nombre, i.alias as item_alias,
               COALESCE(ime.porcentaje, 0) as porcentaje
        FROM ctr_cronogramaevaluativo ce
        JOIN ctr_detallecronogramaevaluativo d ON d.cronograma_id = ce.id AND d.status = TRUE
        JOIN ctr_itemevaluacion i ON i.id = d.item_id AND i.status = TRUE
        LEFT JOIN ctr_itemmodeloevaluativo ime ON ime.itemevaluacion_id = i.id AND ime.modeloevaluativo_id = ce.modeloevaluativo_id
        WHERE ce.status = TRUE
        ORDER BY d.inicio ASC
    """
    rows_eval = _query_all(sql_eval, [])
    evaluaciones_list = []
    for ev in rows_eval:
        ev_inicio = ev['inicio'].strftime('%Y-%m-%d') if hasattr(ev['inicio'], 'strftime') else str(ev['inicio']) if ev['inicio'] else None
        ev_fin = ev['fin'].strftime('%Y-%m-%d') if hasattr(ev['fin'], 'strftime') else str(ev['fin']) if ev['fin'] else None
        porc = float(ev['porcentaje']) if ev['porcentaje'] is not None else 0.0

        ev_dict = {
            'id': ev['id'],
            'nombre': ev['item_nombre'],
            'alias': ev['item_alias'],
            'inicio': ev_inicio,
            'fin': ev_fin,
            'porcentaje': porc,
        }
        evaluaciones_list.append(ev_dict)

        if not subject_id and ev_inicio:
            items.append({
                'id': f"eval-{ev['id']}",
                'tipo': 'evaluacion',
                'titulo': f"Periodo Evaluativo: {ev['item_nombre']}",
                'descripcion': f"Cierre evaluativo {ev['item_alias']} con ponderacion de {porc}%",
                'fecha': ev_fin or ev_inicio,
                'hora': '23:59',
                'fecha_inicio': ev_inicio,
                'fecha_fin': ev_fin,
                'materia_id': None,
                'materia_asignada_id': None,
                'materia_nombre': 'Evaluación Institucional',
                'materia_color': '#8B5CF6',
                'porcentaje': porc,
            })

    items.sort(key=lambda x: (x['fecha'] or '9999-12-31', x.get('hora') or '00:00'))

    pending_count = len([a for a in items if a.get('tipo') == 'actividad' and not a.get('entregada') and not a.get('vencida')])

    return {
        'items': items,
        'activities': actividades_retro,
        'cronograma_academico': cronograma_info,
        'cronograma_evaluativo': evaluaciones_list,
        'subjects': materias_filtro,
        'total': len(items),
        'pending_count': pending_count,
    }


# ==============================================================================
# TAREA 16: BALCÓN DE SERVICIOS Y TRÁMITES ESTUDIANTILES
# Tablas: ctr_solicitudservicio, ctr_solicitudservicioadjunto,
#         ctr_requerimientodocumento, ctr_documentoestudiante, ctr_tipodocumentoestudiante
# ==============================================================================

def obtener_catalogo_servicios_estudiante(persona_id):
    """
    Retorna el catálogo de certificados institucionales, trámites administrativos
    y materias activas matriculadas por el estudiante para la selección en nueva solicitud.
    """
    certificados = [
        {
            'subtipo': 'NO_ADEUDAR',
            'nombre': 'Certificado de No Adeudar',
            'descripcion': 'Acredita que te encuentras al día en tus obligaciones económicas y pensiones institucionales.',
            'icono': 'shield-checkmark-outline',
            'requiere_materia': False,
            'requiere_fechas': False,
            'requiere_adjunto': False,
        },
        {
            'subtipo': 'CERTIFICADO_ACADEMICO',
            'nombre': 'Certificado Académico (Notas)',
            'descripcion': 'Certificado con el promedio y calificaciones de las asignaturas cursadas en el periodo.',
            'icono': 'school-outline',
            'requiere_materia': False,
            'requiere_fechas': False,
            'requiere_adjunto': False,
        },
        {
            'subtipo': 'MATRICULA',
            'nombre': 'Certificado de Matrícula',
            'descripcion': 'Constancia oficial de matrícula ordinaria en el curso y paralelo asignado.',
            'icono': 'document-text-outline',
            'requiere_materia': False,
            'requiere_fechas': False,
            'requiere_adjunto': False,
        },
        {
            'subtipo': 'CONDUCTA',
            'nombre': 'Certificado de Conducta / Comportamiento',
            'descripcion': 'Certificado disciplinario emitido por Inspección General.',
            'icono': 'ribbon-outline',
            'requiere_materia': False,
            'requiere_fechas': False,
            'requiere_adjunto': False,
        },
        {
            'subtipo': 'ESTUDIO',
            'nombre': 'Certificado de Asistencia y Estudio',
            'descripcion': 'Constancia para trámites laborales de padres, visa o seguro médico.',
            'icono': 'business-outline',
            'requiere_materia': False,
            'requiere_fechas': False,
            'requiere_adjunto': False,
        },
    ]

    tramites = [
        {
            'tipo': 'JUSTIFICACION_FALTA',
            'nombre': 'Justificación de Inasistencia / Faltas',
            'descripcion': 'Solicita justificar ausencias por enfermedad, calamidad doméstica o citas médicas oficiales.',
            'icono': 'calendar-outline',
            'requiere_materia': False,
            'requiere_fechas': True,
            'requiere_adjunto': True,
        },
        {
            'tipo': 'EVALUACION_ATRASADA',
            'nombre': 'Evaluación / Examen Atrasado',
            'descripcion': 'Solicita autorización de Secretaría y Docencia para rendir un examen o evaluación fuera de fecha.',
            'icono': 'create-outline',
            'requiere_materia': True,
            'requiere_fechas': True,
            'requiere_adjunto': True,
        },
        {
            'tipo': 'OTRO_TRAMITE',
            'nombre': 'Solicitud General a Secretaría',
            'descripcion': 'Cualquier otro trámite administrativo, rectificación o consulta formal.',
            'icono': 'mail-outline',
            'requiere_materia': False,
            'requiere_fechas': False,
            'requiere_adjunto': False,
        },
    ]

    sql_materias = """
        SELECT mat.id as materia_id, ma.id as materia_asignada_id,
               COALESCE(asig.nombre, 'Sin nombre') as nombre,
               TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as docente_nombre
        FROM ctr_materiaasignada ma
        JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        JOIN ctr_estudiante e ON e.id = m.estudiante_id AND e.status = TRUE
        JOIN ctr_materia mat ON mat.id = ma.materia_id
        JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE e.persona_id = %s AND ma.status = TRUE
        ORDER BY asig.nombre;
    """
    materias = _query_all(sql_materias, [persona_id])

    return {
        'certificados': certificados,
        'tramites': tramites,
        'materias': materias,
    }


def obtener_solicitudes_servicio_estudiante(persona_id, estado=None, tipo=None):
    """
    Lista las solicitudes realizadas por el estudiante en ctr_solicitudservicio,
    con sus indicadores KPI consolidados.
    """
    from django.conf import settings

    sql_est = "SELECT id FROM ctr_estudiante WHERE persona_id = %s AND status = TRUE LIMIT 1"
    est = _query_one(sql_est, [persona_id])
    if not est:
        return {'solicitudes': [], 'kpi': {'total': 0, 'pendientes': 0, 'en_tramite': 0, 'aprobadas': 0, 'rechazadas': 0}}

    estudiante_id = est['id']
    params = [estudiante_id]
    where_extra = ""
    if estado:
        where_extra += " AND s.estado = %s"
        params.append(estado)
    if tipo:
        where_extra += " AND s.tipo = %s"
        params.append(tipo)

    sql = f"""
        SELECT s.id, s.codigo, s.codigo_verificacion, s.tipo, s.subtipo_certificado,
               s.estado, s.nivel_texto, s.paralelo_texto, s.periodo_texto, s.ciudad,
               s.motivo, s.motivo_detalle, s.falta_desde, s.falta_hasta,
               s.fecha_evaluacion, s.modalidad_evaluacion, s.materia_id,
               COALESCE(asig.nombre, '') as materia_nombre,
               s.documento_solicitud, s.certificado_final, s.fecha_emision_certificado,
               s.observacion_rechazo, s.fecha_atencion, s.fecha_creacion,
               (SELECT COUNT(*) FROM ctr_solicitudservicioadjunto adj WHERE adj.solicitud_id = s.id AND adj.status = TRUE) as total_adjuntos
        FROM ctr_solicitudservicio s
        LEFT JOIN ctr_materia mat ON mat.id = s.materia_id
        LEFT JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        LEFT JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        WHERE s.estudiante_id = %s AND s.status = TRUE {where_extra}
        ORDER BY s.fecha_creacion DESC;
    """
    solicitudes = _query_all(sql, params)

    TIPO_TITULOS = {
        'CERTIFICADO': 'Certificado',
        'JUSTIFICACION_FALTA': 'Justificación de Inasistencia',
        'EVALUACION_ATRASADA': 'Evaluación Atrasada',
        'OTRO_TRAMITE': 'Trámite General',
    }
    SUBTIPO_TITULOS = {
        'NO_ADEUDAR': 'No Adeudar',
        'CERTIFICADO_ACADEMICO': 'Académico (Notas)',
        'MATRICULA': 'Matrícula',
        'CONDUCTA': 'Conducta',
        'ESTUDIO': 'Asistencia y Estudio',
    }

    for item in solicitudes:
        item['tipo_display'] = TIPO_TITULOS.get(item['tipo'], item['tipo'])
        item['subtipo_display'] = SUBTIPO_TITULOS.get(item['subtipo_certificado'], item['subtipo_certificado'])
        cert_final = item.get('certificado_final')
        if cert_final:
            item['certificado_url'] = f"{settings.MEDIA_URL}{cert_final}".replace('//', '/')
            item['tiene_certificado'] = True
        else:
            item['certificado_url'] = None
            item['tiene_certificado'] = False

    sql_kpi = """
        SELECT estado, COUNT(*) as cnt
        FROM ctr_solicitudservicio
        WHERE estudiante_id = %s AND status = TRUE
        GROUP BY estado;
    """
    kpi_rows = _query_all(sql_kpi, [estudiante_id])
    kpi_map = {r['estado']: r['cnt'] for r in kpi_rows}
    kpi = {
        'total': sum(kpi_map.values()),
        'pendientes': kpi_map.get('PENDIENTE', 0) + kpi_map.get('EN_TRAMITE', 0),
        'aprobadas': kpi_map.get('APROBADA', 0) + kpi_map.get('ATENDIDA', 0) + kpi_map.get('FINALIZADA', 0),
        'rechazadas': kpi_map.get('RECHAZADA', 0),
    }

    return {
        'solicitudes': solicitudes,
        'kpi': kpi,
    }


def obtener_detalle_solicitud_servicio(persona_id, solicitud_id):
    """
    Retorna el detalle completo de una solicitud, incluyendo adjuntos y datos de resolución.
    """
    from django.conf import settings

    sql_est = "SELECT id FROM ctr_estudiante WHERE persona_id = %s AND status = TRUE LIMIT 1"
    est = _query_one(sql_est, [persona_id])
    if not est:
        raise LookupError("Estudiante no encontrado.")

    sql = """
        SELECT s.id, s.codigo, s.codigo_verificacion, s.tipo, s.subtipo_certificado,
               s.estado, s.nivel_texto, s.paralelo_texto, s.periodo_texto, s.ciudad,
               s.motivo, s.motivo_detalle, s.falta_desde, s.falta_hasta,
               s.fecha_evaluacion, s.modalidad_evaluacion, s.materia_id,
               COALESCE(asig.nombre, '') as materia_nombre,
               s.documento_solicitud, s.certificado_final, s.fecha_emision_certificado,
               s.observacion_rechazo, s.fecha_atencion, s.fecha_creacion, s.atendida_por_id,
               TRIM(COALESCE(p_at.nombres, '') || ' ' || COALESCE(p_at.apellido_1, '')) as atendida_por_nombre
        FROM ctr_solicitudservicio s
        LEFT JOIN ctr_materia mat ON mat.id = s.materia_id
        LEFT JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        LEFT JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_persona p_at ON p_at.id = s.atendida_por_id
        WHERE s.id = %s AND s.estudiante_id = %s AND s.status = TRUE
        LIMIT 1;
    """
    sol = _query_one(sql, [solicitud_id, est['id']])
    if not sol:
        raise LookupError("La solicitud no existe o no pertenece a tu cuenta.")

    TIPO_TITULOS = {
        'CERTIFICADO': 'Certificado',
        'JUSTIFICACION_FALTA': 'Justificación de Inasistencia',
        'EVALUACION_ATRASADA': 'Evaluación Atrasada',
        'OTRO_TRAMITE': 'Trámite General',
    }
    SUBTIPO_TITULOS = {
        'NO_ADEUDAR': 'No Adeudar',
        'CERTIFICADO_ACADEMICO': 'Académico (Notas)',
        'MATRICULA': 'Matrícula',
        'CONDUCTA': 'Conducta',
        'ESTUDIO': 'Asistencia y Estudio',
    }

    sol['tipo_display'] = TIPO_TITULOS.get(sol['tipo'], sol['tipo'])
    sol['subtipo_display'] = SUBTIPO_TITULOS.get(sol['subtipo_certificado'], sol['subtipo_certificado'])
    cert_final = sol.get('certificado_final')
    if cert_final:
        sol['certificado_url'] = f"{settings.MEDIA_URL}{cert_final}".replace('//', '/')
        sol['tiene_certificado'] = True
    else:
        sol['certificado_url'] = None
        sol['tiene_certificado'] = False

    sql_adj = """
        SELECT id, archivo, nombre_original, tamano, fecha_creacion
        FROM ctr_solicitudservicioadjunto
        WHERE solicitud_id = %s AND status = TRUE
        ORDER BY fecha_creacion ASC;
    """
    adjuntos = _query_all(sql_adj, [solicitud_id])
    for adj in adjuntos:
        adj['archivo_url'] = f"{settings.MEDIA_URL}{adj['archivo']}".replace('//', '/')
    sol['adjuntos'] = adjuntos

    return sol


def crear_solicitud_servicio_estudiante(persona_id, usuario_id, datos, archivos_adjuntos=None):
    """
    Crea una nueva solicitud en ctr_solicitudservicio y almacena sus adjuntos en ctr_solicitudservicioadjunto.
    """
    import os, uuid
    from datetime import datetime
    from django.utils import timezone
    from django.core.files.storage import default_storage
    from django.utils.text import get_valid_filename

    sql_est = """
        SELECT e.id as estudiante_id, p.id as persona_id,
               m.id as matricula_id, COALESCE(n.nombre, 'Sin nivel') as nivel,
               COALESCE(par.nombre, 'A') as paralelo,
               COALESCE(per.nombre, 'Periodo Lectivo') as periodo_nombre
        FROM ctr_estudiante e
        JOIN ctr_persona p ON p.id = e.persona_id
        LEFT JOIN ctr_matricula m ON m.estudiante_id = e.id AND m.status = TRUE
        LEFT JOIN ctr_nivel n ON n.id = m.nivel_id
        LEFT JOIN ctr_paralelo par ON par.id = m.paralelo_id
        LEFT JOIN ctr_periodolectivo pl ON pl.id = m.periodolectivo_id
        LEFT JOIN ctr_periodo per ON per.id = pl.periodo_id
        WHERE p.id = %s AND e.status = TRUE
        LIMIT 1;
    """
    est = _query_one(sql_est, [persona_id])
    if not est:
        raise LookupError("Estudiante no encontrado.")

    estudiante_id = est['estudiante_id']
    matricula_id = est['matricula_id']
    nivel_texto = est['nivel']
    paralelo_texto = est['paralelo']
    periodo_texto = est['periodo_nombre']
    regimen_texto = 'ORDINARIO'
    ciudad = 'Guayaquil'

    anho = timezone.now().year
    with connection.cursor() as c:
        c.execute("SELECT COUNT(*) FROM ctr_solicitudservicio WHERE codigo LIKE %s;", [f"SOL-{anho}-%"])
        total_anho = c.fetchone()[0]
    codigo = f"SOL-{anho}-{total_anho + 1:05d}"
    codigo_verif = str(uuid.uuid4())
    now = timezone.now()

    tipo = (datos.get('tipo', 'CERTIFICADO') or 'CERTIFICADO')[:30]
    subtipo = (datos.get('subtipo_certificado', '') or '')[:40]
    materia_id = datos.get('materia_id')
    motivo_raw = (datos.get('motivo', '') or '').strip()
    motivo_detalle = (datos.get('motivo_detalle', '') or motivo_raw).strip()
    motivo = (motivo_raw[:30] if motivo_raw else (motivo_detalle[:30] if motivo_detalle else 'SOLICITUD')).strip()
    falta_desde = datos.get('falta_desde') or None
    falta_hasta = datos.get('falta_hasta') or None
    fecha_evaluacion = datos.get('fecha_evaluacion') or None
    modalidad_evaluacion = datos.get('modalidad_evaluacion', '')

    sql_insert = """
        INSERT INTO ctr_solicitudservicio (
            fecha_creacion, fecha_modificacion, status, codigo, codigo_verificacion,
            tipo, subtipo_certificado, estado, nivel_texto, paralelo_texto,
            regimen_texto, periodo_texto, ciudad, modalidad_evaluacion,
            fecha_evaluacion, motivo, motivo_detalle, falta_desde, falta_hasta,
            observacion_rechazo, estudiante_id, materia_id, matricula_id,
            usuario_creacion_id
        ) VALUES (
            %s, %s, TRUE, %s, %s,
            %s, %s, 'PENDIENTE', %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            '', %s, %s, %s,
            %s
        ) RETURNING id;
    """
    params_insert = [
        now, now, codigo, codigo_verif,
        tipo, subtipo, nivel_texto, paralelo_texto,
        regimen_texto, periodo_texto, ciudad, modalidad_evaluacion,
        fecha_evaluacion, motivo, motivo_detalle, falta_desde, falta_hasta,
        estudiante_id, materia_id, matricula_id,
        usuario_id
    ]

    with connection.cursor() as c:
        c.execute(sql_insert, params_insert)
        solicitud_id = c.fetchone()[0]

    if archivos_adjuntos:
        for f in archivos_adjuntos:
            nombre_limpio = get_valid_filename(f.name)
            timestamp = int(datetime.now().timestamp())
            subruta = os.path.join('balcon', 'adjuntos', f"{persona_id}_{timestamp}_{nombre_limpio}").replace('\\', '/')
            ruta_guardada = default_storage.save(subruta, f)
            tamano = f.size if hasattr(f, 'size') else 0

            sql_adj = """
                INSERT INTO ctr_solicitudservicioadjunto (
                    fecha_creacion, fecha_modificacion, status, archivo, nombre_original,
                    tamano, solicitud_id, subido_por_id, usuario_creacion_id
                ) VALUES (
                    %s, %s, TRUE, %s, %s,
                    %s, %s, %s, %s
                );
            """
            with connection.cursor() as c:
                c.execute(sql_adj, [now, now, ruta_guardada, f.name, tamano, solicitud_id, persona_id, usuario_id])

    return obtener_detalle_solicitud_servicio(persona_id, solicitud_id)


def obtener_documentos_y_requerimientos_estudiante(persona_id):
    """
    Consulta los requerimientos documentales asignados al estudiante (ctr_requerimientodocumento),
    el estado de entrega contra ctr_documentoestudiante y el catálogo completo de tipos.
    """
    from django.conf import settings

    sql_est = "SELECT id FROM ctr_estudiante WHERE persona_id = %s AND status = TRUE LIMIT 1"
    est = _query_one(sql_est, [persona_id])
    if not est:
        return {'requerimientos': [], 'documentos_subidos': [], 'tipos_documentos': [], 'resumen': {}}

    estudiante_id = est['id']

    sql_req = """
        SELECT r.id as requerimiento_id, r.alcance, r.fecha_limite, r.observacion as observacion_requerimiento,
               r.tipo_id, t.nombre as tipo_nombre, t.descripcion as tipo_descripcion, t.orden,
               doc.id as documento_id, doc.archivo, doc.nombre_original, doc.estado,
               doc.fecha_carga, doc.observacion as observacion_documento
        FROM ctr_requerimientodocumento r
        JOIN ctr_tipodocumentoestudiante t ON t.id = r.tipo_id AND t.status = TRUE
        LEFT JOIN LATERAL (
            SELECT id, archivo, nombre_original, estado, fecha_carga, observacion
            FROM ctr_documentoestudiante d
            WHERE d.tipo_id = r.tipo_id AND d.estudiante_id = %s AND d.status = TRUE
            ORDER BY d.fecha_carga DESC LIMIT 1
        ) doc ON TRUE
        WHERE (r.estudiante_id = %s OR r.alcance = 'TODOS') AND r.activo = TRUE AND r.status = TRUE
        ORDER BY t.orden, r.fecha_limite;
    """
    reqs = _query_all(sql_req, [estudiante_id, estudiante_id])
    for r in reqs:
        if r['archivo']:
            r['archivo_url'] = f"{settings.MEDIA_URL}{r['archivo']}".replace('//', '/')
        else:
            r['archivo_url'] = None
        if not r['documento_id']:
            r['estado_entrega'] = 'PENDIENTE'
        else:
            r['estado_entrega'] = r['estado'] or 'CARGADO'

    sql_docs = """
        SELECT doc.id, doc.archivo, doc.nombre_original, doc.tamano, doc.estado,
               doc.cargado_por, doc.fecha_carga, doc.observacion, doc.fecha_revision,
               t.id as tipo_id, t.nombre as tipo_nombre, t.descripcion as tipo_descripcion
        FROM ctr_documentoestudiante doc
        JOIN ctr_tipodocumentoestudiante t ON t.id = doc.tipo_id
        WHERE doc.estudiante_id = %s AND doc.status = TRUE
        ORDER BY doc.fecha_carga DESC;
    """
    docs = _query_all(sql_docs, [estudiante_id])
    for d in docs:
        if d['archivo']:
            d['archivo_url'] = f"{settings.MEDIA_URL}{d['archivo']}".replace('//', '/')
        else:
            d['archivo_url'] = None

    sql_tipos = """
        SELECT id, nombre, descripcion, orden
        FROM ctr_tipodocumentoestudiante
        WHERE status = TRUE AND activo = TRUE
        ORDER BY orden, nombre;
    """
    tipos = _query_all(sql_tipos)

    total_req = len(reqs)
    entregados = len([r for r in reqs if r['documento_id']])
    pendientes = total_req - entregados
    aprobados = len([r for r in reqs if r['estado_entrega'] == 'APROBADO'])
    rechazados = len([r for r in reqs if r['estado_entrega'] == 'RECHAZADO'])

    return {
        'requerimientos': reqs,
        'documentos_subidos': docs,
        'tipos_documentos': tipos,
        'resumen': {
            'total_requeridos': total_req,
            'entregados': entregados,
            'pendientes': pendientes,
            'aprobados': aprobados,
            'rechazados': rechazados,
        }
    }


def subir_documento_estudiante(persona_id, usuario_id, tipo_id, archivo_file, observacion=''):
    """
    Registra un documento subido por el estudiante en ctr_documentoestudiante
    para atender requerimientos de Secretaría.
    """
    import os
    from datetime import datetime
    from django.utils import timezone
    from django.conf import settings
    from django.core.files.storage import default_storage
    from django.utils.text import get_valid_filename

    sql_est = "SELECT id FROM ctr_estudiante WHERE persona_id = %s AND status = TRUE LIMIT 1"
    est = _query_one(sql_est, [persona_id])
    if not est:
        raise LookupError("Estudiante no encontrado.")

    estudiante_id = est['id']
    tipo = _query_one("SELECT id, nombre FROM ctr_tipodocumentoestudiante WHERE id = %s AND status = TRUE", [tipo_id])
    if not tipo:
        raise LookupError("El tipo de documento especificado no existe.")

    nombre_limpio = get_valid_filename(archivo_file.name)
    timestamp = int(datetime.now().timestamp())
    subruta = os.path.join('documentos_estudiante', f"est_{estudiante_id}_tipo_{tipo_id}_{timestamp}_{nombre_limpio}").replace('\\', '/')
    ruta_guardada = default_storage.save(subruta, archivo_file)
    tamano = archivo_file.size if hasattr(archivo_file, 'size') else 0
    now = timezone.now()

    sql_ins = """
        INSERT INTO ctr_documentoestudiante (
            fecha_creacion, fecha_modificacion, status, archivo, nombre_original,
            tamano, estado, cargado_por, fecha_carga, observacion,
            estudiante_id, tipo_id, subido_por_id, usuario_creacion_id
        ) VALUES (
            %s, %s, TRUE, %s, %s,
            %s, 'PENDIENTE', 'ESTUDIANTE', %s, %s,
            %s, %s, %s, %s
        ) RETURNING id;
    """
    with connection.cursor() as c:
        c.execute(sql_ins, [
            now, now, ruta_guardada, archivo_file.name,
            tamano, now, observacion,
            estudiante_id, tipo_id, persona_id, usuario_id
        ])
        doc_id = c.fetchone()[0]

    return {
        'id': doc_id,
        'tipo_id': tipo_id,
        'tipo_nombre': tipo['nombre'],
        'nombre_original': archivo_file.name,
        'tamano': tamano,
        'estado': 'PENDIENTE',
        'cargado_por': 'ESTUDIANTE',
        'fecha_carga': now.isoformat(),
        'observacion': observacion,
        'archivo_url': f"{settings.MEDIA_URL}{ruta_guardada}".replace('//', '/'),
    }

