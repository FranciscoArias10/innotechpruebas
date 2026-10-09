# Documentacion de Endpoints - Fase 1 (Portal Estudiantil)

Guia de referencia de los endpoints implementados para la aplicacion movil UNIEBEC.
Todos los endpoints requieren autenticacion JWT mediante cabecera `Authorization: Bearer <access_token>` y el identificador de periodo lectivo mediante cabecera `X-Period-ID: <id>`.

---

## Formato Estandar de Respuesta (`RespuestaApi`)

Todas las respuestas cumplen la envolvente institucional:

### Exito (HTTP 200 / 201)
```json
{
  "isSuccess": true,
  "message": "Mensaje explicativo del resultado",
  "data": { ... }
}
```

### Error de Validacion (HTTP 400 Bad Request)
```json
{
  "isSuccess": false,
  "message": "Header X-Period-ID es requerido.",
  "errors": {
    "X-Period-ID": ["Este header es obligatorio para consultar los datos del estudiante."]
  }
}
```

---

## 1. Resumen Academico

- **URL:** `GET /api/v1.0.0/movil/student/summary/` (o `/api/v1.0.0/student/summary/`)
- **Headers:**
  - `Authorization: Bearer <token>` (Obligatorio)
  - `X-Period-ID: <id>` (Obligatorio, entero)
- **Descripcion:** Resumen para el dashboard principal (materias matriculadas, asistencia general, actividades pendientes y datos de matricula).
- **Ejemplo Respuesta 200 OK:**
```json
{
  "isSuccess": true,
  "message": "Resumen academico recuperado con exito.",
  "data": {
    "total_subjects": 11,
    "attendance_percentage": 95.5,
    "pending_activities": 0,
    "enrollment": {
      "id": 21,
      "level": "DECIMO DE BASICA",
      "level_alias": "10MO DE BASICA",
      "parallel": "A"
    },
    "period": {
      "id": 2,
      "name": "ACADEMICO"
    }
  }
}
```

---

## 2. Mis Asignaturas

- **URL:** `GET /api/v1.0.0/movil/student/subjects/`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `X-Period-ID: <id>`
- **Descripcion:** Lista de asignaturas matriculadas en el periodo seleccionado con color representativo, docente y nota final.
- **Ejemplo Respuesta 200 OK:**
```json
{
  "isSuccess": true,
  "message": "Asignaturas recuperadas con exito.",
  "data": {
    "subjects": [
      {
        "materia_asignada_id": 254,
        "materia_id": 686,
        "name": "LENGUAJE",
        "color": "#90268f",
        "level": "DECIMO DE BASICA",
        "parallel": "A",
        "final_grade": 8.5,
        "attendance_percentage": 96.0,
        "teacher": "MARIA CAMILA INTRIAGO",
        "pending_activities": 0
      }
    ]
  }
}
```

---

## 3. Calificaciones Generales

- **URL:** `GET /api/v1.0.0/movil/student/grades/`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `X-Period-ID: <id>`
- **Descripcion:** Listado de calificaciones finales y estado por asignatura para el periodo activo.
- **Ejemplo Respuesta 200 OK:**
```json
{
  "isSuccess": true,
  "message": "Calificaciones recuperadas con exito.",
  "data": {
    "periodo_id": 2,
    "calificaciones": [
      {
        "materia_asignada_id": 254,
        "materia_nombre": "LENGUAJE",
        "color": "#90268f",
        "profesor": "MARIA CAMILA INTRIAGO",
        "nota_final": 8.5,
        "estado": "aprobado",
        "asistencia_porcentaje": 96.0
      }
    ]
  }
}
```

---

## 4. Detalle de Calificaciones por Asignatura

- **URL:** `GET /api/v1.0.0/movil/student/subjects/<materia_asignada_id>/grades/`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `X-Period-ID: <id>`
- **Descripcion:** Desglose evaluativo de quimestres, parciales y actividades de una asignatura.
- **Ejemplo Respuesta 200 OK:**
```json
{
  "isSuccess": true,
  "message": "Detalle de calificaciones recuperado con exito.",
  "data": {
    "subject": {
      "id": 254,
      "name": "LENGUAJE",
      "level": "DECIMO DE BASICA",
      "parallel": "A",
      "start_date": "2026-09-20",
      "end_date": "2027-03-15",
      "total_weeks": 40,
      "pending_activities": 0
    },
    "evaluation_model": {
      "id": 6,
      "name": "Modelo Evaluativo Institucional",
      "is_quantitative": true,
      "items": [
        {
          "id": 1,
          "name": "PRIMER BIMESTRE",
          "alias": "PB",
          "max_score": 10.0,
          "total_percentage": 50.0,
          "grade": 8.5,
          "grade_letter": null,
          "grading_books": []
        }
      ]
    }
  }
}
```

---

## 5. Reporte de Asistencia

- **URL:** `GET /api/v1.0.0/movil/student/attendance/` (o `/api/v1.0.0/movil/student/attendance/report/`)
- **Headers:**
  - `Authorization: Bearer <token>`
  - `X-Period-ID: <id>`
- **Descripcion:** Metricas de asistencia acumuladas (horas asistidas, faltas justificadas, injustificadas, atrasos y porcentaje).
- **Ejemplo Respuesta 200 OK:**
```json
{
  "isSuccess": true,
  "message": "Reporte de asistencia recuperado con exito.",
  "data": {
    "subjects": [
      {
        "cronograma_id": 254,
        "name": "LENGUAJE",
        "by_hours": {
          "attended": 45,
          "justified": 3,
          "pending": 0,
          "absent": 2,
          "total": 50,
          "percentage": 96.0
        },
        "by_days": {
          "attended": 30,
          "justified": 2,
          "pending": 0,
          "absent": 1,
          "total": 33,
          "percentage": 96.9
        },
        "status": "excelente"
      }
    ]
  }
}
```

---

## 6. Horario Semanal

- **URL:** `GET /api/v1.0.0/movil/student/schedule/`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `X-Period-ID: <id>`
- **Descripcion:** Grilla semanal de clases del estudiante organizada por turnos y dias con aula, profesor y color.
- **Ejemplo Respuesta 200 OK:**
```json
{
  "isSuccess": true,
  "message": "Horario de clases recuperado con exito.",
  "data": {
    "turnos": [
      {
        "id": 19,
        "nombre": "CLASE 3 - ASINCRONA",
        "nombre_corto": "3",
        "aplica_asistencia": false,
        "dias": [
          {
            "indice": 0,
            "nombre": "LUNES",
            "clases": [
              {
                "nombre": "LENGUAJE",
                "paralelo": "A",
                "aula": "Aula Virtual",
                "profesor": "MARIA CAMILA INTRIAGO",
                "inicio": "2026-09-21",
                "fin": "2027-03-11",
                "color": "#90268f"
              }
            ]
          }
        ]
      }
    ],
    "dias_visibles": [
      {"indice": 1, "nombre": "LUNES", "clases": []},
      {"indice": 2, "nombre": "MARTES", "clases": []},
      {"indice": 3, "nombre": "MIERCOLES", "clases": []},
      {"indice": 4, "nombre": "JUEVES", "clases": []},
      {"indice": 5, "nombre": "VIERNES", "clases": []}
    ]
  }
}
```