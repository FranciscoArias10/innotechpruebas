# T12 · Endpoint `GET /movil/representative/students/<id>/attendance/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~8 h |
| **Rama** | `T12-attendance` |
| **Material** | `openapi/representative_student_attendance.yaml`, `app/views.py`, `app/urls.py`, `app/tests/test_representative_student_attendance.py` |

## Qué se pedía

Implementar el endpoint `GET /api/v1.0.0/movil/representative/students/<id>/attendance/` para que los representantes de familia puedan visualizar el resumen de asistencia de un estudiante:
- Utiliza los datos del sistema real a través del puerto `sige_ports.portal.asistencia_de_estudiante(persona_id, periodo_id)`.
- Reutilizar el permiso de parentesco `EsRepresentanteDelEstudiante` (T11).
- Requiere el header obligatorio `X-Period-ID` para especificar el periodo lectivo.
- Respuestas estandarizadas con la envolvente institucional `RespuestaApi` (`isSuccess`).

## Método

1. **Definición del Contrato (OpenAPI 3.0)**:
   Se creó `openapi/representative_student_attendance.yaml` formalizando los parámetros de Header (`X-Period-ID`), Path (`student_id`), y los esquemas de respuesta para `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden` y `404 Not Found`.

2. **Reutilización del Permiso (`EsRepresentanteDelEstudiante`)**:
   Tal como se planeó, **no se duplicó lógica**. Se reutilizó el permiso desarrollado en la T11 que verifica mediante `portal.representa_a()` que el estudiante pertenezca al usuario autenticado.

3. **Vista y Ruteo Django**:
   En `app/views.py` se construyó `RepresentativeStudentAttendanceView(APIView)`:
   - Aplica los permisos `[IsAuthenticated, EsRepresentanteDelEstudiante]`.
   - Valida la presencia y conversión a entero de `X-Period-ID`.
   - Llama al puerto `asistencia_de_estudiante(persona_id=student_id, periodo_id=periodo_id)`.
   - Toda salida (200, 400, 404, 500) pasa por la clase envoltura `RespuestaApi` para el control de `isSuccess`.

4. **Pruebas Automatizadas (TDD)**:
   Se implementaron 7 pruebas dedicadas en `app/tests/test_representative_student_attendance.py` cubriendo:
   - Camino feliz: respuesta `200 OK` validando la estructura del JSON.
   - Restricción por ausencia o mal formato de `X-Period-ID` (`400 Bad Request`).
   - Bloqueo de peticiones no autenticadas (`401 Unauthorized`).
   - Caso denegado obligatorio simulado con `mock.patch` sobre `representa_a` (`403 Forbidden`).
   - Reporte de puerto vacío capturando `LookupError` (`404 Not Found`).
   - Prueba de Idempotencia.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/representative_student_attendance.yaml` | Creado | ✅ Válido |
| Vista | `RepresentativeStudentAttendanceView` | Validada y conectada | ✅ Válido |
| Ruteo | `app/urls.py` | Asignado al parámetro path | ✅ Válido |
| Pruebas (TDD) | 7 Pruebas unitarias dedicadas | 100% pasando | ✅ Válido |

## Verificación

```bash
# Ejecutar pruebas unitarias específicas de asistencia
python manage.py test app.tests.test_representative_student_attendance
```

### Ejemplo de Petición y Respuesta

**GET `/api/v1.0.0/movil/representative/students/4412/attendance/`**
```json
// Headers:
// Authorization: Bearer <token>
// X-Period-ID: 6
```

**Respuesta (HTTP 200 OK):**
```json
{
    "isSuccess": true,
    "message": "Asistencia recuperada con éxito.",
    "data": {
        "subjects": [
            {
                "cronograma_id": 101,
                "name": "LENGUA Y LITERATURA",
                "by_hours": {
                    "attended": 35,
                    "justified": 2,
                    "pending": 1,
                    "absent": 2,
                    "total": 40,
                    "percentage": 92.5
                },
                "by_days": {
                    "attended": 35,
                    "justified": 2,
                    "pending": 1,
                    "absent": 2,
                    "total": 40,
                    "percentage": 92.5
                },
                "status": "excelente"
            }
        ]
    }
}
```

**Respuesta sin parentesco (HTTP 403 Forbidden):**
```json
{
    "isSuccess": false,
    "message": "No tiene permiso para acceder a la información de este estudiante.",
    "errors": {}
}
```
