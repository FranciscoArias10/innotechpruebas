# Student Subjects API Endpoint - Especificación Técnica

## Información General

| Propiedad | Valor |
|-----------|-------|
| **Endpoint** | `GET /api/v1_0_0/student/subjects/` |
| **Versión** | 1.0.0 |
| **Fecha creación** | 2024-12-17 |
| **Autenticación** | JWT Bearer Token |
| **Archivo Vista** | `api/v1_0_0/student/views.py` → `StudentSubjectsView` |

---

## Propósito

Expone la lista de materias/asignaturas del estudiante para aplicaciones móviles, replicando el comportamiento de la web (`alu_aulavirtual.py`):

- **Lista de materias** del estudiante en el periodo seleccionado
- **Información del docente** de cada materia
- **Porcentaje de asistencia** calculado en tiempo real
- **Actividades pendientes** por materia

---

## Headers Requeridos

| Header | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `Authorization` | string | ✅ | Token JWT en formato `Bearer <access_token>` |
| `X-Period-ID` | integer | ✅ | ID del **Periodo** (tabla `periodo`, NO `periodolectivo`) |

---

## Request

```http
GET /api/v1_0_0/student/subjects/
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
    "subjects": [
      {
        "id": 59327,
        "subject_name": "MATEMÁTICAS",
        "level": "8vo EGB",
        "parallel": "A",
        "classroom": "Aula 101",
        "attendance_percentage": 95.5,
        "is_complementary": false,
        "teacher": {
          "id": 123,
          "full_name": "JUAN PÉREZ LÓPEZ",
          "avatar_url": "/media/fotos/profesor_123.jpg"
        },
        "grades_visible": true,
        "pending_activities_count": 2,
        "final_grade": 8.75,
        "final_grade_letter": null,
        "evaluation_model": {
          "is_quantitative": true
        }
      },
      {
        "id": 59328,
        "subject_name": "LENGUA Y LITERATURA",
        "level": "8vo EGB",
        "parallel": "A",
        "classroom": "Aula 102",
        "attendance_percentage": 88.0,
        "is_complementary": false,
        "teacher": {
          "id": 124,
          "full_name": "MARÍA GARCÍA RODRÍGUEZ",
          "avatar_url": null
        },
        "grades_visible": true,
        "pending_activities_count": 1,
        "final_grade": null,
        "final_grade_letter": "A",
        "evaluation_model": {
          "is_quantitative": false
        }
      }
    ],
    "period": {
      "id": 6,
      "name": "2024-2025"
    },
    "total_subjects": 2
  }
}
```

### Campos de Respuesta

#### Subject Item

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | integer | No | ID de la MateriaAsignada (usar para endpoints relacionados) |
| `subject_name` | string | No | Nombre de la asignatura |
| `level` | string | No | Nivel/grado (alias) |
| `parallel` | string | No | Paralelo |
| `classroom` | string | No | Aula asignada |
| `attendance_percentage` | float | No | Porcentaje de asistencia (0-100), calculado en tiempo real |
| `is_complementary` | boolean | No | Si es materia complementaria |
| `teacher` | object | Sí | Información del profesor principal |
| `grades_visible` | boolean | No | Si las calificaciones son visibles en el periodo |
| `pending_activities_count` | integer | No | Cantidad de actividades pendientes |
| `final_grade` | number | Sí | Nota final numérica (solo modelos cuantitativos) |
| `final_grade_letter` | string | Sí | Nota final en letra (solo modelos cualitativos) |
| `evaluation_model` | object | Sí | Información del modelo evaluativo |

#### Teacher Object

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `id` | integer | No | ID del Profesor |
| `full_name` | string | No | Nombre completo |
| `avatar_url` | string | Sí | URL de la foto del profesor |

#### Evaluation Model Object

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `is_quantitative` | boolean | `true` = modelo cuantitativo (notas numéricas), `false` = cualitativo (letras) |

#### Period Object

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | integer | ID del periodo |
| `name` | string | Nombre del periodo |

---

## Lógica de Actividades Pendientes

