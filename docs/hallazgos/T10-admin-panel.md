# T10 · Panel de Administración de Django

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~6 h |
| **Rama** | `T10-admin-panel` |
| **Material** | `app/admin.py`, `app/tests/test_admin.py` |

## Qué se pedía

Registrar los modelos de la aplicación móvil en el panel de administración de Django (`/admin/`), con listados informativos y filtros útiles para los operadores del sistema, sin necesidad de acceder directamente a la base de datos.

## Método

1. **Creación de `app/admin.py`**:
   Se creó el archivo con cuatro clases `ModelAdmin` personalizadas, una por cada modelo de la aplicación:

   - `VersionAppMovilAdmin`: Permite ver y editar versiones de la app por plataforma. El campo `forzar_actualizacion` es editable directamente desde el listado (`list_editable`) para una respuesta operacional rápida ante actualizaciones críticas.
   - `PreferenciaNotificacionAdmin`: Listado completo de preferencias por usuario con todos los toggles de notificaciones visibles de un vistazo. Búsqueda por nombre, apellido y correo del usuario.
   - `FeedbackMovilAdmin`: Lista los reportes con jerarquía temporal (`date_hierarchy`), resumen del mensaje en 50 caracteres y campos de auditoría en solo lectura.
   - `DispositivoRegistradoAdmin`: Permite ver los tokens de dispositivos con filtros por plataforma y estado activo.

2. **Optimizaciones de rendimiento**:
   - `raw_id_fields = ('usuario',)` en los modelos relacionados con usuarios para evitar selectores HTML que cargarían todos los usuarios de la base de datos.
   - `select_related` implícito en las búsquedas mediante `__` de doble guion bajo en `search_fields`.

3. **Pruebas Automatizadas (TDD)**:
   Se implementaron 10 pruebas en `app/tests/test_admin.py` cubriendo:
   - Registro formal de los 4 modelos en `admin.site` (4 pruebas).
   - Acceso HTTP 200 a los listados para superusuario (4 pruebas).
   - Redirección al login para usuarios sin privilegios de staff (1 prueba).
   - Redirección al login para peticiones anónimas (1 prueba).

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| `VersionAppMovilAdmin` | `list_editable`, `list_filter`, `search_fields` | Registrado | ✅ Válido |
| `PreferenciaNotificacionAdmin` | `list_filter` por todos los campos booleanos, `raw_id_fields` | Registrado | ✅ Válido |
| `FeedbackMovilAdmin` | `date_hierarchy`, `readonly_fields`, `raw_id_fields` | Registrado | ✅ Válido |
| `DispositivoRegistradoAdmin` | `list_filter` por plataforma y activo | Registrado | ✅ Válido |
| Pruebas (TDD) | 10 pruebas unitarias | 100% pasando | ✅ Válido |

## Verificación

```bash
# Ejecutar pruebas del admin
python manage.py test app.tests.test_admin

# Suite completa
python manage.py test
```

### Acceso al Panel

1. Levantar servidor: `python manage.py runserver`
2. Ingresar a `http://127.0.0.1:8000/admin/` con el usuario `admin`.
3. En la sección **App** aparecen los cuatro modelos:
   - **Dispositivos registrados** — con filtro por plataforma y activo.
   - **Feedbacks móviles** — con navegación por fecha y resumen de mensajes.
   - **Preferencias de notificación** — con filtros por tipo de aviso.
   - **Versiones App Móvil** — con edición directa del campo `forzar_actualizacion`.
