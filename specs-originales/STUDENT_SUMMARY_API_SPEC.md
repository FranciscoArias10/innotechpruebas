# Student Summary API Endpoint - Especificación Técnica

## Información General

| Propiedad | Valor |
|-----------|-------|
| **Endpoint** | `GET /api/v1_0_0/student/summary/` |
| **Versión** | 1.0.0 |
| **Fecha creación** | 2024-12-16 |
| **Autenticación** | JWT Bearer Token |
| **Archivo Vista** | `api/v1_0_0/student/views.py` → `StudentSummaryView` |

---

## Propósito

Proporciona métricas académicas consolidadas del estudiante para dashboards de aplicaciones móviles:

- **Número de materias** matriculadas en el periodo
- **Porcentaje de asistencia** general (Asis.%)
- **Actividades pendientes** totales (todas las materias)

---

## Headers Requeridos

| Header | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `Authorization` | string | ✅ | Token JWT en formato `Bearer <access_token>` |
| `X-Period-ID` | integer | ✅ | ID del **Periodo** (tabla `periodo`, NO `periodolectivo`) |

> [!WARNING]
> **Importante**: `X-Period-ID` debe ser el ID de la tabla `periodo`, no de `periodolectivo`. El sistema valida por `periodolectivo__periodo__id`.

---

## Request

```http
GET /api/v1_0_0/student/summary/
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
X-Period-ID: 6
Content-Type: application/json
```

---

## Response

### Exitoso (200 OK)

```json
{
  "success": true,
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

### Campos de Respuesta

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `total_subjects` | `integer` | No | Número de materias activas (no retiradas) |
| `attendance_percentage` | `float` | No | Porcentaje de asistencia general (0-100, 1 decimal) |
| `pending_activities` | `integer` | No | Total de actividades con entrega pendiente |
| `enrollment.id` | `integer` | No | ID de la matrícula |
| `enrollment.level` | `string` | No | Nombre completo del nivel |
| `enrollment.level_alias` | `string` | No | Alias corto del nivel (ej: "8vo EGB") |
| `enrollment.parallel` | `string` | No | Paralelo del estudiante |
| `period.id` | `integer` | No | ID del periodo consultado |
| `period.name` | `string` | No | Nombre descriptivo del periodo |

---

## Códigos de Error

| Status | Condición | Mensaje |
|--------|-----------|---------|
| 400 | Sin header `X-Period-ID` | `"Header X-Period-ID es requerido"` |
| 400 | `X-Period-ID` no numérico | `"X-Period-ID debe ser un número entero válido"` |
| 403 | Usuario sin perfil de persona | `"Perfil de persona no encontrado para este usuario."` |
| 403 | Usuario no es estudiante activo | `"No tiene perfil de estudiante activo."` |
| 403 | Periodo no accesible | `"No tiene acceso al periodo seleccionado."` |
| 404 | Sin matrícula en el periodo | `"No existe matrícula activa para el periodo solicitado."` |
| 500 | Error interno | `"Error al obtener el resumen académico."` |

### Ejemplo Error 400

```json
{
  "success": false,
  "message": "Header X-Period-ID es requerido"
}
```

### Ejemplo Error 404

```json
{
  "success": false,
  "message": "No existe matrícula activa para el periodo solicitado."
}
```

---

## Fuentes de Datos (Backend)

### Total de Materias

```python
# Método: Matricula.num_materias()
MateriaAsignada.objects.filter(
    status=True, 
    nivelmatriculado__matricula=self
).count()
```

### Porcentaje de Asistencia

```python
# Método: Matricula.porcentajeAsistenciaMatricula()
# Promedio de asistenciafinal de todas las MateriaAsignada
materias = MateriaAsignada.objects.filter(
    nivelmatriculado__matricula=self,
    retirado=False
).aggregate(
    count=Count('id'),
    total_asistencia=Sum('asistenciafinal')
)
return materias['total_asistencia'] / materias['count']
```

### Actividades Pendientes

```python
# Query optimizada (evita N+1 del método original)
materias_ids = MateriaAsignada.objects.filter(
    nivelmatriculado__matricula=matricula,
    retirado=False
).values_list('materia_id', flat=True)

Actividad.objects.filter(
    librocategoria__materia_id__in=materias_ids,
    fechainicio__lte=fecha_actual,
    fechafin__gte=fecha_actual,
    tipoentrega__in=[1, 2]  # Individual, Grupal
).exclude(
    entregaactividad__materiaasignada__nivelmatriculado__matricula=matricula
).distinct().count()
```

---

## Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────┐
│                     GET /student/summary/                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ X-Period-ID?  │
              └───────┬───────┘
                      │
           No         │         Yes
        ┌─────────────┴─────────────┐
        ▼                           ▼
   400 Bad Request           ┌──────────────┐
                             │ Es integer?  │
                             └──────┬───────┘
                                    │
                         No         │         Yes
                      ┌─────────────┴─────────────┐
                      ▼                           ▼
                 400 Bad Request           ┌──────────────┐
                                           │ Tiene perfil │
                                           │ estudiante?  │
                                           └──────┬───────┘
                                                  │
                                       No         │         Yes
                                    ┌─────────────┴─────────────┐
                                    ▼                           ▼
                               403 Forbidden             ┌──────────────┐
                                                         │ Tiene acceso │
                                                         │ al periodo?  │
                                                         └──────┬───────┘
                                                                │
                                                     No         │         Yes
                                                  ┌─────────────┴─────────────┐
                                                  ▼                           ▼
                                             403 Forbidden             ┌──────────────┐
                                                                       │ Tiene        │
                                                                       │ matrícula?   │
                                                                       └──────┬───────┘
                                                                              │
                                                                   No         │         Yes
                                                                ┌─────────────┴─────────────┐
                                                                ▼                           ▼
                                                           404 Not Found              200 OK
                                                                                    + summary data
```

---

## Ejemplo de Uso (React Native)

```typescript
import { useAuth } from '@/contexts/AuthContext';
import { usePeriod } from '@/contexts/PeriodContext';

interface StudentSummary {
  total_subjects: number;
  attendance_percentage: number;
  pending_activities: number;
  enrollment: {
    id: number;
    level: string;
    level_alias: string;
    parallel: string;
  };
  period: {
    id: number;
    name: string;
  };
}

export const useStudentSummary = () => {
  const { accessToken } = useAuth();
  const { selectedPeriodId } = usePeriod();
  const [summary, setSummary] = useState<StudentSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    if (!selectedPeriodId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/student/summary/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'X-Period-ID': selectedPeriodId.toString(),
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (data.success) {
        setSummary(data.data);
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError('Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [selectedPeriodId]);

  return { summary, loading, error, refetch: fetchSummary };
};
```

---

## Consideraciones de Performance

| Operación | Queries | Optimización |
|-----------|---------|--------------|
| Validar periodo | 1-2 | Cacheable |
| Obtener matrícula | 1 | Índice en `estudiante + periodolectivo` |
| Contar materias | 1 | Método `num_materias()` |
| % Asistencia | 1 | Aggregate con `Sum + Count` |
| Actividades pendientes | 2 | Query optimizada (vs N+1 original) |

**Total estimado**: 5-6 queries por request

---

## Seguridad

- ✅ Requiere autenticación JWT
- ✅ Solo retorna datos del estudiante autenticado (no IDOR)
- ✅ Mensajes de error genéricos (no exponen información sensible)
- ✅ Validación de acceso al periodo consultado
