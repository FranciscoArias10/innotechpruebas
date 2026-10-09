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
            COALESCE(asig.color, '#0073bc') as color,
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
            cl.inicio, cl.fin,
            asig.nombre as materia,
            COALESCE(asig.color, '#0073bc') as color,
            COALESCE(au.nombre, 'Aula Virtual') as aula,
            COALESCE(par.nombre, 'A') as paralelo,
            TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as profesor,
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
        ORDER BY cl.dia ASC, cl.inicio ASC
    """
    rows = _query_all(sql, [persona_id, periodo_id])

    nombres_dias = {
        0: 'LUNES', 1: 'MARTES', 2: 'MIERCOLES', 3: 'JUEVES', 4: 'VIERNES', 5: 'SABADO', 6: 'DOMINGO',
        1: 'LUNES', 2: 'MARTES', 3: 'MIERCOLES', 4: 'JUEVES', 5: 'VIERNES', 6: 'SABADO', 7: 'DOMINGO'
    }

    # Agrupar por turnos y dias
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

        dia_num = r['dia']
        dia_nombre = nombres_dias.get(dia_num, 'LUNES')
        if dia_num not in turnos_dict[t_id]['dias_map']:
            turnos_dict[t_id]['dias_map'][dia_num] = {
                'indice': dia_num,
                'nombre': dia_nombre,
                'clases': []
            }

        turnos_dict[t_id]['dias_map'][dia_num]['clases'].append({
            'nombre': r['materia'],
            'paralelo': r['paralelo'],
            'aula': r['aula'],
            'profesor': r['profesor'] or 'Docente Asignado',
            'inicio': str(r['inicio']),
            'fin': str(r['fin']),
            'color': r['color']
        })

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

    # Si no hay turnos con clases, entregar grilla base de 5 dias vacios
    if not turnos_salida:
        turnos_salida = [{
            'id': 1,
            'nombre': 'MATUTINO',
            'nombre_corto': 'MAT',
            'aplica_asistencia': True,
            'dias': []
        }]

    dias_visibles = [
        {'indice': 1, 'nombre': 'LUNES', 'clases': []},
        {'indice': 2, 'nombre': 'MARTES', 'clases': []},
        {'indice': 3, 'nombre': 'MIERCOLES', 'clases': []},
        {'indice': 4, 'nombre': 'JUEVES', 'clases': []},
        {'indice': 5, 'nombre': 'VIERNES', 'clases': []},
    ]

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
               COALESCE(asig.color, '#0073bc') as color,
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
