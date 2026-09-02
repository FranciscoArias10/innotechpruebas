# Subject Classmates API Endpoint - Especificación Técnica

## Información General

| Propiedad | Valor |
|-----------|-------|
| **Endpoint** | `GET /api/v1.0.0/student/subjects/<materia_asignada_id>/classmates/` |
| **Versión** | 1.0.0 |
| **Fecha creación** | 2024-12-16 |
| **Autenticación** | JWT Bearer Token |
| **Archivo Vista** | `api/v1_0_0/student/views.py` → `SubjectClassmatesView` |

---

## Propósito

Proporciona la lista de compañeros de clase de una asignatura específica para el estudiante autenticado. Este endpoint implementa **minimización de datos** para cumplir con políticas de privacidad.

**Casos de uso:**
- Ver lista de compañeros para trabajo colaborativo
- Identificar miembros del curso por foto y nombre

---

## Headers Requeridos

| Header | Tipo | Requerido | Descripción |
|--------|------|-----------|-------------|
| `Authorization` | string | ✅ | Token JWT en formato `Bearer <access_token>` |
| `X-Period-ID` | integer | ✅ | ID del **Periodo** (tabla `periodo`, NO `periodolectivo`) |

> [!WARNING]
> **IDOR Prevention**: El `materia_asignada_id` debe pertenecer al estudiante autenticado. Intentos de acceder a materias de otros estudiantes retornarán `403 Forbidden`.

---

## Parámetros de Ruta

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `materia_asignada_id` | integer | ID de la `MateriaAsignada` del estudiante (no `Materia.id`) |

> [!IMPORTANT]
> Usar el ID de `MateriaAsignada` (obtenido de `/student/subjects/`) previene enumeración de materias por terceros.

---

## Request

```http
GET /api/v1.0.0/student/subjects/12345/classmates/
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
    "classmates": [
      {
        "id": 12346,
        "persona_id": 5001,
        "photo_url": "http://localhost:8000/media/imagen_perfil/2024/01/foto.jpg",
        "full_name": "García López Juan Carlos"
      },
      {
        "id": 12347,
        "persona_id": 5002,
        "photo_url": "http://localhost:8000/static/imagen/small/avatar-s-1.png",
        "full_name": "Martínez Pérez María Elena"
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
| `total_students` | `integer` | No | Total de estudiantes incluyendo al autenticado |
| `classmates[].id` | `integer` | No | ID de la MateriaAsignada del compañero |
| `classmates[].persona_id` | `integer` | No | ID único de la Persona (para chat único) |
| `classmates[].photo_url` | `string` | No | URL absoluta de la foto (o avatar por defecto) |
| `classmates[].full_name` | `string` | No | Nombre completo (Apellido1 Apellido2 Nombres) |

> [!TIP]
> **Chat único por persona**: Usa `persona_id` para iniciar conversaciones. Este ID es único por persona y permite identificar al usuario sin importar la materia.

> [!NOTE]
> **Datos NO incluidos (por privacidad):** emails, teléfono, estado de matrícula, asistencia, notas.

---

## Códigos de Error

| Status | Condición | Mensaje |
|--------|-----------|---------|
| 400 | Sin header `X-Period-ID` | `"Header X-Period-ID es requerido"` |
| 400 | `X-Period-ID` no numérico | `"X-Period-ID debe ser un valor numérico"` |
| 403 | Usuario sin perfil de persona | `"Perfil de persona no encontrado"` |
| 403 | Usuario no es estudiante | `"No tiene perfil de estudiante activo"` |
| 403 | **IDOR**: Materia no pertenece al estudiante | `"No tiene acceso a esta materia"` |
| 403 | Periodo no coincide con materia | `"El periodo no coincide con la materia"` |
| 403 | Materia inactiva | `"Materia no disponible"` |
| 500 | Error interno | `"Error al obtener lista de compañeros"` |

### Ejemplo Error 403 (IDOR)

```json
{
  "success": false,
  "message": "No tiene acceso a esta materia"
}
```

---

## Fuentes de Datos (Backend)

### Validación de Propiedad (IDOR Prevention)

```python
mi_materia_asignada = MateriaAsignada.objects.get(
    pk=materia_asignada_id,
    status=True,
    nivelmatriculado__matricula__estudiante=estudiante,
    nivelmatriculado__matricula__retirado=False
)
```

### Query de Compañeros

```python
MateriaAsignada.objects.select_related(
    'nivelmatriculado__matricula__estudiante__persona'
).filter(
    materia=mi_materia_asignada.materia,
    status=True,
    nivelmatriculado__matricula__retirado=False
).exclude(
    nivelmatriculado__matricula__estudiante=estudiante  # Excluye al autenticado
).order_by(
    'nivelmatriculado__matricula__estudiante__persona__apellido_1',
    'nivelmatriculado__matricula__estudiante__persona__apellido_2',
    'nivelmatriculado__matricula__estudiante__persona__nombres'
)
```

---

## Diagrama de Flujo de Seguridad

```
┌──────────────────────────────────────────────────────────┐
│    GET /student/subjects/<MA_ID>/classmates/             │
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
                              │ Es estudiante?    │
                              └─────────┬─────────┘
                                        │
                             No         │         Yes
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                     403 Forbidden          ┌───────────────────┐
                                            │ MA pertenece al   │
                                            │ estudiante?       │
                                            │ (IDOR Check)      │
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
                                                                           + classmates
```

---

## Ejemplo de Uso (React Native)

```typescript
interface Classmate {
  id: number;
  photo_url: string;
  full_name: string;
}

interface ClassmatesResponse {
  subject: {
    id: number;
    name: string;
    level: string;
    parallel: string;
  };
  total_students: number;
  classmates: Classmate[];
}

export const fetchClassmates = async (
  materiaAsignadaId: number,
  accessToken: string,
  periodId: number
): Promise<ClassmatesResponse> => {
  const response = await fetch(
    `${API_BASE}/student/subjects/${materiaAsignadaId}/classmates/`,
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
| Validar MateriaAsignada (IDOR) | 1 | select_related |
| Obtener compañeros | 1 | select_related + order_by |

**Total estimado**: 3-4 queries por request

---

## Seguridad

- ✅ Requiere autenticación JWT
- ✅ **IDOR Prevention**: Valida propiedad de `materia_asignada_id`
- ✅ **Minimización de datos**: Solo foto y nombre
- ✅ **403 en lugar de 404**: No expone existencia de recursos
- ✅ Validación de periodo activo
- ✅ URLs absolutas para fotos (mobile-friendly)
