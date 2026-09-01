# Class Planning API Endpoint - Especificación Técnica

## Información General

| Propiedad | Valor |
|-----------|-------|
| **Endpoint** | `GET /api/v1_0_0/student/subjects/<materia_asignada_id>/planning/` |
| **Versión** | 1.0.0 |
| **Fecha creación** | 2024-12-17 |
| **Autenticación** | JWT Bearer Token |
| **Archivo Vista** | `api/v1_0_0/student/views.py` → `StudentClassPlanningView` |

---

## Propósito

Expone la funcionalidad de "Planificación de Clase" para aplicaciones móviles, replicando el comportamiento de la web (`alu_aulavirtual.py` action='planificacionclase'):

- **Contenido semanal** del docente (unidades, temas, subtemas)
- **Recursos** de la semana (links, archivos, carpetas)
- **Actividades** planificadas con paginación
- **Navegación** entre semanas

---

## Headers Requeridos

| Header | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `Authorization` | string | ✅ | Token JWT en formato `Bearer <access_token>` |
| `X-Period-ID` | integer | ✅ | ID del **Periodo** (tabla `periodo`, NO `periodolectivo`) |

---

## Parámetros de Query

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `week` | integer | - | Número de orden de la semana (1-based) |
| `ids` | integer | - | Alias legacy de `week` (compatibilidad web) |
| `date` | string | hoy + 3 días | Fecha ISO 8601 para determinar semana |
| `activities_limit` | integer | 50 | Máximo de actividades a retornar (max: 100) |
| `activities_offset` | integer | 0 | Offset para paginación de actividades |

> [!NOTE]
> Se aceptan tanto `week` como `ids` para compatibilidad con la web. 
> **Prioridad de selección de semana**: `week`/`ids` > `date` > fecha actual + 3 días.

---

## Request

```http
GET /api/v1_0_0/student/subjects/12345/planning/?week=3
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
X-Period-ID: 6
Content-Type: application/json
```

---

## Response

### Exitoso (200 OK)

```json
{
  "isSuccess": true,
  "message": null,
  "data": {
    "subject": {
      "id": 12345,
      "name": "MATEMÁTICAS",
      "level": "8vo EGB",
      "parallel": "A",
      "start_date": "2025-04-16",
      "end_date": "2026-02-28",
      "total_weeks": 43,
      "pending_activities": 5
    },
    "week": {
      "order": 3,
      "name": "SEMANA 3 TT",
      "start_date": "2025-11-17",
      "end_date": "2025-11-23",
      "has_previous": true,
      "has_next": true,
      "pending_activities": 1
    },
    "content": {
      "units": [
        {
          "id": 1,
          "name": "UNIDAD # 5",
          "objective": "Comprender los conceptos de medición...",
          "topics": [
            {
              "id": 1,
              "name": "SOY EL SEÑOR METRO",
              "content": "<html>...",
              "subtopics": [
                {
                  "id": 1,
                  "name": "MEDIDAS DE TIEMPO",
                  "content": "<html>..."
                }
              ]
            }
          ]
        }
      ],
      "bibliographies": [
        { "id": 1, "name": "Libro de Matemáticas 8vo" }
      ],
      "methodological_strategies": [
        { "id": 1, "name": "Trabajo en grupo" }
      ],
      "resources": {
        "links": [
          {
            "id": 1,
            "name": "OBSERVE EL VIDEO \"NOCIONES DEL TIEMPO\"",
            "url": "https://youtube.com/...",
            "type": { "code": "video", "name": "Video", "icon_url": "/media/icono/video.svg" },
            "type_icon": "/media/icono/link.svg"
          }
        ],
        "files": [
          {
            "id": 1,
            "name": "MATERIAL DE APOYO.pdf",
            "download_url": "/download/...",
            "type": { "code": "pdf", "name": "PDF", "icon_url": "/media/icono/pdf.svg" },
            "type_icon": "/media/icono/pdf.svg"
          }
        ],
        "folders": [
          {
            "id": 1,
            "name": "Material complementario",
            "type": { "code": "folder", "name": "Carpeta", "icon_url": "/media/icono/folder.svg" },
            "type_icon": "/media/icono/folder.svg"
          }
        ]
      }
    },
    "activities": {
      "items": [
        {
          "id": 1,
          "name": "ACTIVIDAD EN CLASE EXPUESTA EN UNA HOJA DE TRABAJO",
          "type": { "id": 1, "name": "Actividad", "icon_url": "/media/icono/actividad.svg" },
          "start_date": "2025-11-18T07:00:00-05:00",
          "end_date": "2025-11-18T12:00:00-05:00",
          "status": { "code": "pending", "label": "Pendiente" },
          "has_attachment": true,
          "attachment_url": "/download/..."
        },
        {
          "id": 2,
          "name": "ACTIVIDAD COMPLEMENTARIA # 2",
          "type": { "id": 2, "name": "Tarea", "icon_url": "/media/icono/tarea.svg" },
          "start_date": "2025-11-27T07:00:00-05:00",
          "end_date": "2025-11-27T12:00:00-05:00",
          "status": { "code": "submitted", "label": "Entregada" },
          "has_attachment": false,
          "attachment_url": null
        }
      ],
      "total": 3,
      "pending_count": 1,
      "limit": 50,
      "offset": 0
    },
    "navigation": {
      "total_weeks": 43,
      "current_week": 3,
      "previous_week": 2,
      "next_week": 4
    }
  }
}
```

