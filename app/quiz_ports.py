# -*- coding: utf-8 -*-
"""
Puertos de logica de negocio y base de datos para la Tarea 11: Cuestionarios y Evaluaciones en Linea.
Maneja:
- Detalle del cuestionario (tiempos, intentos permitidos, historial de intentos, estado de intento activo)
- Apertura o retoma de intento (openAttempt) con control de expiracion del servidor
- Carga de preguntas del intento (loadQuestions) con respuestas previamente guardadas
- Guardado en vivo de respuestas (saveAnswers) a prueba de caidas de conexion
- Finalizacion y calificacion automatica (finishAttempt)
- Revision de intento (viewAttempt) con desglose, retroalimentacion y respuestas correctas
"""
import datetime
from decimal import Decimal
from django.db import connection
from django.utils import timezone


def _query_all(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        desc = cursor.description
        if not desc:
            return []
        cols = [col[0] for col in desc]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _query_one(sql, params=None):
    rows = _query_all(sql, params)
    return rows[0] if rows else None


def obtener_detalle_cuestionario(persona_id, periodo_id, cuestionario_id):
    """
    Retorna el detalle del cuestionario, parametros, historial de intentos del estudiante
    y si existe un intento activo en curso para reanudarlo inmediatamente.
    """
    sql_cuestionario = """
        SELECT 
            c.id,
            c.actividad_id,
            COALESCE(c."limit", 30) as tiempo_limite,
            COALESCE(c.unidad_tiempo, 1) as unidad_tiempo,
            COALESCE(c.usa_limit_tiempo, TRUE) as usa_limit_tiempo,
            COALESCE(c.num_intento, 1) as num_intento,
            COALESCE(c.notamaxima, 10.00) as notamaxima,
            COALESCE(c.metodo_navegacion, 'libre') as metodo_navegacion,
            COALESCE(c.preguntas_aleatorias, FALSE) as preguntas_aleatorias,
            a.nombre as titulo,
            COALESCE(a.descripcion, '') as instrucciones,
            a.fechainicio,
            a.fechafin,
            COALESCE(a.cerrada, FALSE) as cerrada,
            COALESCE(asig.nombre, 'Asignatura') as materia_nombre,
            COALESCE(NULLIF(asig.color, ''), '#0073bc') as materia_color,
            mat.id as materia_id,
            ma.id as materia_asignada_id,
            TRIM(COALESCE(prof_p.nombres, '') || ' ' || COALESCE(prof_p.apellido_1, '')) as docente_nombre
        FROM ctr_cuestionario c
        JOIN ctr_actividad a ON c.actividad_id = a.id
        LEFT JOIN ctr_planificacionsemanalcontenido psc ON a.planificacionsemanal_id = psc.id
        LEFT JOIN ctr_materia mat ON psc.materia_id = mat.id
        LEFT JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        LEFT JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        LEFT JOIN ctr_materiaasignada ma ON ma.materia_id = mat.id AND ma.status = TRUE
        LEFT JOIN ctr_nivelmatriculdo nm ON nm.id = ma.nivelmatriculado_id AND nm.status = TRUE
        LEFT JOIN ctr_matricula m ON m.id = nm.matricula_id AND m.status = TRUE
        LEFT JOIN ctr_estudiante e ON e.id = m.estudiante_id AND e.persona_id = %s
        LEFT JOIN ctr_profesormateria pm ON pm.materia_id = mat.id AND pm.status = TRUE
        LEFT JOIN ctr_profesor prof ON prof.id = pm.profesor_id
        LEFT JOIN ctr_persona prof_p ON prof_p.id = prof.persona_id
        WHERE c.id = %s AND c.status = TRUE
        LIMIT 1
    """
    row = _query_one(sql_cuestionario, [persona_id, cuestionario_id])
    if not row:
        sql_fallback = """
            SELECT 
                c.id, c.actividad_id,
                COALESCE(c."limit", 30) as tiempo_limite,
                COALESCE(c.unidad_tiempo, 1) as unidad_tiempo,
                COALESCE(c.usa_limit_tiempo, TRUE) as usa_limit_tiempo,
                COALESCE(c.num_intento, 1) as num_intento,
                COALESCE(c.notamaxima, 10.00) as notamaxima,
                COALESCE(c.metodo_navegacion, 'libre') as metodo_navegacion,
                COALESCE(c.preguntas_aleatorias, FALSE) as preguntas_aleatorias,
                a.nombre as titulo,
                COALESCE(a.descripcion, '') as instrucciones,
                a.fechainicio, a.fechafin,
                COALESCE(a.cerrada, FALSE) as cerrada,
                'Evaluacion Institucional' as materia_nombre,
                '#0073bc' as materia_color,
                1 as materia_id,
                1 as materia_asignada_id,
                'Docente UNIEBEC' as docente_nombre
            FROM ctr_cuestionario c
            JOIN ctr_actividad a ON c.actividad_id = a.id
            WHERE c.id = %s AND c.status = TRUE
            LIMIT 1
        """
        row = _query_one(sql_fallback, [cuestionario_id])
        if not row:
            raise LookupError("Cuestionario no encontrado.")

    est = _query_one("SELECT id FROM ctr_estudiante WHERE persona_id = %s AND status = TRUE LIMIT 1", [persona_id])
    estudiante_id = est['id'] if est else None

    cnt = _query_one("SELECT count(*) as total FROM ctr_cuestionariopregunta WHERE cuestionario_id = %s AND status = TRUE", [cuestionario_id])
    total_preguntas = cnt['total'] if cnt else 0

    tiempo_minutos = int(row['tiempo_limite']) if row['tiempo_limite'] and row['tiempo_limite'] > 0 else 30
    tiempo_segundos_total = tiempo_minutos * 60

    intentos = []
    intento_activo = None
    if estudiante_id:
        sql_intentos = """
            SELECT 
                id,
                COALESCE(estado, 'finalizado') as estado,
                fecha_inicio,
                fecha_fin,
                tiempo_utilizado,
                puntuacion_total,
                nota_final,
                respuestas_correctas,
                respuestas_incorrectas,
                es_calificado
            FROM ctr_intentocuestionario
            WHERE cuestionario_id = %s AND estudiante_id = %s AND status = TRUE
            ORDER BY id ASC
        """
        raw_intentos = _query_all(sql_intentos, [cuestionario_id, estudiante_id])
        now = timezone.now()

        for idx, it in enumerate(raw_intentos):
            num = idx + 1
            f_ini = it['fecha_inicio']
            f_fin = it['fecha_fin']
            st = it['estado']

            if st in ('iniciado', 'en_curso'):
                segundos_transcurridos = (now - f_ini).total_seconds() if f_ini else 0
                tiempo_restante = max(0, int(tiempo_segundos_total - segundos_transcurridos))

                if tiempo_restante <= 0:
                    terminar_intento_cuestionario(persona_id, it['id'])
                    it['estado'] = 'finalizado'
                    it['tiempo_utilizado'] = tiempo_segundos_total
                else:
                    intento_activo = {
                        'id': it['id'],
                        'numero_intento': num,
                        'tiempo_restante_segundos': tiempo_restante,
                        'fecha_fin_calculada': (f_ini + datetime.timedelta(seconds=tiempo_segundos_total)).isoformat(),
                        'fecha_inicio': f_ini.isoformat() if f_ini else None,
                    }

            intentos.append({
                'id': it['id'],
                'numero_intento': num,
                'estado': it['estado'],
                'fecha_inicio': f_ini.isoformat() if f_ini else None,
                'fecha_fin': f_fin.isoformat() if f_fin else None,
                'tiempo_utilizado': it['tiempo_utilizado'],
                'puntuacion_total': float(it['puntuacion_total'] or 0),
                'nota_final': float(it['nota_final'] or 0),
                'respuestas_correctas': it['respuestas_correctas'] or 0,
                'respuestas_incorrectas': it['respuestas_incorrectas'] or 0,
                'es_calificado': bool(it['es_calificado']),
            })

    intentos_permitidos = int(row['num_intento']) if row['num_intento'] is not None else 1
    intentos_realizados = len([i for i in intentos if i['estado'] == 'finalizado'])
    intentos_restantes = max(0, intentos_permitidos - intentos_realizados) if intentos_permitidos > 0 else 999

    now_tz = timezone.now()
    dentro_de_plazo = True
    if row['fechafin'] and now_tz > row['fechafin']:
        dentro_de_plazo = False

    puede_iniciar = (intentos_restantes > 0 or intento_activo is not None) and dentro_de_plazo and not row['cerrada']

    return {
        'id': row['id'],
        'actividad_id': row['actividad_id'],
        'titulo': row['titulo'],
        'instrucciones': row['instrucciones'],
        'materia_id': row['materia_id'],
        'materia_asignada_id': row['materia_asignada_id'],
        'materia_nombre': row['materia_nombre'],
        'materia_color': row['materia_color'],
        'docente_nombre': row['docente_nombre'],
        'fechainicio': row['fechainicio'].isoformat() if row['fechainicio'] else None,
        'fechafin': row['fechafin'].isoformat() if row['fechafin'] else None,
        'cerrada': bool(row['cerrada']),
        'tiempo_limite_minutos': tiempo_minutos,
        'tiempo_limite_segundos': tiempo_segundos_total,
        'intentos_permitidos': intentos_permitidos,
        'intentos_restantes': intentos_restantes,
        'notamaxima': float(row['notamaxima']),
        'total_preguntas': total_preguntas,
        'metodo_navegacion': row['metodo_navegacion'],
        'intentos': intentos,
        'intento_activo': intento_activo,
        'puede_iniciar': puede_iniciar,
    }


def iniciar_o_retomar_intento_cuestionario(persona_id, periodo_id, cuestionario_id):
    """
    Inicia un nuevo intento de evaluacion o retoma el intento que ya estaba en curso.
    Controla el tiempo estrictamente con el reloj del servidor.
    """
    est = _query_one("SELECT id FROM ctr_estudiante WHERE persona_id = %s AND status = TRUE LIMIT 1", [persona_id])
    if not est:
        raise LookupError("Estudiante no matriculado o inactivo.")
    estudiante_id = est['id']

    cuestionario = _query_one('SELECT id, "limit", num_intento, notamaxima FROM ctr_cuestionario WHERE id = %s AND status = TRUE', [cuestionario_id])
    if not cuestionario:
        raise LookupError("Cuestionario no encontrado.")

    tiempo_minutos = int(cuestionario['limit']) if cuestionario['limit'] and cuestionario['limit'] > 0 else 30
    tiempo_segundos_total = tiempo_minutos * 60
    now = timezone.now()

    intento_existente = _query_one("""
        SELECT id, fecha_inicio, estado 
        FROM ctr_intentocuestionario 
        WHERE cuestionario_id = %s AND estudiante_id = %s AND estado IN ('iniciado', 'en_curso') AND status = TRUE
        ORDER BY id DESC LIMIT 1
    """, [cuestionario_id, estudiante_id])

    if intento_existente:
        f_ini = intento_existente['fecha_inicio']
        segundos_transcurridos = (now - f_ini).total_seconds() if f_ini else 0
        tiempo_restante = max(0, int(tiempo_segundos_total - segundos_transcurridos))

        if tiempo_restante > 0:
            return {
                'intento_id': intento_existente['id'],
                'cuestionario_id': cuestionario_id,
                'estado': 'en_curso',
                'reanudado': True,
                'tiempo_restante_segundos': tiempo_restante,
                'tiempo_limite_segundos': tiempo_segundos_total,
                'fecha_fin_calculada': (f_ini + datetime.timedelta(seconds=tiempo_segundos_total)).isoformat(),
            }
        else:
            terminar_intento_cuestionario(persona_id, intento_existente['id'])

    intentos_permitidos = int(cuestionario['num_intento']) if cuestionario['num_intento'] is not None else 1
    finalizados = _query_one("""
        SELECT count(*) as total 
        FROM ctr_intentocuestionario 
        WHERE cuestionario_id = %s AND estudiante_id = %s AND estado = 'finalizado' AND status = TRUE
    """, [cuestionario_id, estudiante_id])
    total_fin = finalizados['total'] if finalizados else 0

    if intentos_permitidos > 0 and total_fin >= intentos_permitidos:
        raise PermissionError("Has alcanzado el numero maximo de intentos permitidos para esta evaluacion.")

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ctr_intentocuestionario 
            (fecha_creacion, status, estado, fecha_inicio, tiempo_utilizado, puntuacion_total, nota_final, respuestas_correctas, respuestas_incorrectas, cuestionario_id, estudiante_id, es_calificado)
            VALUES (NOW(), TRUE, 'en_curso', NOW(), 0, 0, 0, 0, 0, %s, %s, FALSE)
            RETURNING id, fecha_inicio
        """, [cuestionario_id, estudiante_id])
        res = cursor.fetchone()
        nuevo_id, f_ini = res[0], res[1]

    fecha_fin_calc = f_ini + datetime.timedelta(seconds=tiempo_segundos_total)

    return {
        'intento_id': nuevo_id,
        'cuestionario_id': cuestionario_id,
        'estado': 'en_curso',
        'reanudado': False,
        'tiempo_restante_segundos': tiempo_segundos_total,
        'tiempo_limite_segundos': tiempo_segundos_total,
        'fecha_fin_calculada': fecha_fin_calc.isoformat(),
    }


def obtener_preguntas_intento(persona_id, intento_id):
    """
    Retorna la lista de preguntas para rendir el intento, con sus opciones de respuesta
    y cualquier respuesta previamente guardada.
    """
    intento = _query_one("""
        SELECT i.id, i.cuestionario_id, i.estado, i.fecha_inicio, c."limit"
        FROM ctr_intentocuestionario i
        JOIN ctr_cuestionario c ON i.cuestionario_id = c.id
        JOIN ctr_estudiante e ON i.estudiante_id = e.id
        WHERE i.id = %s AND e.persona_id = %s AND i.status = TRUE
    """, [intento_id, persona_id])
    if not intento:
        raise LookupError("Intento de evaluacion no encontrado.")

    c_id = intento['cuestionario_id']
    tiempo_minutos = int(intento['limit']) if intento['limit'] and intento['limit'] > 0 else 30
    tiempo_segundos_total = tiempo_minutos * 60
    now = timezone.now()
    f_ini = intento['fecha_inicio']
    segundos_transcurridos = (now - f_ini).total_seconds() if f_ini else 0
    tiempo_restante = max(0, int(tiempo_segundos_total - segundos_transcurridos))

    sql_preguntas = """
        SELECT 
            cp.id as item_id,
            cp.orden,
            cp.nota as puntuacion,
            p.id as pregunta_id,
            p.nombre as titulo_pregunta,
            p.enunciado,
            tp.tipo as tipo_nombre
        FROM ctr_cuestionariopregunta cp
        JOIN ctr_pregunta p ON cp.pregunta_id = p.id
        LEFT JOIN ctr_tipopregunta tp ON p.tipo_id = tp.id
        WHERE cp.cuestionario_id = %s AND cp.status = TRUE
        ORDER BY cp.orden ASC, cp.id ASC
    """
    preguntas_raw = _query_all(sql_preguntas, [c_id])

    sql_respuestas = """
        SELECT 
            r.id as respuesta_id,
            r.pregunta_cuestionario_id as pregunta_id,
            r.respuesta_verdadero_falso,
            r.respuesta_corta
        FROM ctr_respuestaintento r
        WHERE r.intento_id = %s AND r.status = TRUE
    """
    respuestas_guardadas_raw = _query_all(sql_respuestas, [intento_id])
    respuestas_map = {r['pregunta_id']: r for r in respuestas_guardadas_raw}

    sql_opciones_sel = """
        SELECT ro.respuestaintento_id, ro.origenrespuestaopcion_id as opcion_id
        FROM ctr_respuestaintento_opciones_seleccionadas ro
        JOIN ctr_respuestaintento r ON r.id = ro.respuestaintento_id
        WHERE r.intento_id = %s
    """
    opciones_sel_raw = _query_all(sql_opciones_sel, [intento_id])
    opciones_sel_map = {}
    for o in opciones_sel_raw:
        opciones_sel_map.setdefault(o['respuestaintento_id'], []).append(o['opcion_id'])

    preguntas_lista = []
    for idx, p in enumerate(preguntas_raw):
        p_id = p['pregunta_id']

        tipo_raw = (p['tipo_nombre'] or '').lower()
        if 'verdadero' in tipo_raw or 'falso' in tipo_raw:
            tipo_normalizado = 'verdadero_falso'
        elif 'multiple' in tipo_raw:
            tipo_normalizado = 'opcion_multiple_multiple'
        elif 'texto' in tipo_raw or 'corta' in tipo_raw:
            tipo_normalizado = 'texto'
        else:
            tipo_normalizado = 'opcion_multiple_unica'

        sql_opciones = """
            SELECT id, respuesta
            FROM ctr_respuestaopcion
            WHERE pregunta_id = %s AND status = TRUE
            ORDER BY id ASC
        """
        opciones_raw = _query_all(sql_opciones, [p_id])

        resp_guardada = respuestas_map.get(p_id)
        seleccionadas = []
        texto_guardado = ''
        vf_guardado = None

        if resp_guardada:
            import json
            r_id = resp_guardada['respuesta_id']
            seleccionadas = opciones_sel_map.get(r_id, [])
            texto_guardado = resp_guardada['respuesta_corta'] or ''
            if not seleccionadas and texto_guardado:
                try:
                    parsed = json.loads(texto_guardado)
                    if isinstance(parsed, list):
                        seleccionadas = parsed
                    elif isinstance(parsed, int):
                        seleccionadas = [parsed]
                except Exception:
                    pass
            vf_guardado = resp_guardada['respuesta_verdadero_falso']

        preguntas_lista.append({
            'id': p_id,
            'item_id': p['item_id'],
            'pregunta_id': p_id,
            'numero': idx + 1,
            'orden': p['orden'],
            'titulo': p['titulo_pregunta'],
            'enunciado': p['enunciado'],
            'puntuacion': float(p['puntuacion'] or 1.0),
            'tipo': tipo_normalizado,
            'opciones': [{'id': o['id'], 'texto': o['respuesta']} for o in opciones_raw],
            'respuesta_guardada': {
                'opcion_ids': seleccionadas,
                'texto': texto_guardado,
                'verdadero_falso': vf_guardado,
                'respondida': bool(seleccionadas or texto_guardado or vf_guardado is not None),
            }
        })

    return {
        'intento_id': intento_id,
        'cuestionario_id': c_id,
        'estado': intento['estado'],
        'tiempo_restante_segundos': tiempo_restante,
        'total_preguntas': len(preguntas_lista),
        'preguntas': preguntas_lista,
    }


def guardar_respuesta_intento(persona_id, intento_id, pregunta_id, opcion_ids=None, texto=None, verdadero_falso=None):
    """
    Guarda de forma atomica y persistente la respuesta de una pregunta.
    Almacena tanto en la estructura relacional como en respuesta_corta serializada
    para maxima resiliencia ante restricciones de FKs historicas.
    """
    import json
    intento = _query_one("""
        SELECT i.id, i.cuestionario_id, i.estado, i.fecha_inicio, c."limit"
        FROM ctr_intentocuestionario i
        JOIN ctr_cuestionario c ON i.cuestionario_id = c.id
        JOIN ctr_estudiante e ON i.estudiante_id = e.id
        WHERE i.id = %s AND e.persona_id = %s AND i.status = TRUE
    """, [intento_id, persona_id])
    if not intento or intento['estado'] == 'finalizado':
        raise PermissionError("El intento ya no se encuentra en curso.")

    c_id = intento['cuestionario_id']
    cp = _query_one("SELECT id FROM ctr_cuestionariopregunta WHERE cuestionario_id = %s AND pregunta_id = %s AND status = TRUE", [c_id, pregunta_id])
    cp_id = cp['id'] if cp else pregunta_id

    existente = _query_one("""
        SELECT id FROM ctr_respuestaintento 
        WHERE intento_id = %s AND (pregunta_cuestionario_id = %s OR pregunta_cuestionario_id = %s) AND status = TRUE
    """, [intento_id, cp_id, pregunta_id])

    texto_guardar = texto if texto else (json.dumps(opcion_ids) if opcion_ids else '')

    with connection.cursor() as cursor:
        if existente:
            r_id = existente['id']
            cursor.execute("""
                UPDATE ctr_respuestaintento
                SET respuesta_verdadero_falso = %s,
                    respuesta_corta = %s,
                    fecha_modificacion = NOW()
                WHERE id = %s
            """, [verdadero_falso, texto_guardar, r_id])
        else:
            cursor.execute("""
                INSERT INTO ctr_respuestaintento
                (fecha_creacion, status, orden, respuesta_verdadero_falso, respuesta_corta, puntuacion_obtenida, es_correcta, tiempo_respuesta, intento_id, pregunta_cuestionario_id)
                VALUES (NOW(), TRUE, 1, %s, %s, 0, FALSE, 0, %s, %s)
                RETURNING id
            """, [verdadero_falso, texto_guardar, intento_id, cp_id])
            r_id = cursor.fetchone()[0]

        try:
            cursor.execute("DELETE FROM ctr_respuestaintento_opciones_seleccionadas WHERE respuestaintento_id = %s", [r_id])
            if opcion_ids:
                for op_id in opcion_ids:
                    cursor.execute("""
                        INSERT INTO ctr_respuestaintento_opciones_seleccionadas
                        (respuestaintento_id, origenrespuestaopcion_id)
                        VALUES (%s, %s)
                    """, [r_id, op_id])
        except Exception:
            pass

    return {
        'guardado': True,
        'pregunta_id': pregunta_id,
        'intento_id': intento_id,
        'timestamp': timezone.now().isoformat(),
    }


def terminar_intento_cuestionario(persona_id, intento_id):
    """
    Finaliza el intento de cuestionario, computa automaticamente la nota
    en base a las respuestas correctas de la base de datos y la deja registrada.
    """
    intento = _query_one("""
        SELECT i.id, i.cuestionario_id, i.fecha_inicio, c.notamaxima
        FROM ctr_intentocuestionario i
        JOIN ctr_cuestionario c ON i.cuestionario_id = c.id
        JOIN ctr_estudiante e ON i.estudiante_id = e.id
        WHERE i.id = %s AND e.persona_id = %s AND i.status = TRUE
    """, [intento_id, persona_id])
    if not intento:
        raise LookupError("Intento de evaluacion no encontrado.")

    c_id = intento['cuestionario_id']
    f_ini = intento['fecha_inicio']
    now = timezone.now()
    tiempo_utilizado = int((now - f_ini).total_seconds()) if f_ini else 0
    nota_maxima_cuestionario = float(intento['notamaxima'] or 10.0)

    preguntas = _query_all("""
        SELECT cp.id as item_id, cp.nota as peso, p.id as pregunta_id, tp.tipo as tipo_nombre
        FROM ctr_cuestionariopregunta cp
        JOIN ctr_pregunta p ON cp.pregunta_id = p.id
        LEFT JOIN ctr_tipopregunta tp ON p.tipo_id = tp.id
        WHERE cp.cuestionario_id = %s AND cp.status = TRUE
    """, [c_id])

    total_peso_preguntas = sum(float(p['peso'] or 1.0) for p in preguntas) or 10.0
    puntuacion_acumulada = 0.0
    correctas_count = 0
    incorrectas_count = 0

    with connection.cursor() as cursor:
        for p in preguntas:
            p_id = p['pregunta_id']
            peso = float(p['peso'] or 1.0)

            opciones_correctas = _query_all("""
                SELECT id, respuesta 
                FROM ctr_respuestaopcion 
                WHERE pregunta_id = %s AND es_correcta = TRUE AND status = TRUE
            """, [p_id])
            ids_correctas = {o['id'] for o in opciones_correctas}

            resp_est = _query_one("""
                SELECT id, respuesta_verdadero_falso, respuesta_corta 
                FROM ctr_respuestaintento 
                WHERE intento_id = %s AND pregunta_cuestionario_id = %s AND status = TRUE
            """, [intento_id, p_id])

            es_correcta = False
            puntos_ganados = 0.0

            if resp_est:
                r_id = resp_est['id']
                import json
                sel_ops = _query_all("SELECT origenrespuestaopcion_id FROM ctr_respuestaintento_opciones_seleccionadas WHERE respuestaintento_id = %s", [r_id])
                ids_seleccionadas = {s['origenrespuestaopcion_id'] for s in sel_ops}
                if not ids_seleccionadas and resp_est['respuesta_corta']:
                    try:
                        parsed = json.loads(resp_est['respuesta_corta'])
                        if isinstance(parsed, list):
                            ids_seleccionadas = set(parsed)
                        elif isinstance(parsed, int):
                            ids_seleccionadas = {parsed}
                    except Exception:
                        pass

                tipo_raw = (p['tipo_nombre'] or '').lower()
                if 'verdadero' in tipo_raw or 'falso' in tipo_raw:
                    txt_correcta = opciones_correctas[0]['respuesta'].strip().lower() if opciones_correctas else 'verdadero'
                    resp_vf = (resp_est['respuesta_verdadero_falso'] or '').strip().lower()
                    if resp_vf and resp_vf in txt_correcta:
                        es_correcta = True
                else:
                    if ids_correctas and ids_seleccionadas == ids_correctas:
                        es_correcta = True

                if es_correcta:
                    puntos_ganados = peso
                    puntuacion_acumulada += peso
                    correctas_count += 1
                else:
                    incorrectas_count += 1

                cursor.execute("""
                    UPDATE ctr_respuestaintento
                    SET es_correcta = %s, puntuacion_obtenida = %s
                    WHERE id = %s
                """, [es_correcta, puntos_ganados, r_id])
            else:
                incorrectas_count += 1

        if total_peso_preguntas > 0:
            nota_final = (puntuacion_acumulada / total_peso_preguntas) * nota_maxima_cuestionario
        else:
            nota_final = 0.0
        nota_final = round(nota_final, 2)

        cursor.execute("""
            UPDATE ctr_intentocuestionario
            SET estado = 'finalizado',
                fecha_fin = NOW(),
                tiempo_utilizado = %s,
                puntuacion_total = %s,
                nota_final = %s,
                respuestas_correctas = %s,
                respuestas_incorrectas = %s,
                es_calificado = TRUE,
                fecha_modificacion = NOW()
            WHERE id = %s
        """, [tiempo_utilizado, puntuacion_acumulada, nota_final, correctas_count, incorrectas_count, intento_id])

    return {
        'intento_id': intento_id,
        'cuestionario_id': c_id,
        'estado': 'finalizado',
        'nota_final': nota_final,
        'nota_maxima': nota_maxima_cuestionario,
        'respuestas_correctas': correctas_count,
        'respuestas_incorrectas': incorrectas_count,
        'total_preguntas': len(preguntas),
        'tiempo_utilizado_segundos': tiempo_utilizado,
    }


def obtener_revision_intento(persona_id, intento_id):
    """
    Retorna la revision detallada de un intento completado.
    """
    intento = _query_one("""
        SELECT 
            i.id, i.cuestionario_id, i.estado, i.fecha_inicio, i.fecha_fin,
            i.tiempo_utilizado, i.nota_final, i.puntuacion_total,
            i.respuestas_correctas, i.respuestas_incorrectas,
            c.notamaxima, a.nombre as titulo_cuestionario,
            asig.nombre as materia_nombre
        FROM ctr_intentocuestionario i
        JOIN ctr_cuestionario c ON i.cuestionario_id = c.id
        JOIN ctr_actividad a ON c.actividad_id = a.id
        JOIN ctr_estudiante e ON i.estudiante_id = e.id
        LEFT JOIN ctr_planificacionsemanalcontenido psc ON a.planificacionsemanal_id = psc.id
        LEFT JOIN ctr_materia mat ON psc.materia_id = mat.id
        LEFT JOIN ctr_asignaturamallacurricular amc ON amc.id = mat.asignaturamalla_id
        LEFT JOIN ctr_asignatura asig ON asig.id = amc.asignatura_id
        WHERE i.id = %s AND e.persona_id = %s AND i.status = TRUE
    """, [intento_id, persona_id])
    if not intento:
        raise LookupError("Intento de evaluacion no encontrado.")

    c_id = intento['cuestionario_id']

    sql_preguntas = """
        SELECT 
            cp.id as item_id,
            cp.orden,
            cp.nota as puntuacion,
            p.id as pregunta_id,
            p.nombre as titulo_pregunta,
            p.enunciado,
            p.retroalimentacion as retroalimentacion_general,
            tp.tipo as tipo_nombre
        FROM ctr_cuestionariopregunta cp
        JOIN ctr_pregunta p ON cp.pregunta_id = p.id
        LEFT JOIN ctr_tipopregunta tp ON p.tipo_id = tp.id
        WHERE cp.cuestionario_id = %s AND cp.status = TRUE
        ORDER BY cp.orden ASC, cp.id ASC
    """
    preguntas_raw = _query_all(sql_preguntas, [c_id])

    sql_resp = """
        SELECT id, pregunta_cuestionario_id, respuesta_verdadero_falso, respuesta_corta, es_correcta, puntuacion_obtenida
        FROM ctr_respuestaintento
        WHERE intento_id = %s AND status = TRUE
    """
    respuestas_map = {r['pregunta_cuestionario_id']: r for r in _query_all(sql_resp, [intento_id])}

    sql_sel = """
        SELECT ro.respuestaintento_id, ro.origenrespuestaopcion_id
        FROM ctr_respuestaintento_opciones_seleccionadas ro
        JOIN ctr_respuestaintento r ON r.id = ro.respuestaintento_id
        WHERE r.intento_id = %s
    """
    sel_map = {}
    for s in _query_all(sql_sel, [intento_id]):
        sel_map.setdefault(s['respuestaintento_id'], []).append(s['origenrespuestaopcion_id'])

    preguntas_revision = []
    for idx, p in enumerate(preguntas_raw):
        p_id = p['pregunta_id']
        peso = float(p['puntuacion'] or 1.0)

        opciones_raw = _query_all("""
            SELECT id, respuesta, es_correcta, COALESCE(retroalimentacion, '') as retroalimentacion
            FROM ctr_respuestaopcion
            WHERE pregunta_id = %s AND status = TRUE
            ORDER BY id ASC
        """, [p_id])

        resp_est = respuestas_map.get(p_id)
        seleccionadas = []
        texto_dado = ''
        vf_dado = None
        es_correcta = False
        puntos_obtenidos = 0.0

        if resp_est:
            r_id = resp_est['id']
            seleccionadas = sel_map.get(r_id, [])
            texto_dado = resp_est['respuesta_corta'] or ''
            vf_dado = resp_est['respuesta_verdadero_falso']
            es_correcta = bool(resp_est['es_correcta'])
            puntos_obtenidos = float(resp_est['puntuacion_obtenida'] or 0.0)

        preguntas_revision.append({
            'pregunta_id': p_id,
            'numero': idx + 1,
            'titulo': p['titulo_pregunta'],
            'enunciado': p['enunciado'],
            'puntuacion_maxima': peso,
            'puntos_obtenidos': puntos_obtenidos,
            'es_correcta': es_correcta,
            'retroalimentacion': p['retroalimentacion_general'] or '',
            'opciones': [
                {
                    'id': o['id'],
                    'texto': o['respuesta'],
                    'es_correcta': bool(o['es_correcta']),
                    'fue_seleccionada': o['id'] in seleccionadas,
                    'retroalimentacion': o['retroalimentacion'],
                }
                for o in opciones_raw
            ],
            'respuesta_estudiante': {
                'opcion_ids': seleccionadas,
                'texto': texto_dado,
                'verdadero_falso': vf_dado,
            }
        })

    return {
        'intento_id': intento_id,
        'cuestionario_id': c_id,
        'titulo_cuestionario': intento['titulo_cuestionario'],
        'materia_nombre': intento['materia_nombre'],
        'estado': intento['estado'],
        'fecha_inicio': intento['fecha_inicio'].isoformat() if intento['fecha_inicio'] else None,
        'fecha_fin': intento['fecha_fin'].isoformat() if intento['fecha_fin'] else None,
        'tiempo_utilizado_segundos': intento['tiempo_utilizado'] or 0,
        'nota_final': float(intento['nota_final'] or 0.0),
        'nota_maxima': float(intento['notamaxima'] or 10.0),
        'respuestas_correctas': intento['respuestas_correctas'] or 0,
        'respuestas_incorrectas': intento['respuestas_incorrectas'] or 0,
        'total_preguntas': len(preguntas_revision),
        'preguntas': preguntas_revision,
    }
