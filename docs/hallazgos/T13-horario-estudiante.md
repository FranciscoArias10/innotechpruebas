# T13 · Endpoint `GET /movil/representative/students/<id>/schedule/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~8 h |
| **Rama** | `T13-schedule` |
| **Material** | `openapi/representative_student_schedule.yaml`, `app/views.py`, `app/urls.py`, `app/tests/test_representative_student_schedule.py` |

## Qué se pedía

Implementar el endpoint `GET /api/v1.0.0/movil/representative/students/<id>/schedule/` para que los representantes visualicen el horario semanal de clases de los estudiantes a su cargo:
- Utiliza los datos de `sige_ports.portal.horario_de_estudiante(persona_id, periodo_id)`.
- Reutiliza el permiso de parentesco `EsRepresentanteDelEstudiante`.
- Requiere `X-Period-ID`.
- Mantiene la envoltura de respuesta estándar institucional `RespuestaApi`.

## Método

1. **Definición del Contrato (OpenAPI 3.0)**:
   Se documentó la ruta en `openapi/representative_student_schedule.yaml`, mapeando la estructura anidada del puerto (`turnos`, `dias`, `clases`, y `dias_visibles`).

2. **Reutilización del Permiso (`EsRepresentanteDelEstudiante`)**:
   Aplicado de forma idéntica a las T11 y T12, demostrando que la lógica de validación de `portal.representa_a()` está completamente desacoplada y lista para usarse modularmente.

3. **Vista y Ruteo Django**:
   Se construyó `RepresentativeStudentScheduleView(APIView)` en `app/views.py`:
   - Validaciones de tipo y presencia de cabeceras (`400 Bad Request`).
   - Gestión de excepciones (`LookupError` mapeado a `404 Not Found`).
   - Envío de los datos extraídos de `portal.horario_de_estudiante` al objeto `RespuestaApi` (`200 OK`).

4. **Pruebas Automatizadas (TDD)**:
   Se añadieron 7 pruebas unitarias nuevas en `app/tests/test_representative_student_schedule.py`, garantizando la correcta ejecución y la protección de los datos. Destaca la prueba mediante `mock.patch` sobre el puerto que simula una consulta de un padre sin parentesco para afirmar que DRF lanza un `403 Forbidden`.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/representative_student_schedule.yaml` | Creado | ✅ Válido |
| Vista | `RepresentativeStudentScheduleView` | Validada y conectada | ✅ Válido |
| Ruteo | `app/urls.py` | Asignado al path correcto | ✅ Válido |
| Pruebas (TDD) | 7 Pruebas unitarias dedicadas | 100% pasando | ✅ Válido |

## Verificación

```bash
# Ejecutar pruebas unitarias específicas de horario
python manage.py test app.tests.test_representative_student_schedule
```

### Ejemplo de Respuesta (HTTP 200 OK)

```json
{
  "isSuccess": true,
  "message": "Horario recuperado con éxito.",
  "data": {
    "turnos": [
      {
        "id": 1,
        "nombre": "MATUTINO JARDIN",
        "nombre_corto": "MAT JAR",
        "aplica_asistencia": true,
        "dias": [
          {
            "indice": 1,
            "nombre": "Lunes",
            "clases": [
              {
                "nombre": "EXPRESIÓN CORPORAL",
                "paralelo": "A",
                "aula": "Aula 23",
                "profesor": "LOURDES PERERO",
                "fecha_inicio": "2025-05-01",
                "fecha_fin": "2026-02-28",
                "color": "#4287f5"
              }
            ]
          }
        ]
      }
    ],
    "dias_visibles": [
      {
        "indice": 6,
        "nombre": "Sábado",
        "clases": []
      },
      {
        "indice": 7,
        "nombre": "Domingo",
        "clases": []
      }
    ]
  }
}
```