### Campos de Respuesta

#### Subject

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | integer | No | ID de la MateriaAsignada |
| `name` | string | No | Nombre de la asignatura |
| `level` | string | No | Nivel/grado |
| `parallel` | string | No | Paralelo |
| `start_date` | date | Sí | Fecha inicio de la materia |
| `end_date` | date | Sí | Fecha fin de la materia |
| `total_weeks` | integer | No | Total de semanas configuradas |
| `pending_activities` | integer | No | Actividades pendientes (todas las semanas) |

#### Week

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `order` | integer | No | Número de orden de la semana |
| `name` | string | No | Nombre de la semana (ej: "SEMANA 3 TT") |
| `start_date` | date | Sí | Fecha inicio de la semana |
| `end_date` | date | Sí | Fecha fin de la semana |
| `has_previous` | boolean | No | Si existe semana anterior |
| `has_next` | boolean | No | Si existe semana siguiente |
| `pending_activities` | integer | No | Actividades pendientes **solo de esta semana** (para badge) |

#### Content

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `units` | array | Sí | Lista de unidades con temas y subtemas |
| `bibliographies` | array | Sí | Lista de bibliografías |
| `methodological_strategies` | array | Sí | Estrategias metodológicas |
| `resources.links` | array | Sí | Links de recursos (videos, enlaces externos) |
| `resources.files` | array | Sí | Archivos descargables (PDF, documentos) |
| `resources.folders` | array | Sí | Carpetas (solo metadata) |

> [!IMPORTANT]
> `content` puede ser `null` si la semana no tiene contenido aprobado (`estado=3`).

#### Content.Resources Item (links, files, folders)

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | integer | No | ID del recurso |
| `name` | string | No | Nombre/descripción del recurso |
| `url` | string | Sí | URL del enlace (solo para `links`) |
| `download_url` | string | Sí | URL de descarga (solo para `files`) |
| `type` | object | No | Tipo del recurso |
| `type.code` | string | No | Código: `video`, `link`, `pdf`, `doc`, `excel`, `ppt`, `image`, `file`, `folder` |
| `type.name` | string | No | Nombre legible: "Video", "PDF", "Documento", etc. |
| `type.icon_url` | string | Sí | URL del icono |
| `type_icon` | string | Sí | **[LEGACY]** URL del icono (deprecated, usar `type.icon_url`) |

#### Activities

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `items` | array | Lista de actividades de la semana |
| `total` | integer | Total de actividades de la semana (para paginación) |
| `pending_count` | integer | Cantidad de actividades pendientes de la semana |
| `limit` | integer | Límite aplicado |
| `offset` | integer | Offset aplicado |

#### Activities.status.code

| Código | Descripción |
|--------|-------------|
| `pending` | Sin entrega, dentro del plazo |
| `submitted` | Entregada |
| `overdue` | Sin entrega, plazo vencido |

#### Navigation

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `total_weeks` | integer | No | Total de semanas configuradas |
| `current_week` | integer | Sí | Orden de la semana actual |
| `previous_week` | integer | Sí | Orden de la semana anterior (null si primera) |
| `next_week` | integer | Sí | Orden de la semana siguiente (null si última) |

---

## Códigos de Error

| Status | Condición | Mensaje |
|--------|-----------|---------|
| 400 | Sin header `X-Period-ID` | `"Header X-Period-ID es requerido"` |
| 400 | Parámetro `week`/`ids` no numérico | `"Parámetro week/ids debe ser un número entero"` |
| 400 | Formato fecha inválido | `"Formato de fecha inválido. Use ISO 8601"` |
| 403 | Usuario sin perfil persona | `"Perfil de persona no encontrado"` |
| 403 | Usuario no es estudiante | `"No tiene perfil de estudiante activo"` |
| 403 | Periodo no accesible | `"No tiene acceso al periodo solicitado"` |
| 403 | Materia no pertenece al periodo | `"La materia no pertenece al periodo solicitado"` |
| 404 | Materia no encontrada | `"Materia no encontrada o no tiene acceso"` |
| 404 | Semana no encontrada | `"Semana {n} no encontrada"` |
| 500 | Error interno | `"Error al obtener planificación de clase"` |

### Ejemplo Error 404

```json
{
  "isSuccess": false,
  "message": "Materia no encontrada o no tiene acceso"
}
```

---

## Fuentes de Datos (Backend)

### Semanas del Cronograma

```python
SemanaCronograma.objects.filter(
    cronograma__cronogramamateria__materia_id=materia.id
).distinct().order_by("inicio")
```

### Determinación de Semana Actual

```python
from datetime import timedelta
from django.utils import timezone

ref_date = timezone.now().date() + timedelta(days=3)
target_week = semanas.filter(inicio__lte=ref_date, fin__gte=ref_date).first()
```

