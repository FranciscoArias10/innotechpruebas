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
