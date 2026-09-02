# T8 · Endpoint `GET|PUT /movil/notifications/preferences/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~12 h |
| **Rama** | `T08-notifications-preferences` |
| **Material** | `openapi/notification_preferences.yaml`, `app/models.py`, `app/views.py`, `app/serializers.py`, `app/tests/test_notification_preferences.py` |

## Qué se pedía

Implementar el endpoint `GET|PUT /movil/notifications/preferences/` para consultar y modificar las preferencias de notificación de cada usuario autenticado:
- Indicar qué avisos quiere recibir el usuario (`push_enabled`, `grades`, `attendance`, `events`, `announcements`, `tasks`).
- El método `PUT` debe ser **parcial** (permitir cambiar un subconjunto de campos) e **idempotente** (mismo resultado sin importar cuántas veces se repita la petición).
- Autenticación requerida (`IsAuthenticated` vía JWT Bearer).
- Respuestas estandarizadas con el sobre institucional `RespuestaApi` (`isSuccess`).

## Método

1. **Definición del Contrato (OpenAPI 3.0)**:
   Se definió `openapi/notification_preferences.yaml` especificando las operaciones `get` y `put`, los esquemas de datos reutilizables, códigos `200`, `400` (validación) y `401` (no autenticado). Se actualizó el bundle general en `openapi/openapi.yaml`.

2. **Modelo y Migración**:
   Se creó el modelo `PreferenciaNotificacion` en `app/models.py` heredando de `ModeloBase` (`sige_ports`), con relación `OneToOne` hacia el usuario y valores por defecto activos (`default=True`). Se generó y aplicó la migración `0003_preferencianotificacion.py`.

3. **Serializador y Actualización Parcial**:
   En `app/serializers.py` se implementó `PreferenciaNotificacionSerializer` con todos los campos opcionales (`required=False`), garantizando soporte para actualizaciones parciales (`partial=True`).

4. **Vista Idempotente**:
   En `app/views.py` se implementó `NotificationPreferencesView(APIView)`:
   - En `GET`: recupera las preferencias o inicializa los valores predeterminados mediante `get_or_create`, garantizando que todo usuario siempre reciba preferencias válidas.
   - En `PUT`: valida y actualiza parcialmente dentro de una transacción atómica de forma idempotente, devolviendo el estado consolidado.

5. **Pruebas Automatizadas (TDD)**:
   Se implementaron 8 pruebas exhaustivas en `app/tests/test_notification_preferences.py` cubriendo:
   - Consulta exitosa con generación de defaults.
   - Rechazo de peticiones anónimas (`401 Unauthorized`).
   - Actualización parcial sin alterar campos omitidos.
   - Idempotencia de llamadas sucesivas.
   - Validación de tipos erróneos (`400 Bad Request` con estructura `errors`).
   - Cumplimiento estricto del sobre institucional (`isSuccess`).
   - Aislamiento seguro entre diferentes usuarios.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/notification_preferences.yaml` | Creado y compilado en bundle | ✅ Válido |
| Modelo | `PreferenciaNotificacion` | Migración `0003` aplicada | ✅ Válido |
| Serializador | `PreferenciaNotificacionSerializer` | Soporte parcial configurado | ✅ Válido |
| Vista | `NotificationPreferencesView` | GET y PUT idempotente | ✅ Válido |
| Pruebas (TDD) | 8 Pruebas unitarias dedicadas | 100% pasando (19/19 suite completa) | ✅ Válido |

## Verificación

```bash
# 1. Ejecutar pruebas unitarias
python manage.py test app.tests.test_notification_preferences

# 2. Ejecutar suite completa
python manage.py test
```

### Ejemplo de Petición y Respuesta

**PUT `/api/v1.0.0/movil/notifications/preferences/`**
```json
// Headers:
// Authorization: Bearer <token>
// Content-Type: application/json

{
    "grades": false,
    "tasks": false
}
```

**Respuesta (HTTP 200 OK):**
```json
{
    "isSuccess": true,
    "message": "Preferencias de notificación actualizadas con éxito.",
    "data": {
        "push_enabled": true,
        "grades": false,
        "attendance": true,
        "events": true,
        "announcements": true,
        "tasks": false
    }
}
```
