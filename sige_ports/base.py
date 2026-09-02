# -*- coding: utf-8 -*-
"""
Doble de `helpers.model_helper.ModeloBase` del sistema real.

Los campos son EXACTAMENTE los mismos que los del original, para que la
migracion que se genere del lado de sige-ube produzca las mismas columnas.
No agreguen ni quiten campos aqui.
"""
from django.conf import settings
from django.db import models


class ModeloBase(models.Model):
    """Modelo base para todos los modelos del proyecto."""

    fecha_creacion = models.DateTimeField(
        blank=True, auto_now_add=True, null=True, verbose_name=u"Fecha creación")
    usuario_creacion = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+',
        blank=True, null=True, verbose_name=u'Usuario de creación')
    fecha_modificacion = models.DateTimeField(
        blank=True, null=True, auto_now=True, verbose_name=u"Fecha modificación")
    usuario_modificacion = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+',
        blank=True, null=True)
    status = models.BooleanField(default=True, verbose_name=u"Status")

    class Meta:
        abstract = True
