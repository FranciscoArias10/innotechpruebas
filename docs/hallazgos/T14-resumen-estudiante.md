# T14 · Endpoint `GET /movil/representative/students/<id>/summary/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~8 h |
| **Rama** | `T14-summary` |
| **Material** | `openapi/representative_student_summary.yaml`, `app/views.py`, `app/urls.py`, `app/tests/test_representative_student_summary.py` |

## Qué se pedía

Implementar el endpoint `GET /api/v1.0.0/movil/representative/students/<id>/summary/` para que los representantes legales consulten las métricas consolidadas del tablero del estudiante (materias activas, porcentaje de asistencia, actividades pendientes, matrícula y periodo):
- Utiliza los datos del puerto `sige_ports.portal.resumen_estudiante(persona_id, periodo_id)`.
- Reutiliza el permiso de parentesco `EsRepresentanteDelEstudiante` (sin duplicar lógica de autorización).
- Requiere el header `X-Period-ID`.
- Mantiene la envoltura de respuesta estándar institucional `RespuestaApi` (`isSuccess`).

## Método

1. **Definición del Contrato (OpenAPI 3.0)**:
   Se documentó la ruta en `openapi/representative_student_summary.yaml` detallando los esquemas de matrícula, periodo, métricas y los códigos de respuesta (`200`, `400`, `401`, `403` y `404`).

2. **Reutilización del Permiso (`EsRepresentanteDelEstudiante`)**:
   Se vinculó directamente en la vista a través de `permission_classes = [IsAuthenticated, EsRepresentanteDelEstudiante]`, validando con `portal.representa_a()` antes de invocar la consulta de datos.

3. **Vista y Ruteo Django**:
   Se implementó `RepresentativeStudentSummaryView(APIView)` en `app/views.py`:
   - Validación del header `X-Period-ID` con retorno estructurado de errores (`400 Bad Request`).
   - Gestión de `LookupError` traduciéndolo a `404 Not Found` en caso de que el estudiante no tenga matrícula en el periodo.
   - Manejo de excepciones imprevistas traduciéndolas a `500 Internal Server Error` sin exponer trazas técnicas.
   - Integración de los datos en el sobre `RespuestaApi` (`200 OK`).
   - Registro del path en `app/urls.py`: `representative/students/<int:student_id>/summary/`.

4. **Pruebas Automatizadas (TDD)**:
   Se agregaron 7 pruebas unitarias en `app/tests/test_representative_student_summary.py` cubriendo camino feliz, verificación del sobre `isSuccess`, rechazo anónimo (401), validación de cabeceras (400), parentesco denegado con `mock.patch` (403), estudiante sin matrícula con `LookupError` (404) y fallos internos (500).

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/representative_student_summary.yaml` | Creado | ✅ Válido |
| Permiso | `EsRepresentanteDelEstudiante` | Reutilizado desde T11 | ✅ Válido |
| Vista | `RepresentativeStudentSummaryView` | Validada y conectada | ✅ Válido |
| Ruteo | `app/urls.py` | Asignado al path correcto | ✅ Válido |
| Pruebas (TDD) | 7 Pruebas unitarias dedicadas | 100% pasando (62/62 suite completa) | ✅ Válido |

## Verificación

```bash
# Ejecutar pruebas unitarias de resumen
python manage.py test app.tests.test_representative_student_summary

# Ejecutar suite completa
python manage.py test
```

### Ejemplo de Respuesta (HTTP 200 OK)

```json
{
  "isSuccess": true,
  "message": "Resumen académico recuperado con éxito.",
  "data": {
    "total_subjects": 8,
    "attendance_percentage": 95.5,
    "pending_activities": 3,
    "enrollment": {
      "id": 9876,
      "level": "OCTAVO AÑO DE EDUCACIÓN GENERAL BÁSICA",
      "level_alias": "8vo EGB",
      "parallel": "A"
    },
    "period": {
      "id": 6,
      "name": "PERIODO LECTIVO 2024 - 2025"
    }
  }
}
```
