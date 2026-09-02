# T11 · Endpoint `GET /representative/students/<id>/grades/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~10 h |
| **Rama** | `T11-representative-student-grades` |
| **Material** | `openapi/representative_student_grades.yaml`, `app/permissions.py`, `app/views.py`, `app/urls.py`, `app/tests/test_representative_student_grades.py` |

## Qué se pedía

Implementar el endpoint `GET /api/v1.0.0/movil/representative/students/<id>/grades/` para que los representantes de familia puedan visualizar las calificaciones detalladas de una asignatura de los estudiantes bajo su representación:
- Utiliza los datos del sistema real a través de los puertos en `sige_ports.portal`.
- Verificación de parentesco mediante `portal.representa_a(persona_id, estudiante_id)`. Si no representa al estudiante, debe retornar `403 Forbidden`.
- Requiere el header obligatorio `X-Period-ID` para especificar el periodo lectivo.
- Requiere el parámetro de consulta `materia_asignada_id` para identificar la asignatura.
- Extraer la lógica de verificación de parentesco a un permiso de DRF reutilizable (`EsRepresentanteDelEstudiante`) para las tareas T11 a T14.
- Respuestas estandarizadas con la envolvente institucional `RespuestaApi` (`isSuccess`).

## Método

1. **Definición del Contrato (OpenAPI 3.0)**:
   Se creó `openapi/representative_student_grades.yaml` formalizando los parámetros de Header (`X-Period-ID`), Path (`student_id`), Query (`materia_asignada_id`) y los esquemas de respuesta para `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found` y `500 Internal Server Error`.

2. **Permiso Reutilizable (`EsRepresentanteDelEstudiante`)**:
   Se implementó en `app/permissions.py` heredando de `BasePermission`. Extrae el `student_id` de la URL y valida con `portal.representa_a(persona_id=request.user.id, estudiante_id=student_id)`. Si es `False`, DRF detiene la ejecución y devuelve `403 Forbidden`.

3. **Vista y Ruteo Django**:
   En `app/views.py` se construyó `RepresentativeStudentGradesView(APIView)`:
   - Aplica los permisos `[IsAuthenticated, EsRepresentanteDelEstudiante]`.
   - Valida la presencia y conversión a entero de `X-Period-ID` y `materia_asignada_id`.
   - Consume `portal.notas_de_estudiante(persona_id=student_id, periodo_id=periodo_id, materia_asignada_id=materia_asignada_id)`.
   - Captura `LookupError` del puerto devolviendo `404 Not Found`.
   - Registrado en `app/urls.py` bajo el nombre `'movil-representative-student-grades'`.

4. **Pruebas Automatizadas (TDD)**:
   Se implementaron 8 pruebas en `app/tests/test_representative_student_grades.py` cubriendo:
   - Camino feliz: Retorno de notas de estudiante con `isSuccess: true` (`200 OK`).
   - Verificación de envolvente: Presencia de `isSuccess` y ausencia de `success`.
   - Encabezado `X-Period-ID` faltante o no numérico (`400 Bad Request`).
   - Parámetro `materia_asignada_id` faltante o no entero (`400 Bad Request`).
   - Solicitud sin autenticación (`401 Unauthorized`).
   - Verificación de parentesco denegado mediante `mock.patch('sige_ports.portal.representa_a', return_value=False)` (`403 Forbidden`).
   - Materia no encontrada o no asignada (`404 Not Found`).
   - Idempotencia en solicitudes consecutivas.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/representative_student_grades.yaml` | Creado | ✅ Válido |
| Permiso | `EsRepresentanteDelEstudiante` en `app/permissions.py` | Implementado y Reutilizable | ✅ Válido |
| Vista | `RepresentativeStudentGradesView` en `app/views.py` | Creado con validación e integración a puertos | ✅ Válido |
| Ruteo | `representative/students/<int:student_id>/grades/` | Registrado en `app/urls.py` | ✅ Válido |
| Pruebas (TDD) | 8 pruebas unitarias dedicadas | 100% pasando (41/41 suite completa) | ✅ Válido |

## Verificación

Para verificar que la entrega está correcta, se ejecutan las pruebas automatizadas del proyecto:

```bash
# 1. Pruebas dedicadas de T11
venv/bin/python manage.py test app.tests.test_representative_student_grades

# 2. Suite completa de la aplicación (41 pruebas)
venv/bin/python manage.py test
```

### Ejemplo de Petición y Respuesta

**GET `/api/v1.0.0/movil/representative/students/4412/grades/?materia_asignada_id=123`**

```http
Authorization: Bearer <token>
X-Period-ID: 6
```

**Respuesta de Éxito (HTTP 200 OK):**

```json
{
  "isSuccess": true,
  "message": "Notas recuperadas con éxito.",
  "data": {
    "subject": {
      "id": 123,
      "name": "MATEMÁTICA",
      "level": "1ro BGU",
      "parallel": "A",
      "start_date": "2025-09-01",
      "end_date": "2026-06-30",
      "total_weeks": 40,
      "pending_activities": 5
    },
    "evaluation_model": {
      "id": 1,
      "name": "Modelo Evaluativo Bachillerato",
      "is_quantitative": true,
      "items": [...]
    }
  }
}
```

**Respuesta de Permiso Denegado (HTTP 403 Forbidden):**

```json
{
  "detail": "No tiene permiso para acceder a la información de este estudiante."
}
```
