# Subject Students (Teacher Roster) API Endpoint - Especificación Técnica

## Información General

| Propiedad | Valor |
|-----------|-------|
| **Endpoint** | `GET /api/v1.0.0/teacher/subjects/<materia_id>/students/` |
| **Versión** | 1.0.0 |
| **Fecha creación** | 2024-12-16 |
| **Autenticación** | JWT Bearer Token |
| **Archivo Vista** | `api/v1_0_0/teacher/views.py` → `SubjectStudentsView` |

---

## Propósito

Proporciona la lista completa de estudiantes matriculados en una asignatura para docentes. Incluye todos los datos necesarios para gestión académica.

**Casos de uso:**
- Control de asistencia
- Revisión de calificaciones
- Contacto con estudiantes
- Gestión de estado de matrícula

---

## Headers Requeridos

| Header | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `Authorization` | string | ✅ | Token JWT en formato `Bearer <access_token>` |
| `X-Period-ID` | integer | ✅ | ID del **Periodo** (tabla `periodo`, NO `periodolectivo`) |

> [!WARNING]
> **Control de Acceso**: El docente debe tener una asignación activa (`ProfesorMateria`) a la materia solicitada.

---

## Parámetros de Ruta

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `materia_id` | integer | ID de la `Materia` |

---

## Request

```http
GET /api/v1.0.0/teacher/subjects/456/students/
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
    "subject": {
      "id": 456,
      "name": "Matemáticas",
      "level": "OCTAVO AÑO EGB",
      "parallel": "A"
    },
    "total_students": 25,
    "students": [
      {
        "id": 12345,
        "student_id": 100,
        "persona_id": 5001,
        "photo_url": "http://localhost:8000/media/imagen_perfil/2024/01/foto.jpg",
        "full_name": "García López Juan Carlos",
        "emails": ["juan.garcia@institucion.edu.ec", "juan@correo.com"],
        "phone": "0999654321",
        "enrollment_status": {
          "label": "badge-success",
          "status": "Activo"
        },
        "attendance_percentage": 95.5,
        "final_grade": 9.25
      },
      {
        "id": 12346,
        "student_id": 101,
        "persona_id": 5002,
        "photo_url": "http://localhost:8000/static/imagen/small/avatar-s-2.png",
        "full_name": "Martínez Pérez María Elena",
        "emails": ["maria.martinez@institucion.edu.ec"],
        "phone": null,
        "enrollment_status": {
          "label": "badge-success",
          "status": "Activo"
        },
        "attendance_percentage": 100.0,
        "final_grade": null
      }
    ]
  }
}
```

### Campos de Respuesta

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `subject.id` | `integer` | No | ID de la materia |
| `subject.name` | `string` | No | Nombre de la asignatura |
| `subject.level` | `string` | No | Nivel académico |
| `subject.parallel` | `string` | No | Paralelo |
| `total_students` | `integer` | No | Total de estudiantes matriculados |
| `students[].id` | `integer` | No | ID de la MateriaAsignada |
| `students[].student_id` | `integer` | No | ID del Estudiante |
| `students[].persona_id` | `integer` | No | ID único de la Persona (para chat único) |
| `students[].photo_url` | `string` | No | URL absoluta de la foto |
| `students[].full_name` | `string` | No | Nombre completo |
| `students[].emails` | `array` | No | Lista de correos (institucional primero) |
| `students[].phone` | `string` | Sí | Teléfono móvil (null si no disponible) |
| `students[].enrollment_status.label` | `string` | No | Clase CSS para badge (badge-success, etc.) |
| `students[].enrollment_status.status` | `string` | No | Estado descriptivo (Activo, Retirado, etc.) |
| `students[].attendance_percentage` | `float` | No | Porcentaje de asistencia (1 decimal) |
| `students[].final_grade` | `float` | Sí | Nota final (2 decimales, null si no aplica) |

> [!TIP]
> **Chat único por persona**: Usa `persona_id` para iniciar conversaciones. Este ID es único por persona y permite identificar al usuario sin importar la materia o rol.

---

## Códigos de Error

| Status | Condición | Mensaje |
|--------|-----------|---------|
| 400 | Sin header `X-Period-ID` | `"Header X-Period-ID es requerido"` |
| 400 | `X-Period-ID` no numérico | `"X-Period-ID debe ser un valor numérico"` |
| 403 | Usuario sin perfil de persona | `"Perfil de persona no encontrado"` |
| 403 | Usuario no es docente | `"No tiene perfil de docente activo"` |
| 403 | Materia no existe | `"Materia no encontrada"` |
| 403 | Docente sin asignación a materia | `"No tiene asignación a esta materia"` |
| 403 | Periodo no coincide con materia | `"El periodo no coincide con la materia"` |
| 500 | Error interno | `"Error al obtener lista de estudiantes"` |

