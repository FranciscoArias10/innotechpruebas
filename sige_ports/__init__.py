# -*- coding: utf-8 -*-
"""
sige_ports — la costura entre el codigo de ustedes y el sistema real.

ESTE PAQUETE NO VIAJA A sige-ube.

Aqui adentro hay dobles: imitaciones de piezas del sistema real que sirven
para que puedan trabajar y correr pruebas sin tener el monolito.

En sige-ube existe un paquete con ESTE MISMO NOMBRE, cuyo contenido son las
piezas de verdad. Como el nombre del paquete y las firmas son identicas, el
codigo que ustedes escriben en app/ funciona en los dos lados SIN CAMBIAR
UNA SOLA LINEA.

Regla practica: si necesitan algo del sistema real, no lo importen directo.
Pidan que se agregue un puerto aqui.
"""
from sige_ports.base import ModeloBase
from sige_ports.respuesta import RespuestaApi
from sige_ports import portal

__all__ = ['ModeloBase', 'RespuestaApi', 'portal']
