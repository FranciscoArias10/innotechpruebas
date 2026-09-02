# -*- coding: utf-8 -*-
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class AppVersionRateThrottle(AnonRateThrottle):
    """
    Límite de tasa para el endpoint de versión de la aplicación.
    Dado que es un endpoint público (sin autenticación), evitamos el abuso.
    Se define el rate duro aquí para no contaminar settings.py del arnés.
    """
    rate = '10/minute'


class FeedbackRateThrottle(UserRateThrottle):
    """
    Límite de tasa para el endpoint de envío de feedback.
    Evita abuso y spam de comentarios a 2 por hora por usuario.
    """
    scope = 'feedback'
    rate = '2/hour'

