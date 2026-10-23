# -*- coding: utf-8 -*-
"""
Puertos de autenticacion para el andamio.

Cada funcion es un CONTRATO igual que portal.py:
  - En este andamio consulta directamente la DB via SQL crudo sobre las tablas
    reales del sistema (ctr_persona, ctr_estudiante, ctr_periodo).
  - En sige-ube la misma funcion existira como puerto oficial.

REGLA: no inventes datos. Si la tabla no existe aun o el usuario de prueba
no tiene las relaciones, la funcion lanza LookupError o devuelve un valor
razonable (lista vacia, None). El endpoint lo traduce a un mensaje util.
"""
from django.db import connection


def _query_one(sql, params=()):
    """Ejecuta una consulta SQL y devuelve la primera fila como dict, o None."""
    with connection.cursor() as c:
        c.execute(sql, params)
        cols = [d[0] for d in c.description]
        row = c.fetchone()
        if row is None:
            return None
        return dict(zip(cols, row))


def _query_all(sql, params=()):
    """Ejecuta una consulta SQL y devuelve todas las filas como lista de dicts."""
    with connection.cursor() as c:
        c.execute(sql, params)
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]


def obtener_perfiles_usuario(user):
    """
    Devuelve la lista de perfiles del usuario según la estructura real de la base de datos:
    - auth_user.is_staff / is_superuser
    - ctr_persona vinculada al usuario
    - ctr_profesor (docentes)
    - ctr_estudiante (estudiantes)
    - ctr_familiar (representantes legales)
    - ctr_perfilusuario / auth_group (cargos directivos y administrativos)
    """
    perfiles = []
    try:
        row = _query_one(
            """
            SELECT 
                (SELECT COUNT(*) FROM ctr_estudiante e JOIN ctr_persona p ON p.id = e.persona_id WHERE p.usuario_id = %s AND e.status = true) AS es_estudiante,
                (SELECT COUNT(*) FROM ctr_profesor pr JOIN ctr_persona p ON p.id = pr.persona_id WHERE p.usuario_id = %s AND pr.status = true) AS es_profesor,
                (SELECT COUNT(*) FROM ctr_familiar f JOIN ctr_persona p ON p.id = f.personafamiliar_id WHERE p.usuario_id = %s AND f.representante = true AND f.status = true) AS es_representante,
                (SELECT string_agg(g.name, ',') FROM ctr_perfilusuario pu JOIN auth_group g ON g.id = pu.grupo_id JOIN ctr_persona p ON p.id = pu.persona_id WHERE p.usuario_id = %s AND pu.status = true) AS perfiles_institucionales,
                (SELECT string_agg(g.name, ',') FROM auth_user_groups ug JOIN auth_group g ON g.id = ug.group_id WHERE ug.user_id = %s) AS perfiles_django
            """,
            [user.id, user.id, user.id, user.id, user.id]
        )
        if row:
            if row.get('es_profesor'):
                perfiles.append('teacher')
            if row.get('es_estudiante'):
                perfiles.append('student')
            if row.get('es_representante'):
                perfiles.append('representative')

            # Grupos django e institucionales
            todos_grupos = set()
            for gfield in [row.get('perfiles_institucionales'), row.get('perfiles_django')]:
                if gfield:
                    for g in gfield.split(','):
                        todos_grupos.add(g.strip().lower())

            for g in todos_grupos:
                if 'rector' in g and 'rector' not in perfiles:
                    perfiles.append('rector')
                elif 'vicerrector' in g and 'vicerrector' not in perfiles:
                    perfiles.append('vicerrector')
                elif 'director' in g and 'director' not in perfiles:
                    perfiles.append('director')
                elif 'administrador' in g and 'admin' not in perfiles:
                    perfiles.append('admin')
                elif 'dece' in g and 'dece' not in perfiles:
                    perfiles.append('dece')
                elif 'admision' in g and 'admisiones' not in perfiles:
                    perfiles.append('admisiones')
                elif 'secretaria' in g and 'secretaria' not in perfiles:
                    perfiles.append('secretaria')
    except Exception:
        pass

    if user.is_staff or user.is_superuser:
        if 'admin' not in perfiles:
            perfiles.append('admin')

    if not perfiles:
        perfiles = ['student']

    return perfiles


def obtener_periodos_usuario(user):
    """
    Devuelve los periodos lectivos disponibles para el usuario.

    Consulta ctr_periodo. Si la tabla no existe, devuelve un periodo de prueba.

    Devuelve lista de dicts: [{'id': int, 'name': str, 'is_active': bool}]
    """
    try:
        rows = _query_all(
            "SELECT id, nombre AS name, activo AS is_active "
            "FROM ctr_periodo WHERE status = TRUE ORDER BY activo DESC, id DESC LIMIT 10"
        )
        if rows:
            return [{'id': r['id'], 'name': r['name'], 'is_active': bool(r['is_active'])} for r in rows]
    except Exception:
        pass

    # Fallback: periodo de prueba para el andamio
    return [{'id': 1, 'name': 'Periodo de prueba (andamio)', 'is_active': True}]


def obtener_periodo_activo_id(periodos):
    """
    Devuelve el id del periodo activo de una lista de periodos.
    Si no hay ninguno activo, devuelve el id del primero.
    """
    for p in periodos:
        if p.get('is_active'):
            return p['id']
    if periodos:
        return periodos[0]['id']
    return None


def obtener_username_por_cedula(cedula):
    """
    Devuelve dict {'username': str, 'full_name': str} para la cedula dada.
    Lanza LookupError si no se encuentra.
    """
    try:
        row = _query_one(
            """
            SELECT au.username,
                   TRIM(cp.nombres || ' ' || cp.apellido_1 || ' ' || COALESCE(cp.apellido_2, '')) AS full_name
            FROM ctr_persona cp
            JOIN auth_user au ON au.id = cp.usuario_id
            WHERE cp.cedula = %s AND cp.status = TRUE
            LIMIT 1
            """,
            [cedula]
        )
        if row:
            return {'username': row['username'], 'full_name': row['full_name']}
    except Exception:
        pass
    raise LookupError('No se encontro usuario para cedula: %s' % cedula)


def obtener_persona_por_usuario(user):
    """
    Devuelve dict con datos de la persona vinculada al usuario.
    Devuelve None si no existe o si hay error de DB.
    """
    try:
        row = _query_one(
            """
            SELECT cedula, nombres, apellido_1, apellido_2,
                   TRIM(nombres || ' ' || apellido_1 || ' ' || COALESCE(apellido_2, '')) as nombre_completo,
                   TRIM(apellido_1 || ' ' || COALESCE(apellido_2, '')) as apellidos,
                   correo_institucional, foto
            FROM ctr_persona
            WHERE usuario_id = %s AND status = TRUE
            LIMIT 1
            """,
            [user.id]
        )
        return row
    except Exception:
        return None


def password_change_required(user):
    """
    Devuelve True si el usuario debe cambiar su clave al ingresar.

    En el sistema real se consulta una bandera en el perfil. Aqui intentamos
    la consulta; si falla (tabla no existe) devolvemos False.
    """
    try:
        row = _query_one(
            "SELECT debe_cambiar_clave FROM ctr_estudiante WHERE usuario_id = %s AND status = TRUE LIMIT 1",
            [user.id]
        )
        if row and row.get('debe_cambiar_clave'):
            return True
    except Exception:
        pass
    return False