### Contenido Semanal Aprobado

```python
def contenido_semanal_aprobado(self, idmateria):
    return PlanificacionSemanalContenido.objects.filter(
        materia_id=idmateria, 
        inicio=self.inicio, 
        fin=self.fin, 
        estado=3  # APROBADO
    ).latest("id")
```

### Determinación de Tipo de Archivo

```python
# Para archivos: detecta tipo por extensión
file_ext = file_name.split('.')[-1].lower()
if file_ext in ['pdf']:
    type_code, type_name = 'pdf', 'PDF'
elif file_ext in ['doc', 'docx']:
    type_code, type_name = 'doc', 'Documento'
# etc.

# Para links: detecta videos por URL
if 'youtube' in url or 'vimeo' in url:
    type_code, type_name = 'video', 'Video'
```

---

## Diagrama de Modelos

```
┌─────────────────────┐     ┌─────────────────────────┐
│  MateriaAsignada    │────▶│  Materia                │
└─────────────────────┘     └───────────┬─────────────┘
                                        │
                                        ▼
┌─────────────────────┐     ┌─────────────────────────┐
│  SemanaCronograma   │────▶│  CronogramaAcademico    │
└─────────┬───────────┘     └─────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  PlanificacionSemanalContenido                      │
│  (estado: 1=Pendiente, 2=Enviado, 3=Aprobado, 4=Rechazado) │
└─────────────────────┬───────────────────────────────┘
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ UnidadSemanal│ │ Bibliografía │ │ Actividad    │
│ Clase        │ │ SemanalClase │ │              │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌──────────────┐
│ TemaSemanal  │
│ Clase        │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ SubTemaSema- │
│ nalClase     │
└──────────────┘
```

---

## Ejemplo de Uso (React Native)

```typescript
import { useCallback, useState } from 'react';

interface ClassPlanningData {
  subject: SubjectInfo;
  week: WeekInfo | null;
  content: WeekContent | null;
  activities: ActivitiesPaginated;
  navigation: NavigationInfo;
}

export const useClassPlanning = (materiaAsignadaId: number) => {
  const { accessToken } = useAuth();
  const { selectedPeriodId } = usePeriod();
  const [data, setData] = useState<ClassPlanningData | null>(null);

  const fetchPlanning = useCallback(async (week?: number) => {
    let url = `${API_BASE}/student/subjects/${materiaAsignadaId}/planning/`;
    if (week) url += `?week=${week}`;
    
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'X-Period-ID': selectedPeriodId.toString(),
      },
    });
    
    const result = await response.json();
    if (result.isSuccess) setData(result.data);
  }, [materiaAsignadaId, selectedPeriodId, accessToken]);

  const goToNextWeek = () => {
    if (data?.navigation.next_week) {
      fetchPlanning(data.navigation.next_week);
    }
  };

  return { data, fetchPlanning, goToNextWeek };
};
```

---

## Consideraciones para React Native (HTML Content)

Los campos `topics.content` y `subtopics.content` contienen HTML.

```typescript
// Usar react-native-render-html
import RenderHtml from 'react-native-render-html';

const ContentRenderer = ({ htmlContent }: { htmlContent: string }) => {
  const { width } = useWindowDimensions();
  
  // Resolver URLs relativas a absolutas
  const processedHtml = htmlContent.replace(
    /src="\/media\//g, 
    `src="${API_BASE}/media/`
  );
  
  return (
    <RenderHtml
      contentWidth={width - 32}
      source={{ html: processedHtml }}
    />
  );
};
```

---

## Seguridad

- ✅ Requiere autenticación JWT
- ✅ Valida propiedad de la MateriaAsignada (evita IDOR)
- ✅ Valida que estudiante no esté retirado
- ✅ Valida que el periodo corresponda a la materia
- ✅ Solo muestra contenido aprobado (`estado=3`)
- ✅ Carpetas solo devuelven metadata (no acceso a filesystem)
- ✅ Mensajes de error genéricos

---

## Endpoints Relacionados

| Endpoint | Descripción |
|----------|-------------|
| `GET /student/subjects/` | Lista de materias del estudiante |
| `GET /student/calendar/` | Calendario de actividades |
| `GET /student/activity/<id>/` | Detalle de actividad |
| `GET /student/subjects/<id>/classmates/` | Compañeros de la materia |

---

## Notas de Implementación

### Lógica de Semana por Defecto

La web usa `fecha actual + 3 días` como referencia para mostrar la semana "adelantada".

### Alias `ids` vs `week`

El parámetro `ids` se mantiene para compatibilidad con código legacy. Se recomienda usar `week`.

### Carpetas - Endpoint Futuro

Las carpetas solo devuelven metadata. Se planea un endpoint separado:
```
GET /student/subjects/<id>/planning/folders/<folder_id>/contents/
```

### Resources.notes (No implementado)

La funcionalidad de "notas de texto del docente" requiere un nuevo modelo `NotaSemanalClase` que actualmente no existe en el sistema. Se documenta para implementación futura.
