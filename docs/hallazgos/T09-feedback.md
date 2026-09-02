# T9 · Endpoint `POST /movil/feedback/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~10 h |
| **Rama** | `T09-feedback` |
| **Material** | `openapi/feedback.yaml`, `app/models.py`, `app/views.py`, `app/serializers.py`, `app/throttling.py`, `app/tests/test_feedback.py` |

## Qué se pedía

Implementar el endpoint `POST /movil/feedback/` para que los usuarios autenticados puedan enviar sugerencias, quejas o reportes de error desde la aplicación móvil:
- El formulario es abierto: `tipo` (SUGERENCIA, QUEJA, ERROR) y `mensaje` libre.
- Requiere autenticación (`IsAuthenticated` vía JWT Bearer).
- Debe tener un **límite de tasa estricto** por clase propia (`app/throttling.py`), sin tocar `proyecto/settings.py`.
- Respuestas estandarizadas con el sobre institucional `RespuestaApi` (`isSuccess`).

## Método

1. **Definición del Contrato (OpenAPI 3.0)**:
   Se definió `openapi/feedback.yaml` especificando la operación `post`, los esquemas de datos `FeedbackMovilCreate` y `RespuestaExito`, con los códigos de error `400` (validación), `401` (no autenticado) y `429` (throttling excedido).

2. **Modelo y Migración**:
   Se creó el modelo `FeedbackMovil` en `app/models.py` heredando de `ModeloBase` (`sige_ports`), con relación `ForeignKey` hacia el usuario (permitiendo múltiples feedbacks por usuario), campo `tipo` con opciones controladas y `mensaje` libre. Se generó y aplicó la migración `0004_feedbackmovil.py`.

3. **Serializador**:
   En `app/serializers.py` se implementó `FeedbackMovilSerializer` usando `ModelSerializer` con los campos `tipo` y `mensaje`, delegando toda la validación al modelo (choices y campo requerido).

4. **Throttling Aislado**:
   En `app/throttling.py` se añadió la clase `FeedbackRateThrottle`, heredando de `UserRateThrottle` con un límite duro de `2/hour` por usuario. La tasa se define en el código de la app, **sin modificar** la zona prohibida de `proyecto/settings.py`.

5. **Vista y Transaccionalidad**:
   En `app/views.py` se implementó `FeedbackView(APIView)`:
   - Usa el `IsAuthenticated` global (sin sobreescribir `permission_classes`).
   - Aplica `FeedbackRateThrottle` para bloquear abusos.
   - El guardado se protege dentro de `transaction.atomic()`.
   - Toda salida (201, 400, 500) pasa por `RespuestaApi` garantizando el sobre `isSuccess`.

6. **Pruebas Automatizadas (TDD)**:
   Se implementaron 4 pruebas en `app/tests/test_feedback.py` cubriendo:
   - Camino feliz: el feedback se crea y se asocia correctamente al usuario.
   - Rechazo de peticiones anónimas (`401 Unauthorized`).
   - Datos inválidos: tipo fuera de opciones y mensaje ausente (`400 Bad Request` con estructura `errors`).
   - Throttling estricto: a la tercera petición el servidor devuelve `429 Too Many Requests`.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/feedback.yaml` | Creado | ✅ Válido |
| Modelo | `FeedbackMovil` | Migración `0004` aplicada | ✅ Válido |
| Serializador | `FeedbackMovilSerializer` | Validación de tipo y mensaje | ✅ Válido |
| Throttling | `FeedbackRateThrottle` | Activo (2/hora por usuario) | ✅ Válido |
| Vista | `FeedbackView` | POST con atomic y sobre estándar | ✅ Válido |
| Pruebas (TDD) | 4 pruebas unitarias dedicadas | 100% pasando (23/23 suite completa) | ✅ Válido |

## Verificación

```bash
# 1. Ejecutar pruebas unitarias de T9
python manage.py test app.tests.test_feedback

# 2. Ejecutar suite completa
python manage.py test
```

### Ejemplo de Petición y Respuesta

**POST `/api/v1.0.0/movil/feedback/`**
```json
// Headers:
// Authorization: Bearer <token>
// Content-Type: application/json

{
    "tipo": "SUGERENCIA",
    "mensaje": "Por favor agreguen modo oscuro a la aplicación."
}
```

**Respuesta (HTTP 201 Created):**
```json
{
    "isSuccess": true,
    "message": "Feedback enviado con éxito.",
    "data": {
        "tipo": "SUGERENCIA",
        "mensaje": "Por favor agreguen modo oscuro a la aplicación."
    }
}
```

**Respuesta throttling excedido (HTTP 429):**
```json
{
    "detail": "Request was throttled. Expected available in 3600 seconds."
}
```
