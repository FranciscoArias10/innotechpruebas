# -*- coding: utf-8 -*-
from rest_framework.throttling import AnonRateThrottle

class AppVersionRateThrottle(AnonRateThrottle):
    """
    Límite de tasa para el endpoint de versión de la aplicación.
    Dado que es un endpoint público (sin autenticación), evitamos el abuso.
    Se define el rate duro aquí para no contaminar settings.py del arnés.
    """
    rate = '10/minute'
