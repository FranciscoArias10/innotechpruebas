# -*- coding: utf-8 -*-
"""
Puertos de datos del portal.

Cada funcion de aqui es un CONTRATO: nombre, argumentos y forma del diccionario
que devuelve. En este repositorio la implementacion es un doble que lee un
archivo de fixtures/. En sige-ube, la misma funcion consulta la base real.

Ustedes NUNCA escriben la version real. Ustedes escriben todo lo que la rodea:
la vista, el serializer, la validacion, los codigos de error y las pruebas.

Si su endpoint necesita un dato que no esta aqui, NO inventen la consulta:
pidan el puerto nuevo, con la forma exacta que necesitan. Se agrega, se les
entrega el fixture, y siguen.
"""
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures'


def _cargar(nombre):
    ruta = FIXTURES / nombre
    if not ruta.exists():
        raise FileNotFoundError(
            'Falta el fixture %s. Pidelo antes de seguir: los dobles no se '
            'inventan, se generan desde el sistema real.' % ruta.name)
    with ruta.open(encoding='utf-8') as f:
        return json.load(f)


def resumen_estudiante(persona_id, periodo_id):
    """
    Metricas del tablero del estudiante.

    Devuelve:
        {
          'total_subjects': int,
          'attendance_percentage': float,
          'pending_activities': int,
          'enrollment': {'id': int, 'level': str, 'level_alias': str, 'parallel': str},
          'period': {'id': int, 'name': str},
        }

    Lanza LookupError si la persona no tiene matricula en ese periodo.
    """
    return _cargar('resumen_estudiante.json')


def representados_de(persona_id):
    """
    Estudiantes que representa una persona.

    Devuelve una lista de:
        {'estudiante_id': int, 'persona_id': int, 'nombre_completo': str,
         'nivel': str, 'paralelo': str}

    Lista vacia si no representa a nadie.
    """
    return _cargar('representados.json')


def representa_a(persona_id, estudiante_id):
    """
    Verificacion de parentesco. True si esa persona representa a ese estudiante
    en un vinculo activo.

    ESTE PUERTO ES DE SEGURIDAD. En el doble siempre devuelve True para que
    puedan trabajar; en el sistema real consulta el vinculo. Sus pruebas DEBEN
    cubrir tambien el caso False -- monten el doble con `unittest.mock.patch`.
    """
    return True


def notas_de_estudiante(persona_id, periodo_id, materia_asignada_id):
    """
    Libro de calificaciones de un estudiante en una materia.

    Devuelve:
        {
          'subject': {'id': int, 'name': str, 'level': str, 'parallel': str,
                      'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD',
                      'total_weeks': int, 'pending_activities': int},
          'evaluation_model': {
              'id': int, 'name': str, 'is_quantitative': bool,
              'items': [{                       # quimestres
                  'id': int, 'name': str, 'alias': str,
                  'max_score': int, 'total_percentage': int,
                  'grade': float|None, 'grade_letter': str|None,
                  'grading_books': [{           # parciales
                      'id': int, 'name': str, 'percentage': float,
                      'grade': float|None, 'grade_letter': str|None,
                      'categories': [{          # tareas, lecciones, ...
                          'id': int, 'name': str, 'percentage': float,
                          'grade': float|None, 'grade_letter': str|None,
                          'activities': [{'id': int, 'name': str,
                                          'grade': float|None,
                                          'grade_letter': str|None}],
                      }],
                  }],
              }],
          },
        }

    OJO: cuando `is_quantitative` es False la materia es CUALITATIVA y las notas
    vienen en `grade_letter` (por ejemplo 'EX', 'MB'), con `grade` en None. Su
    vista tiene que manejar los dos casos; no asuman que siempre hay un numero.

    Lanza LookupError si esa materia asignada no corresponde al estudiante.
    """
    return _cargar('notas_estudiante.json')


def asistencia_de_estudiante(persona_id, periodo_id):
    """
    Resumen de asistencia por materia.

    Devuelve:
        {'subjects': [{
            'cronograma_id': int,
            'name': str,
            'by_hours': {'attended': int, 'justified': int, 'pending': int,
                         'absent': int, 'total': int, 'percentage': float},
            'by_days':  {... mismas claves ...},
            'status': str,      # 'excelente' | 'normal' | 'riesgo' | ...
        }]}

    `percentage` se calcula como (attended + justified) / total * 100: la falta
    justificada NO baja el porcentaje. No lo recalculen en la vista.
    """
    return _cargar('asistencia_estudiante.json')


def horario_de_estudiante(persona_id, periodo_id):
    """
    Horario semanal, agrupado por turno y por dia.

    Devuelve:
        {
          'turnos': [{
              'id': int, 'nombre': str, 'nombre_corto': str,
              'aplica_asistencia': bool,
              'dias': [{'indice': int, 'nombre': str, 'clases': [{
                  'nombre': str, 'paralelo': str, 'aula': str, 'profesor': str,
                  'fecha_inicio': 'YYYY-MM-DD', 'fecha_fin': 'YYYY-MM-DD',
                  'color': str,
              }]}],
          }],
          'dias_visibles': [{'indice': int, 'nombre': str, 'clases': []}],
        }

    `indice` va de 1 (lunes) a 7 (domingo). `dias_visibles` trae los dias que la
    institucion muestra aunque no tengan clase, para que la grilla no se deforme.
    """
    return _cargar('horario_estudiante.json')
