# -*- coding: utf-8 -*-
"""
Prueba del andamio. ESTO NO VIAJA a sige-ube.

Verifica que todos los puertos de `sige_ports.portal` respondan y que su fixture
exista. Sin esto, un fixture faltante se descubre recien cuando alguien toma la
tarea que lo usa.

No prueba la logica de negocio: eso vive del otro lado, en el sistema real.
"""
import inspect
from django.test import SimpleTestCase

from sige_ports import portal

# firma -> argumentos de ejemplo
ARGUMENTOS = {
    'resumen_estudiante': (7, 6),
    'representados_de': (7,),
    'representa_a': (7, 4412),
    'notas_de_estudiante': (7, 6, 123),
    'asistencia_de_estudiante': (7, 6),
    'horario_de_estudiante': (7, 6),
}


def _puertos_publicos():
    return [n for n, f in inspect.getmembers(portal, inspect.isfunction)
            if not n.startswith('_') and f.__module__ == portal.__name__]


class PuertosTests(SimpleTestCase):

    def test_todo_puerto_tiene_argumentos_de_ejemplo(self):
        """Si agregas un puerto, agrega su entrada en ARGUMENTOS."""
        faltan = set(_puertos_publicos()) - set(ARGUMENTOS)
        self.assertFalse(faltan, 'Puertos sin argumentos de ejemplo: %s' % faltan)

    def test_todo_puerto_responde(self):
        """Cada puerto devuelve algo. Si falta su fixture, falla aqui."""
        for nombre in _puertos_publicos():
            with self.subTest(puerto=nombre):
                resultado = getattr(portal, nombre)(*ARGUMENTOS[nombre])
                self.assertIsNotNone(resultado)

    def test_todo_puerto_esta_documentado(self):
        """Un puerto sin docstring no es un contrato, es una adivinanza."""
        for nombre in _puertos_publicos():
            with self.subTest(puerto=nombre):
                doc = getattr(portal, nombre).__doc__
                self.assertTrue(doc and doc.strip(),
                                'El puerto %s no documenta que devuelve' % nombre)
