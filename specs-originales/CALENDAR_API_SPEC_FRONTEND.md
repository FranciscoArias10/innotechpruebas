# 📱 Especificación Técnica: Calendario de Actividades Académicas

**Versión:** 1.1  
**Fecha:** 2025-12-09  
**Autor:** Backend Team  
**Para:** Equipo Frontend/Mobile  

---

## Resumen Ejecutivo

Se ha implementado un nuevo módulo de **Calendario de Actividades Académicas** en la API REST del SIGE. Este módulo permite a los estudiantes consultar sus tareas, exámenes y actividades pendientes a través de la aplicación móvil.

---

## Endpoints Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1.0.0/student/calendar/` | GET | Lista de actividades (agenda/mes/semana) |
| `/api/v1.0.0/student/activity/<id>/` | GET | Detalle de una actividad específica |

---

## 1. Endpoint: Calendario de Actividades

### `GET /api/v1.0.0/student/calendar/`

#### Headers Requeridos

```http
Authorization: Bearer <access_token>
```

#### Headers Opcionales

```http
X-Period-ID: <period_id>
```

#### Query Parameters

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `period_id` | integer | No | - | ID del periodo lectivo (prioridad sobre header) |
| `view` | string | No | `agenda` | Tipo de vista: `agenda`, `month`, `week` |
| `date` | string | No | Fecha actual | Fecha de referencia ISO 8601 (ej: `2025-12-01`) |
| `subject_id` | integer | No | - | Filtrar por materia específica |

> **Prioridad del periodo:** `period_id` (query) → `X-Period-ID` (header) → periodo activo del estudiante

#### Vistas Disponibles

| Vista | Rango | Límite | Uso Recomendado |
|-------|-------|--------|-----------------|
| `agenda` | Próximos 30 días | 50 actividades | **Vista por defecto**. Lista scrollable de próximas actividades |
| `month` | Primer al último día del mes | Sin límite | Calendario mensual con indicadores por día |
| `week` | Lunes a domingo de la semana | Sin límite | Vista semanal con horarios |

#### Ejemplo de Request

```bash
# Vista agenda (default)
curl -X GET "https://sige.innotech-solutions.com.ec/api/v1.0.0/student/calendar/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "X-Period-ID: 6"

# Vista mensual para diciembre 2025
curl -X GET "https://sige.innotech-solutions.com.ec/api/v1.0.0/student/calendar/?view=month&date=2025-12-01" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."

# Filtrar por materia
curl -X GET "https://sige.innotech-solutions.com.ec/api/v1.0.0/student/calendar/?subject_id=45" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

#### Respuesta Exitosa (200)

```json
{
  "isSuccess": true,
  "message": "",
  "data": {
    "view": "agenda",
    "period": {
      "id": 6,
      "name": "PERIODO LECTIVO 2024 - 2025"
    },
    "range": {
      "start": "2025-12-09T00:00:00-05:00",
      "end": "2026-01-08T23:59:59-05:00"
    },
    "summary": {
      "total": 15,
      "pending": 5,
      "completed": 8,
      "overdue": 2
    },
    "activities": [
      {
        "id": 123,
        "title": "Tarea: Ejercicios de Matemáticas",
        "description": "Resolver ejercicios del capítulo 5...",
        "start": "2025-12-10T08:00:00-05:00",
        "end": "2025-12-15T23:59:00-05:00",
        "color": "#E57373",
        "type": {
          "id": 1,
          "name": "Tarea",
          "icon_url": "/media/icono/2024/01/tarea.svg"
        },
        "grading_type": "Cuantitativa",
        "delivery_type": "Permitir envío",
        "requires_submission": true,
        "grading_info": {
          "cohort": "PRIMER QUIMESTRE",
          "grading_book": "TAREAS",
          "category": "Trabajo individual"
        },
        "subject": {
          "id": 45,
          "name": "MATEMÁTICAS",
          "parallel": "A"
        },
        "status": {
          "code": "pending",
          "label": "Pendiente",
          "badge": "warning"
        },
        "submission": {
          "required": true,
          "submitted": false,
          "deadline_passed": false
        },
        "attachments": {
          "has_attachments": true,
          "count": 1
        },
        "links": {
          "has_links": false
        },
        "time_remaining": "5 días, 3 horas, 25 minutos y 10 segundos",
        "week_number": 12,
        "can_submit": true
      }
    ]
  }
}
```

---

## 2. Endpoint: Detalle de Actividad

### `GET /api/v1.0.0/student/activity/<id>/`

#### Headers Requeridos

```http
Authorization: Bearer <access_token>
```

#### Respuesta Exitosa (200)

```json
{
  "isSuccess": true,
  "message": "",
  "data": {
    "id": 123,
    "title": "Tarea: Ejercicios de Matemáticas",
    "description": "<p>Instrucciones completas en <strong>HTML</strong>...</p>",
    "start": "2025-12-10T08:00:00-05:00",
    "end": "2025-12-15T23:59:00-05:00",
    "type": {
      "id": 1,
      "name": "Tarea",
      "icon_url": "/media/icono/tarea.svg"
    },
    "grading_type": "Cuantitativa",
    "delivery_type": "Permitir envío",
    "requires_submission": true,
    "grading_info": {
      "cohort": "PRIMER QUIMESTRE",
      "grading_book": "TAREAS",
      "category": "Trabajo individual"
    },
    "subject": {
      "id": 45,
      "name": "MATEMÁTICAS",
      "parallel": "A"
    },
    "status": {
      "code": "pending",
      "label": "Pendiente",
      "badge": "warning"
    },
    "submission": {
      "required": true,
      "submitted": false,
      "deadline_passed": false,
      "history": []
    },
    "attachments": [
      {
        "id": 1,
        "name": "instrucciones.pdf",
        "type": "pdf",
        "url": "/media/adjuntoactividad/2025/01/instrucciones.pdf"
      }
    ],
    "links": [],
    "grade": null,
    "feedback": null,
    "time_remaining": "5 días, 3 horas, 25 minutos y 10 segundos",
    "week_number": 12,
    "can_submit": true
  }
}
```

---

## 3. Estructura de Datos

### Nuevos Campos (v1.1)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `grading_type` | string | Tipo de calificación: "Cuantitativa", "Cualitativa" |
| `delivery_type` | string | Tipo de entrega: "Permitir envío", "Sin envío", etc. |
| `requires_submission` | boolean | `true` si la actividad requiere entrega de archivo/texto |
| `grading_info` | object | Información del modelo evaluativo |

### Campo `grading_info`

```typescript
interface GradingInfo {
  cohort: string | null;       // Cohorte del modelo evaluativo (ej: "PRIMER QUIMESTRE")
  grading_book: string | null; // Libro de calificación (ej: "TAREAS")
  category: string | null;     // Categoría (ej: "Trabajo individual")
}
```

### Campo `status`

| `code` | `label` | `badge` | Descripción |
|--------|---------|---------|-------------|
| `pending` | Pendiente | `warning` | 🟡 Aún no entregada, dentro del plazo |
| `submitted` | Entregada | `info` | 🔵 Entregada, pendiente de calificación |
| `completed` | Calificada | `success` | 🟢 Calificada por el docente |
| `overdue` | Vencida | `danger` | 🔴 No entregada y plazo vencido |

### Campo `submission`

```typescript
interface Submission {
  required: boolean;        // Si requiere entrega de archivo/texto
  submitted: boolean;       // Si el estudiante ya realizó una entrega
  deadline_passed: boolean; // Si la fecha límite ya pasó
  history?: SubmissionHistory[]; // Solo en detalle: historial de entregas
}

