# Student Subject Grades API

Endpoint para obtener las calificaciones detalladas de una materia específica para un estudiante.  
Replica exactamente la estructura jerárquica de `calificacion.html` para aplicaciones móviles.

---

## Endpoint

```
GET /api/v1_0_0/student/subjects/{materia_asignada_id}/grades/
```

---

## Request

### Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `Authorization` | string | ✅ | Token JWT: `Bearer <token>` |
| `X-Period-ID` | integer | ✅ | ID del periodo académico |

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `materia_asignada_id` | integer | ✅ | ID de la materia asignada al estudiante |

### Example Request

```bash
curl -X GET "http://localhost:8000/api/v1_0_0/student/subjects/123/grades/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "X-Period-ID: 1"
```

---

## Response

### Success Response (200 OK)

```json
{
  "isSuccess": true,
  "data": {
    "subject": {
      "id": 123,
      "name": "Matemáticas",
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
      "items": [
        {
          "id": 10,
          "name": "1er Quimestre",
          "alias": "Q1",
          "max_score": 10,
          "total_percentage": 50,
          "grade": 8.75,
          "grade_letter": null,
          "grading_books": [
            {
              "id": 20,
              "name": "Parcial 1",
              "percentage": 33.33,
              "grade": 8.5,
              "grade_letter": null,
              "categories": [
                {
                  "id": 30,
                  "name": "Tareas",
                  "percentage": 40,
                  "grade": 9.0,
                  "grade_letter": null,
                  "activities": [
                    {
                      "id": 100,
                      "name": "Tarea 1 - Ecuaciones",
                      "type": {
                        "id": 1,
                        "name": "Tarea",
                        "icon_url": "http://localhost:8000/static/icons/tarea.png"
                      },
                      "grade": 9.5,
                      "grade_letter": null,
                      "grading_status": "graded"
                    },
                    {
                      "id": 101,
                      "name": "Tarea 2 - Funciones",
                      "type": {
                        "id": 1,
                        "name": "Tarea",
                        "icon_url": "http://localhost:8000/static/icons/tarea.png"
                      },
                      "grade": null,
                      "grade_letter": null,
                      "grading_status": "pending"
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    "final_grade": 8.25,
    "final_grade_letter": null,
    "status": {
      "code": "approved",
      "label": "Aprobado",
      "severity": "success"
    },
    "grades_visible": true,
    "grades_blocked": false,
    "block_message": null,
    "info_message": null
  }
}
```

### Grades Not Visible Response (200 OK)

Cuando `periodo.visiblenota = false`:

```json
{
  "isSuccess": true,
  "data": {
    "subject": { ... },
    "evaluation_model": null,
    "final_grade": null,
    "final_grade_letter": null,
    "status": null,
    "grades_visible": false,
    "grades_blocked": false,
    "block_message": null,
    "info_message": {
      "title": "Calificaciones no disponibles",
      "description": "Las calificaciones no están habilitadas para visualización en este periodo."
    }
  }
}
```

### Grades Blocked Response (200 OK)

Cuando existe un bloqueo de visualización de calificaciones (`BloqVistaNivel`):

```json
{
  "isSuccess": true,
  "data": {
    "subject": { ... },
    "evaluation_model": null,
    "final_grade": null,
    "final_grade_letter": null,
    "status": null,
    "grades_visible": true,
    "grades_blocked": true,
    "block_message": {
      "title": "Bloqueo de Calificaciones",
      "description": "Las calificaciones están bloqueadas temporalmente..."
    },
    "info_message": null
  }
}
```

---

## Response Fields

### Root Level

| Field | Type | Description |
|-------|------|-------------|
| `subject` | object | Información de la materia |
| `evaluation_model` | object \| null | Modelo evaluativo con estructura jerárquica |
| `final_grade` | number \| null | Nota final de la materia |
| `final_grade_letter` | string \| null | Nota final en letra (escalas cualitativas) |
| `status` | object \| null | Estado de aprobación de la materia |
| `grades_visible` | boolean | Si las notas son visibles según configuración del periodo |
| `grades_blocked` | boolean | Si existe bloqueo de calificaciones para el nivel |
| `block_message` | object \| null | Mensaje de bloqueo si aplica |
| `info_message` | object \| null | Mensaje informativo si aplica (ej: notas no visibles) |

### Subject Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | ID de MateriaAsignada |
| `name` | string | Nombre de la asignatura |
| `level` | string | Nivel académico |
| `parallel` | string | Paralelo |
| `start_date` | string \| null | Fecha de inicio (ISO 8601) |
| `end_date` | string \| null | Fecha de fin (ISO 8601) |
| `total_weeks` | integer | Total de semanas de planificación |
| `pending_activities` | integer | Actividades pendientes |

### Activity Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | ID de la actividad |
| `name` | string | Nombre de la actividad |
| `type` | object | Tipo de actividad |
| `grade` | number \| null | Nota obtenida (null si no calificada) |
| `grade_letter` | string \| null | Nota en letra |
| `grading_status` | string | Estado: `graded` \| `pending` |

### Type Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer \| null | ID del tipo de recurso |
| `name` | string | Nombre del tipo |
| `icon_url` | string \| null | **URL absoluta** del icono |

### Status Object

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Código semántico: `approved`, `pending`, `failed` |
| `label` | string | Etiqueta para UI: "Aprobado", "Pendiente", "Reprobado" |
| `severity` | string | Nivel de severidad UI: `success`, `warning`, `danger` |

> **Nota**: `severity` es un valor semántico para UI, no una clase CSS. Mapear a estilos en el cliente.

---

## Error Responses

### 400 Bad Request

```json
{
  "isSuccess": false,
  "message": "Header X-Period-ID es requerido"
}
```

### 403 Forbidden

```json
{
  "isSuccess": false,
  "message": "Periodo inválido"
}
```

### 404 Not Found

```json
{
  "isSuccess": false,
  "message": "Materia no encontrada o sin acceso"
}
```

### 500 Internal Server Error

```json
{
  "isSuccess": false,
  "message": "Error al obtener calificaciones"
}
```

---

## Data Structure Hierarchy

```
evaluation_model
└── items[] (Quimestres/Períodos)
    └── grading_books[] (Parciales)
        └── categories[] (Tareas, Talleres, Exámenes)
            └── activities[] (Actividades individuales)
```

---

## Important Notes

### Null Grades
- `grade: null` indica que la actividad/categoría/ítem no tiene calificación asignada
- Usar `grading_status` para determinar si está pendiente o calificada
- No usar `grade == 0` para verificar pendientes (0 puede ser una nota válida)

### Absolute URLs
- `icon_url` siempre es URL absoluta (incluye dominio)
- Listo para uso directo en móvil sin concatenación

### Security
- Valida que `materia_asignada_id` pertenece al estudiante autenticado
- Valida que el estudiante tiene acceso al periodo solicitado
- Mensaje genérico "Materia no encontrada o sin acceso" para evitar enumeración