Una actividad se considera **pendiente** si cumple **todas** estas condiciones:

```python
Actividad.objects.filter(
    librocategoria__materia=ma.materia,
    fechafin__gte=fecha_actual,              # No ha vencido
    planificacionsemanal__estado=3,          # Planificación APROBADA
    status=True,                              # Actividad activa
    oculto=False                              # No oculta
).exclude(
    entregaactividad__materiaasignada=ma     # Sin entrega del estudiante
).exclude(
    notaactividad__materiaasignada=ma        # Sin calificación
).distinct().count()
```

> [!IMPORTANT]
> Solo se cuentan actividades de **planificaciones aprobadas** (`estado=3`).

---

## Lógica de Porcentaje de Asistencia

Se calcula dinámicamente usando el método del modelo:

```python
asistencia_data = ma.calcularPocentajeAsistencia()
attendance_percentage = asistencia_data.get('porcentajeAsitido', 0)
```

Este método:
- Obtiene todas las clases activas de la materia
- Cuenta lecciones con asistencia registrada
- Calcula `(asistencias / total_lecciones) * 100`

Si el cálculo falla, se usa el valor almacenado `asistenciafinal` como fallback.

---

## Códigos de Error

| Status | Condición | Mensaje |
|--------|-----------|---------|
| 400 | Sin header `X-Period-ID` | `"Header X-Period-ID es requerido"` |
| 403 | Usuario sin perfil persona | `"Perfil de persona no encontrado para este usuario."` |
| 403 | Usuario no es estudiante | `"Perfil de estudiante no encontrado."` |
| 403 | Periodo no accesible | `"Periodo inválido"` |
| 500 | Error interno | `"Error al obtener las materias."` |

### Ejemplo Error 403

```json
{
  "isSuccess": false,
  "message": "Perfil de persona no encontrado para este usuario."
}
```

---

## Fuentes de Datos (Backend)

### Materias del Estudiante

```python
MateriaAsignada.objects.select_related(
    'materia__asignaturamalla__asignatura',
    'materia__asignaturamalla__nivelmalla__nivel',
    'materia__paralelo',
    'materia__aula',
    'materia__modeloevaluativo',
    'nivelmatriculado__matricula'
).filter(
    nivelmatriculado__matricula__estudiante=estudiante,
    nivelmatriculado__matricula__periodolectivo__periodo=periodo,
    nivelmatriculado__matricula__retirado=False
).distinct().order_by('materia__asignaturamalla__asignatura__nombre')
```

### Profesor Principal

```python
profesor = ma.profesor_materia()  # Método del modelo MateriaAsignada
```

---

## Lógica de Nota Final

> [!IMPORTANT]
> Los valores de `final_grade` y `final_grade_letter` son **idénticos** a los del endpoint `GET /student/subjects/<id>/grades/`.

**Fuente de verdad:**
- `materia.modeloevaluativo` → modelo evaluativo
- `materia.escuantitativa` → determina si es cuantitativo o cualitativo
- `materia_asignada.notafinal` → nota final almacenada

**Reglas:**

| Condición | `final_grade` | `final_grade_letter` |
|-----------|---------------|----------------------|
| `grades_visible = false` | `null` | `null` |
| Cuantitativa con nota | `8.5` | `null` |
| Cualitativa con nota | `null` | `"A"` |
| Sin nota asignada | `null` | `null` |

```python
# Código exacto (líneas 746-768 de views.py)
if periodo.visiblenota:
    nota_final = ma.notafinal if ma.notafinal else None
    if nota_final and modeloevaluativo:
        if es_cuantitativa:
            final_grade = float(nota_final)
        else:
            final_grade_letter = ma.promedio_letra_modeloevaluativo(
                modeloevaluativo.id, nota_final
            )
```

---

## Diagrama de Modelos