interface SubmissionHistory {
  submitted_at: string;     // ISO 8601
  observation: string | null;
  file_name: string | null;
}
```

### Campo `summary` (solo en calendario)

```typescript
interface Summary {
  total: number;     // Total de actividades en el rango
  pending: number;   // Sin entregar, dentro del plazo
  completed: number; // Calificadas
  overdue: number;   // Vencidas sin entrega
}
```

---

## 4. Manejo de Errores

| HTTP | `isSuccess` | Caso | `message` |
|------|-------------|------|-----------|
| 400 | `false` | Vista no válida | `"Vista no válida. Use: agenda, month, week."` |
| 400 | `false` | Formato fecha inválido | `"Formato de fecha no válido. Use ISO 8601."` |
| 400 | `false` | Sin periodo activo | `"No se encontró un periodo lectivo activo para el estudiante."` |
| 401 | - | Sin token | Respuesta estándar DRF |
| 403 | `false` | Sin perfil estudiante | `"No tiene perfil de estudiante."` |
| 403 | `false` | Periodo no accesible | `"No tiene acceso al periodo."` |
| 403 | `false` | Materia no accesible | `"No tiene acceso a esta materia."` |
| 404 | `false` | Actividad no encontrada | `"Actividad no encontrada."` |

---

## 5. Recomendaciones de Implementación UI

### Vista Agenda (Default)

```
┌─────────────────────────────────────────┐
│  📊 Resumen                             │
│  ┌───────┬───────┬───────┬───────┐     │
│  │  15   │   5   │   8   │   2   │     │
│  │ Total │Pend.  │Compl. │Venc.  │     │
│  └───────┴───────┴───────┴───────┘     │
├─────────────────────────────────────────┤
│  📅 Próximas Actividades               │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │ 🔴 #E57373                      │   │
│  │ Tarea: Ejercicios Matemáticas   │   │
│  │ MATEMÁTICAS - A                 │   │
│  │ 📁 PRIMER QUIMESTRE > TAREAS    │   │
│  │ 📅 15 Dic 2025, 23:59           │   │
│  │ ⏰ 5 días restantes             │   │
│  │ 🟡 Pendiente    📎 Requiere envío│   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Badges de Estado

