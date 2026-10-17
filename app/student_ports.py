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

    from django.db import connection
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
    - Docentes de las asignaturas que cursa el estudiante.
    - Compañeros de aula (mismo nivel, paralelo y periodo).
    """
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
                cursor.execute("""
                    INSERT INTO chat_message_attachment (message_id, file, original_filename, mime_type, size_bytes, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, [
                    msg_id,
                    adj.get('url', ''),
                    adj.get('name', 'adjunto'),
                    adj.get('mime_type', 'application/octet-stream'),
                    adj.get('size', 0),
                    json.dumps(meta)
                ])
                adj_id = cursor.fetchone()[0]
                adj_resultado.append({
                    'id': adj_id,
                    'url': adj.get('url', ''),
                    'name': adj.get('name', ''),
                    'mime_type': adj.get('mime_type', 'application/octet-stream'),
                    'size': adj.get('size', 0),
                })

        # Actualizar conversación
        vista_previa = (contenido or 'Archivo adjunto')[:90]
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
            SELECT p.id as persona_id, p.nombres, p.apellido_1, u.id as usuario_id
            FROM chat_conversation_participant ccp
            JOIN ctr_persona p ON p.id = ccp.persona_id
            LEFT JOIN auth_user u ON (u.username = p.identificacion OR u.email = p.correo)
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