### Ejemplo Error 403Ejemplo Error 403

```json
{
  "success": false,
  "message": "No tiene asignación a esta materia"
}
```

---

## Fuentes de Datos (Backend)

### Validación de Asignación Docente

```python
tiene_asignacion = ProfesorMateria.objects.filter(
    profesor=profesor,
    materia=materia,
    activo=True,
    status=True
).exists()
```

### Query de Estudiantes

```python
MateriaAsignada.objects.select_related(
    'nivelmatriculado__matricula__estudiante__persona'
).filter(
    materia=materia,
    status=True,
    nivelmatriculado__matricula__retirado=False
).order_by(
    'nivelmatriculado__matricula__estudiante__persona__apellido_1',
    'nivelmatriculado__matricula__estudiante__persona__apellido_2',
    'nivelmatriculado__matricula__estudiante__persona__nombres'
)
```

### Priorización de Emails

```python
emails = []
if persona.correo_institucional:
    emails.append(persona.correo_institucional)  # Primero institucional
if persona.correo:
    emails.append(persona.correo)  # Luego personal
```

---

## Diagrama de Flujo de Seguridad

```
┌──────────────────────────────────────────────────────────┐
│    GET /teacher/subjects/<MATERIA_ID>/students/          │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ X-Period-ID?  │
                └───────┬───────┘
                        │
             No         │         Yes
          ┌─────────────┴─────────────┐
          ▼                           ▼
     400 Bad Request          ┌───────────────────┐
                              │ Es docente?       │
                              └─────────┬─────────┘
                                        │
                             No         │         Yes
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                     403 Forbidden          ┌───────────────────┐
                                            │ Materia existe?   │
                                            └─────────┬─────────┘
                                                      │
                                           No         │         Yes
                                        ┌─────────────┴─────────────┐
                                        ▼                           ▼
                                   403 Forbidden          ┌───────────────────┐
                                                          │ Tiene             │
                                                          │ ProfesorMateria?  │
                                                          └─────────┬─────────┘
                                                                    │
                                                         No         │         Yes
                                                      ┌─────────────┴─────────────┐
                                                      ▼                           ▼
                                                 403 Forbidden          ┌───────────────────┐
                                                                        │ Periodo coincide? │
                                                                        └─────────┬─────────┘
                                                                                  │
                                                                       No         │         Yes
                                                                    ┌─────────────┴─────────────┐
                                                                    ▼                           ▼
                                                               403 Forbidden               200 OK
                                                                                         + students
```

---

## Ejemplo de Uso (React Native)

```typescript
interface StudentRoster {
  id: number;
  student_id: number;
  photo_url: string;
  full_name: string;
  emails: string[];
  phone: string | null;
  enrollment_status: {
    label: string;
    status: string;
  };
  attendance_percentage: number;
  final_grade: number | null;
}

interface RosterResponse {
  subject: {
    id: number;
    name: string;
    level: string;
    parallel: string;
  };
  total_students: number;
  students: StudentRoster[];
}

export const fetchStudentRoster = async (
  materiaId: number,
  accessToken: string,
  periodId: number
): Promise<RosterResponse> => {
  const response = await fetch(
    `${API_BASE}/teacher/subjects/${materiaId}/students/`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'X-Period-ID': periodId.toString(),
        'Content-Type': 'application/json',
      },
    }
  );
  
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.message);
  }
  
  return data.data;
};
```

---

## Consideraciones de Performance

| Operación | Queries | Optimización |
|-----------|---------|--------------|
| Validar periodo | 1-2 | Cacheable |
| Validar ProfesorMateria | 1 | exists() |
| Obtener Materia | 1 | select_related |
| Obtener estudiantes | 1 | select_related + order_by |

**Total estimado**: 4-5 queries por request

---

## Consideraciones de Privacidad

| Campo | Incluido | Justificación |
|-------|----------|---------------|
| `emails` | ✅ | Necesario para contacto académico (institucional primero) |
| `phone` | ✅ | Contacto de emergencia / notificaciones |
| `enrollment_status` | ✅ | Gestión de asistencia/calificaciones |
| `attendance_percentage` | ✅ | Control docente |
| `final_grade` | ✅ | Gestión de calificaciones |

> [!CAUTION]
> Este endpoint expone PII. Restringido exclusivamente a docentes con asignación activa.

---

## Seguridad

- ✅ Requiere autenticación JWT
- ✅ Valida rol de docente
- ✅ Valida asignación `ProfesorMateria`
- ✅ Valida consistencia de periodo
- ✅ **403 en lugar de 404**: No expone existencia de recursos
- ✅ select_related evita N+1 queries
- ✅ URLs absolutas para fotos