```
┌─────────────────────┐     ┌─────────────────────────┐
│  Estudiante         │────▶│  Matricula              │
└─────────────────────┘     └───────────┬─────────────┘
                                        │
                                        ▼
┌─────────────────────┐     ┌─────────────────────────┐
│  NivelMatriculado   │────▶│  MateriaAsignada        │
└─────────────────────┘     └───────────┬─────────────┘
                                        │
                                        ▼
┌─────────────────────┐     ┌─────────────────────────┐
│  Materia            │────▶│  AsignaturaMalla        │
└─────────────────────┘     └─────────────────────────┘
```

---

## Ejemplo de Uso (React Native)

```typescript
import { useCallback, useState, useEffect } from 'react';

interface Subject {
  id: number;
  subject_name: string;
  level: string;
  parallel: string;
  classroom: string;
  attendance_percentage: number;
  is_complementary: boolean;
  teacher: {
    id: number;
    full_name: string;
    avatar_url: string | null;
  } | null;
  grades_visible: boolean;
  pending_activities_count: number;
  final_grade: number | null;
  final_grade_letter: string | null;
  evaluation_model: {
    is_quantitative: boolean;
  } | null;
}

interface SubjectsResponse {
  subjects: Subject[];
  period: { id: number; name: string };
  total_subjects: number;
}

export const useStudentSubjects = () => {
  const { accessToken } = useAuth();
  const { selectedPeriodId } = usePeriod();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSubjects = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/student/subjects/`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'X-Period-ID': selectedPeriodId.toString(),
        },
      });
      
      const result = await response.json();
      if (result.isSuccess) {
        setSubjects(result.data.subjects);
      }
    } finally {
      setLoading(false);
    }
  }, [selectedPeriodId, accessToken]);

  useEffect(() => {
    fetchSubjects();
  }, [fetchSubjects]);

  return { subjects, loading, refetch: fetchSubjects };
};
```

### Componente de Card

```tsx
const SubjectCard = ({ subject }: { subject: Subject }) => (
  <TouchableOpacity 
    style={styles.card}
    onPress={() => navigation.navigate('SubjectDetail', { id: subject.id })}
  >
    <View style={styles.header}>
      <Text style={styles.title}>{subject.subject_name}</Text>
      <Text style={styles.level}>{subject.level} - {subject.parallel}</Text>
    </View>
    
    {subject.teacher && (
      <View style={styles.teacher}>
        <Image 
          source={{ uri: subject.teacher.avatar_url || DEFAULT_AVATAR }}
          style={styles.avatar}
        />
        <Text>{subject.teacher.full_name}</Text>
      </View>
    )}
    
    <View style={styles.stats}>
      <View style={styles.stat}>
        <Text style={styles.statValue}>{subject.attendance_percentage}%</Text>
        <Text style={styles.statLabel}>Asistencia</Text>
      </View>
      
      {subject.pending_activities_count > 0 && (
        <View style={[styles.stat, styles.pending]}>
          <Text style={styles.pendingValue}>{subject.pending_activities_count}</Text>
          <Text style={styles.statLabel}>Pendientes</Text>
        </View>
      )}
    </View>
  </TouchableOpacity>
);
```

---

## Seguridad

- ✅ Requiere autenticación JWT
- ✅ Valida que el usuario tenga perfil de estudiante
- ✅ Valida acceso al periodo solicitado
- ✅ Solo muestra materias no retiradas
- ✅ Solo cuenta actividades de planificaciones aprobadas

---

## Endpoints Relacionados

| Endpoint | Descripción |
|----------|-------------|
| `GET /student/subjects/<id>/planning/` | Planificación semanal de una materia |
| `GET /student/subjects/<id>/classmates/` | Compañeros de una materia |
| `GET /student/calendar/` | Calendario de actividades |
| `GET /student/summary/` | Resumen académico del estudiante |

---

## Notas de Implementación

### Porcentaje de Asistencia en Tiempo Real

El método `calcularPocentajeAsistencia()` es costoso computacionalmente. Si hay problemas de rendimiento, considerar:
1. Usar el valor almacenado `asistenciafinal`
2. Implementar caché
3. Calcular asíncronamente

### Orden de Materias

Las materias se ordenan alfabéticamente por nombre de asignatura.
