# T3 · Formalizar las 11 especificaciones OpenAPI restantes

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~4 h |
| **Rama** | `T03-openapi-specs` |
| **Material** | `openapi/` (11 contratos YAML + script bundle) |

## Qué se pedía

Formalizar las 11 especificaciones OpenAPI 3.0.3 restantes del sistema (Estudiante, Docente, Configuración, Calendario y ChatIA) en formato YAML dentro de la carpeta `openapi/`, garantizando que compartan el sobre de respuesta estandarizado `isSuccess`.

## Método

1. **Creación de los 11 Contratos YAML**:
   Se crearon los archivos OpenAPI 3.0.3 correspondientes a cada módulo:
   - `student_summary.yaml`: `GET /student/summary/`
   - `student_subjects.yaml`: `GET /student/subjects/`
   - `subject_grades.yaml`: `GET /student/subjects/{materia_asignada_id}/grades/`
   - `student_attendance.yaml`: `GET /student/attendance/report/`
   - `subject_classmates.yaml`: `GET /student/subjects/{materia_asignada_id}/classmates/`
   - `class_planning.yaml`: `GET /student/subjects/{materia_asignada_id}/planning/`
   - `calendar.yaml`: `GET /student/calendar/` y `GET /student/activity/{id}/`
   - `subject_students_teacher.yaml`: `GET /teacher/subjects/{materia_id}/students/`
   - `branding_config.yaml`: `GET /config/branding/`
   - `chatia_public_config.yaml`: `GET /chat-ia/config/`
   - `chatia_session_management.yaml`: `GET/PATCH/DELETE /chat-ia/sessions/`

2. **Estandarización del Sobre (`isSuccess`)**:
   En todos los contratos se definió el sobre reutilizable `components/schemas/Sobre` utilizando `isSuccess: true` y estructurando las respuestas exitosas con `allOf`.

3. **Script Empaquetador (`scripts/bundle_openapi.py`)**:
   Se desarrolló una herramienta en Python para fusionar limpiamente las 20 rutas de la API en un único archivo `openapi/openapi.yaml` sin conflictos de esquemas.

## Resultado

| Archivo YAML | Módulo | Rutas Incluidas | Sobre Usado | Veredicto |
|---|---|---|---|---|
| `student_summary.yaml` | Estudiante | `GET /student/summary/` | `isSuccess` | ✅ Válido |
| `student_subjects.yaml` | Estudiante | `GET /student/subjects/` | `isSuccess` | ✅ Válido |
| `subject_grades.yaml` | Estudiante | `GET /student/subjects/{id}/grades/` | `isSuccess` | ✅ Válido |
| `student_attendance.yaml` | Estudiante | `GET /student/attendance/report/` | `isSuccess` | ✅ Válido |
| `subject_classmates.yaml` | Estudiante | `GET /student/subjects/{id}/classmates/` | `isSuccess` | ✅ Válido |
| `class_planning.yaml` | Estudiante | `GET /student/subjects/{id}/planning/` | `isSuccess` | ✅ Válido |
| `calendar.yaml` | Calendario | `GET /student/calendar/`, `GET /student/activity/{id}/` | `isSuccess` | ✅ Válido |
| `subject_students_teacher.yaml` | Docente | `GET /teacher/subjects/{id}/students/` | `isSuccess` | ✅ Válido |
| `branding_config.yaml` | Configuración | `GET /config/branding/` | `isSuccess` | ✅ Válido |
| `chatia_public_config.yaml` | ChatIA | `GET /chat-ia/config/` | `isSuccess` | ✅ Válido |
| `chatia_session_management.yaml` | ChatIA | `GET/PATCH/DELETE /chat-ia/sessions/` | `isSuccess` | ✅ Válido |

## Verificación

Se verificó el cumplimiento mediante tres pruebas automáticas reproducibles:

```bash
# 1. Validación sintáctica de los 12 archivos
for f in openapi/*.yaml; do ./venv/bin/python -c "import yaml; yaml.safe_load(open('$f'))" && echo "$f -> OK"; done

# 2. Empaquetado de las 20 rutas en openapi/openapi.yaml
./venv/bin/python scripts/bundle_openapi.py

# 3. Renderizado de la documentación completa con Redocly
npx @redocly/cli build-docs openapi/openapi.yaml -o docs_completo.html
```

Todos los contratos validan correctamente y generan la documentación OpenAPI 3.0 completa de la API móvil.
