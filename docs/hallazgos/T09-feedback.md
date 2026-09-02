# Hallazgos y Ejecución: T09 Feedback Móvil

## Resumen de la Tarea
- **Endpoint:** `POST /api/v1.0.0/movil/feedback/`
- **Propósito:** Permitir a los usuarios de la app enviar comentarios, quejas o sugerencias.
- **Complejidad:** Se requirió implementar un límite de tasa (throttling) estricto (2 peticiones por hora) por usuario para mitigar posibles abusos y spam a la base de datos de la institución.

## Decisiones de Arquitectura y Reglas Aplicadas

1. **Modelado (sige_ports)**:
   Se creó el modelo `FeedbackMovil` heredando explícitamente de `ModeloBase` (desde `sige_ports`). Se usó `fecha_creacion` (del base) para evitar incompatibilidades con el sistema real. El modelo registra al `usuario`, el `tipo` (Sugerencia, Error, Queja) y el `mensaje`.

2. **Límite de Tasa Aislado (Throttling)**:
   > [!TIP]
   > En lugar de tocar el archivo `proyecto/settings.py` que está prohibido, el throttling se encapsuló en `app/throttling.py` mediante la clase `FeedbackRateThrottle`, heredando de `UserRateThrottle`. Se fijó una cuota dura de `2/hour`.

3. **Autenticación Implícita**:
   No se sobreescribió `permission_classes` en la vista, apoyándonos en el `IsAuthenticated` global, lo cual asegura que solo los estudiantes/docentes verificados puedan enviar feedback.

4. **Transaccionalidad y Sobre de Respuesta**:
   El guardado se protegió dentro de `transaction.atomic()` y las salidas (201 Created y 400 Bad Request) se forzaron a cruzar por la clase `RespuestaApi`, devolviendo el estricto formato `{"isSuccess": true|false, "message": "...", "data": ...}`.

## Validación y TDD

Se escribieron **4 pruebas clave** que aseguran la fiabilidad del endpoint a lo largo del tiempo:

| Prueba | Propósito | Resultado |
|---|---|---|
| `test_post_feedback_exitoso` | Verifica el camino feliz. El feedback se inserta y se asocia al usuario autenticado. | ✅ Pasó |
| `test_post_feedback_sin_autenticar` | Garantiza que se bloqueen peticiones anónimas (401). | ✅ Pasó |
| `test_post_datos_invalidos` | Verifica que el sobre de error (`isSuccess: false` + `errors`) se despache ante tipos inválidos o campos faltantes (400). | ✅ Pasó |
| `test_throttling_estricto` | Verifica que una tercera petición seguida del mismo usuario sea rechazada por DRF con un `429 Too Many Requests`. | ✅ Pasó |

## Cómo probar manualmente
Levanta el servidor:
```bash
python manage.py runserver
```
Y envía un payload con tu token JWT:
```bash
curl -X POST http://127.0.0.1:8000/api/v1.0.0/movil/feedback/ \
  -H "Authorization: Bearer <TU_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"tipo": "SUGERENCIA", "mensaje": "Por favor agreguen modo oscuro."}'
```