```tsx
const statusStyles = {
  pending:   { bg: '#FFF3CD', text: '#856404', icon: '🕐' },
  submitted: { bg: '#D1ECF1', text: '#0C5460', icon: '📤' },
  completed: { bg: '#D4EDDA', text: '#155724', icon: '✅' },
  overdue:   { bg: '#F8D7DA', text: '#721C24', icon: '⚠️' }
};
```

### Indicador de Tipo de Entrega

```tsx
// Mostrar indicador si requiere envío
{activity.requires_submission && (
  <Badge variant="info">📎 Requiere envío</Badge>
)}
```

### Mostrar Información del Modelo Evaluativo

```tsx
// En el detalle de la actividad
<View style={styles.gradingInfo}>
  <Text style={styles.label}>Cohorte:</Text>
  <Text>{activity.grading_info?.cohort || '-'}</Text>
  
  <Text style={styles.label}>Libro:</Text>
  <Text>{activity.grading_info?.grading_book || '-'}</Text>
  
  <Text style={styles.label}>Categoría:</Text>
  <Text>{activity.grading_info?.category || '-'}</Text>
</View>
```

---

## 6. Ejemplo de Implementación (React Native)

### Types

```typescript
// types/calendar.ts

interface GradingInfo {
  cohort: string | null;
  grading_book: string | null;
  category: string | null;
}

interface Activity {
  id: number;
  title: string;
  description: string;
  start: string;
  end: string;
  color: string;
  type: { id: number; name: string; icon_url: string | null };
  grading_type: string | null;
  delivery_type: string | null;
  requires_submission: boolean;
  grading_info: GradingInfo | null;
  subject: { id: number; name: string; parallel: string };
  status: { code: string; label: string; badge: string };
  submission: { required: boolean; submitted: boolean; deadline_passed: boolean };
  attachments: { has_attachments: boolean; count: number };
  links: { has_links: boolean };
  time_remaining: string | null;
  week_number: number;
  can_submit: boolean;
}

interface CalendarResponse {
  isSuccess: boolean;
  message: string;
  data: {
    view: string;
    period: { id: number; name: string };
    range: { start: string; end: string };
    summary: { total: number; pending: number; completed: number; overdue: number };
    activities: Activity[];
  }
}
```

### Service

```typescript
// services/calendar.service.ts
import { getAccessToken, getSelectedPeriodId } from './auth.service';

const API_BASE = 'https://sige.innotech-solutions.com.ec/api/v1.0.0';

interface CalendarParams {
  view?: 'agenda' | 'month' | 'week';
  date?: string;
  subject_id?: number;
}

export async function getCalendar(params?: CalendarParams): Promise<CalendarResponse> {
  const queryString = new URLSearchParams(params as any).toString();
  const url = `${API_BASE}/student/calendar/${queryString ? '?' + queryString : ''}`;
  
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${await getAccessToken()}`,
      'X-Period-ID': await getSelectedPeriodId(),
    },
  });
  
  return response.json();
}

export async function getActivityDetail(id: number) {
  const response = await fetch(`${API_BASE}/student/activity/${id}/`, {
    headers: {
      'Authorization': `Bearer ${await getAccessToken()}`,
    },
  });
  
  return response.json();
}
```

---

## 7. Checklist de Implementación Frontend

### Servicio y Datos
- [ ] Crear tipos TypeScript para las respuestas
- [ ] Crear servicio `calendar.service.ts`
- [ ] Crear hook `useCalendar.ts`
- [ ] Crear hook `useActivityDetail.ts`

### Pantallas
- [ ] Crear pantalla `CalendarScreen.tsx`
- [ ] Crear pantalla `ActivityDetailScreen.tsx`
- [ ] Agregar navegación entre pantallas

### Componentes
- [ ] Implementar `SummaryCard` (total, pending, completed, overdue)
- [ ] Implementar `ActivityCard` con info de grading
- [ ] Implementar `StatusBadge` con colores por estado
- [ ] Implementar `GradingInfoSection` para mostrar cohorte/libro/categoría
- [ ] Implementar indicador `RequiresSubmission`
- [ ] Implementar selector de vista (SegmentedControl)

### Funcionalidades
- [ ] Implementar pull-to-refresh
- [ ] Implementar renderizado HTML para `description`
- [ ] Implementar descarga/visualización de adjuntos
- [ ] Implementar estados vacíos (sin actividades)

---

## 8. Changelog

### v1.1 (2025-12-09)
- ✅ Agregado `grading_type`: Tipo de calificación
- ✅ Agregado `delivery_type`: Tipo de entrega  
- ✅ Agregado `requires_submission`: Indica si requiere envío
- ✅ Agregado `grading_info` con:
  - `cohort`: Cohorte del modelo evaluativo
  - `grading_book`: Libro de calificación
  - `category`: Categoría de la actividad

### v1.0 (2025-12-09)
- Implementación inicial de endpoints calendar y activity detail

---

**Estado del Backend:** ✅ Implementado y listo para pruebas
