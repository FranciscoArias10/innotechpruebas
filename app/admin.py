# -*- coding: utf-8 -*-
"""
Configuración del panel de administración de Django (T10).
Registra los modelos de la app móvil con listados, filtros, búsquedas
y optimizaciones para los operadores del sistema.
"""
from django.contrib import admin
from django.utils.html import format_html

from app.models import (
    DispositivoRegistrado,
    VersionAppMovil,
    PreferenciaNotificacion,
    FeedbackMovil,
)


@admin.register(VersionAppMovil)
class VersionAppMovilAdmin(admin.ModelAdmin):
    list_display = (
        'plataforma',
        'version_minima',
        'version_actual',
        'forzar_actualizacion',
        'status',
        'fecha_modificacion',
    )
    list_filter = ('plataforma', 'forzar_actualizacion', 'status')
    search_fields = ('version_minima', 'version_actual')
    list_editable = ('forzar_actualizacion',)
    ordering = ('plataforma',)


@admin.register(PreferenciaNotificacion)
class PreferenciaNotificacionAdmin(admin.ModelAdmin):
    list_display = (
        'usuario',
        'push_enabled',
        'grades',
        'attendance',
        'events',
        'announcements',
        'tasks',
        'fecha_modificacion',
    )
    list_filter = (
        'push_enabled',
        'grades',
        'attendance',
        'events',
        'announcements',
        'tasks',
    )
    search_fields = (
        'usuario__username',
        'usuario__email',
        'usuario__first_name',
        'usuario__last_name',
    )
    raw_id_fields = ('usuario',)


@admin.register(FeedbackMovil)
class FeedbackMovilAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'usuario',
        'tipo',
        'resumen_mensaje',
        'fecha_creacion',
        'status',
    )
    list_filter = ('tipo', 'status', 'fecha_creacion')
    search_fields = ('usuario__username', 'usuario__email', 'mensaje')
    date_hierarchy = 'fecha_creacion'
    readonly_fields = (
        'fecha_creacion',
        'fecha_modificacion',
        'usuario_creacion',
        'usuario_modificacion',
    )
    raw_id_fields = ('usuario',)

    def resumen_mensaje(self, obj):
        if not obj.mensaje:
            return '-'
        return (obj.mensaje[:50] + '...') if len(obj.mensaje) > 50 else obj.mensaje
    resumen_mensaje.short_description = 'Mensaje'


@admin.register(DispositivoRegistrado)
class DispositivoRegistradoAdmin(admin.ModelAdmin):
    list_display = (
        'usuario',
        'plataforma_nombre',
        'app_version',
        'modelo_dispositivo',
        'activo',
        'fecha_modificacion',
    )
    list_filter = ('plataforma', 'activo', 'status')
    search_fields = ('usuario__username', 'token', 'modelo_dispositivo')
    raw_id_fields = ('usuario',)

    def plataforma_nombre(self, obj):
        return obj.get_plataforma_display()
    plataforma_nombre.short_description = 'Plataforma'
