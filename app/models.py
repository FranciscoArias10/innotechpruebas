# -*- coding: utf-8 -*-
"""
Modelos de la app. ESTO SI VIAJA a sige-ube.

Regla: solo modelos NUEVOS. Nunca importen ni modifiquen un modelo del
sistema real -- si necesitan datos de alla, va por un puerto de sige_ports.
"""
from django.conf import settings
from django.db import models

from sige_ports import ModeloBase


class DispositivoRegistrado(ModeloBase):
    """Token de notificaciones push de un dispositivo de un usuario."""

    ANDROID = 1
    IOS = 2
    PLATAFORMA = ((ANDROID, u'Android'), (IOS, u'iOS'))

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='dispositivos', verbose_name=u'Usuario')
    token = models.CharField(max_length=255, verbose_name=u'Token del dispositivo')
    plataforma = models.IntegerField(
        choices=PLATAFORMA, default=ANDROID, verbose_name=u'Plataforma')
    app_version = models.CharField(
        max_length=20, default='', blank=True, verbose_name=u'Versión de la app')
    modelo_dispositivo = models.CharField(
        max_length=120, default='', blank=True, verbose_name=u'Modelo del dispositivo')
    activo = models.BooleanField(default=True, verbose_name=u'Activo')

    def __str__(self):
        return u'%s - %s (%s)' % (self.usuario, self.get_plataforma_display(), self.token[:12])

    class Meta:
        verbose_name = u'Dispositivo registrado'
        verbose_name_plural = u'Dispositivos registrados'
        ordering = ['-fecha_modificacion']
        unique_together = ('usuario', 'token')
