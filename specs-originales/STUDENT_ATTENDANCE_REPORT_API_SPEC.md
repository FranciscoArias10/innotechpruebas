# Student Attendance Report API

## Endpoint

```
GET /api/v1_0_0/student/attendance/report/
```

## Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | Bearer token |
| `X-Period-ID` | Yes | Academic period ID |

## Response Structure

```json
{
  "isSuccess": true,
  "data": {
    "student": { "id": 123, "full_name": "Juan Pérez" },
    "period": { "id": 1, "name": "2025-2026" },
    "evaluative_items": [...],
    "summary": {...},
    "subjects": [
      {
        "materia_asignada_id": 456,
        "subject_id": 789,
        "cronograma_id": 10,
        "name": "LENGUA Y LITERATURA",
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
        "by_item": [...],
        "status": "excelente"
      }
    ]
  }
}
```

## Attendance Fields

### `by_hours` (por hora/lección)

| Field | Type | Description |
|-------|------|-------------|
| `attended` | int | Horas con asistencia marcada (asistio=True) |
| `justified` | int | Horas con falta justificada aprobada |
| `pending` | int | Horas sin registro de asistencia |
| `absent` | int | Horas con falta injustificada |
| `total` | int | Total de horas/lecciones |
| `percentage` | float | **(attended + justified) / total * 100** |

### `by_days` (por día)

| Field | Type | Description |
|-------|------|-------------|
| `attended` | int | Días con al menos una asistencia |
| `justified` | int | Días con justificación aprobada |
| `pending` | int | Días sin registro |
| `absent` | int | Días con falta injustificada |
| `total` | int | Total de días con clase |
| `percentage` | float | **(attended + justified) / total * 100** |

## Percentage Calculation

> **IMPORTANTE**: Las faltas justificadas aprobadas cuentan como asistencia en el porcentaje.

```python
# Fórmula
percentage = (attended + justified) / total * 100
```

Ejemplo:
- attended: 45, justified: 3, absent: 2, total: 50
- percentage = (45 + 3) / 50 * 100 = **96.0%**

## Justified Absences

Una falta se considera justificada cuando:
1. Existe en `JustificacionAsistenciaDetalle`
2. La `JustificacionAsistencia` tiene `estado=3` (aprobada)

```python
lecciones_justificadas = JustificacionAsistenciaDetalle.objects.filter(
    justificacionamateriaasignada__materiaasignada=ma,
    justificacionamateriaasignada__justificacionasistencia__estado=3,
    asistencialeccion__leccion_id__in=[...]
).values_list('asistencialeccion__leccion_id', flat=True)
```

## Priority Logic

Prioridad para clasificar cada hora/día:
1. **Justificada** → cuenta como asistencia
2. **Presente** (asistio=True) → asistencia
3. **Falta** (asistio=False) → falta injustificada
4. **Pendiente** → sin registro

## Status Values

| Value | Condition |
|-------|-----------|
| `sin_datos` | total = 0 |
| `excelente` | ≥ 95% |
| `buena` | 85-94% |
| `regular` | 70-84% |
| `baja` | < 70% |

## Error Responses

| Status | Condition |
|--------|-----------|
| 400 | Missing `X-Period-ID` |
| 403 | No access to period |
| 404 | No enrollment found |
| 500 | Server error |
