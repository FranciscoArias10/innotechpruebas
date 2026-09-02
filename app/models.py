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


class VersionAppMovil(ModeloBase):
    """Información sobre la versión de la app móvil y forzado de actualización."""
    
    ANDROID = 'android'
    IOS = 'ios'
    PLATAFORMA = ((ANDROID, u'Android'), (IOS, u'iOS'))

    plataforma = models.CharField(
        max_length=10, choices=PLATAFORMA, unique=True, verbose_name=u'Plataforma')
    version_minima = models.CharField(
        max_length=20, default='1.0.0', verbose_name=u'Versión mínima soportada')
    version_actual = models.CharField(
        max_length=20, default='1.0.0', verbose_name=u'Versión actual')
    forzar_actualizacion = models.BooleanField(
        default=False, verbose_name=u'Forzar actualización global')

    def __str__(self):
        return u'Versión %s: Mín %s / Act %s' % (self.get_plataforma_display(), self.version_minima, self.version_actual)

    class Meta:
        verbose_name = u'Versión App Móvil'
        verbose_name_plural = u'Versiones App Móvil'


class PreferenciaNotificacion(ModeloBase):
    """Preferencias de notificación push y avisos para cada usuario."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='preferencias_notificacion', verbose_name=u'Usuario')
    push_enabled = models.BooleanField(
        default=True, verbose_name=u'Notificaciones push habilitadas')
    grades = models.BooleanField(
        default=True, verbose_name=u'Avisos de calificaciones y notas')
    attendance = models.BooleanField(
        default=True, verbose_name=u'Avisos de asistencia y faltas')
    events = models.BooleanField(
        default=True, verbose_name=u'Avisos de calendario y eventos')
    announcements = models.BooleanField(
        default=True, verbose_name=u'Avisos y comunicados generales')
    tasks = models.BooleanField(
        default=True, verbose_name=u'Avisos de tareas y planificación')

    def __str__(self):
        return u'Preferencias de %s' % self.usuario

    class Meta:
        verbose_name = u'Preferencia de notificación'
        verbose_name_plural = u'Preferencias de notificación'

