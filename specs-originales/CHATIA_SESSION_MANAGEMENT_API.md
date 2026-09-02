# ChatIA Session Management - API Spec para Frontend

**Fecha:** 2025-12-31  
**Versión API:** v1.0.0

---

## Resumen de Cambios

| Feature | Endpoint | Descripción |
|---------|----------|-------------|
| Auto-título | `POST /messages/` | Título generado automáticamente en primer mensaje |
| Renombrar | `PATCH /sessions/{id}/` | Actualizar título manualmente |
| Eliminar | `DELETE /sessions/{id}/` | Eliminación lógica (soft delete) |

---

## 1. Listado de Sesiones

```http
GET /api/v1_0_0/chat-ia/sessions/
```

### Cambio
- Las sesiones eliminadas (`status='deleted'`) **ya no aparecen** en el listado
- El campo `title` ahora puede tener un valor generado automáticamente

### Response (sin cambios en estructura)
```json
{
  "isSuccess": true,
  "data": [
    {
      "id": "uuid",
      "title": "Consulta sobre horario",  // Ahora se genera automático
      "status": "active",
      "created_at": "2025-12-31T10:00:00Z",
      "updated_at": "2025-12-31T10:30:00Z"
    }
  ]
}
```

---

## 2. Renombrar Sesión (NUEVO)

```http
PATCH /api/v1_0_0/chat-ia/sessions/{session_id}/
Content-Type: application/json
Authorization: Bearer {token}
```

### Request Body
```json
{
  "title": "Mi título personalizado"
}
```

### Validaciones
| Regla | Error |
|-------|-------|
| Título vacío | 400 `"Title is required"` |
| Título > 100 chars | 400 `"Title max 100 characters"` |
| Sesión eliminada | 410 (ver abajo) |

### Success Response (200)
```json
{
  "isSuccess": true,
  "data": {
    "id": "uuid",
    "title": "Mi título personalizado",
    "status": "active",
    "updated_at": "2025-12-31T16:30:00Z"
  }
}
```

### Error: Sesión Eliminada (410)
```json
{
  "isSuccess": false,
  "message": "Session has been deleted",
  "error": {
    "code": "SESSION_DELETED"
  }
}
```

---

## 3. Eliminar Sesión (ACTUALIZADO)

```http
DELETE /api/v1_0_0/chat-ia/sessions/{session_id}/
Authorization: Bearer {token}
```

### Comportamiento
- **Soft delete**: La sesión no se borra físicamente
- **Idempotente**: Llamar 2 veces devuelve 200 ambas
- La sesión desaparece del listado

### Success Response (200)
```json
{
  "isSuccess": true,
  "message": "Sesión eliminada",
  "data": {
    "id": "uuid",
    "status": "deleted",
    "deleted_at": "2025-12-31T16:30:00Z"
  }
}
```

---

## 4. Error 410 Gone

**Nuevo código de error** para sesiones eliminadas.

### Cuándo ocurre
- `PATCH /sessions/{id}/` sobre sesión eliminada
- `POST /messages/` sobre sesión eliminada

### Payload estándar
```json
{
  "isSuccess": false,
  "message": "Session has been deleted",
  "error": {
    "code": "SESSION_DELETED"
  }
}
```

### Manejo recomendado en frontend
```typescript
if (response.status === 410) {
  // Remover sesión de la lista local
  // Mostrar toast: "Esta conversación fue eliminada"
  // Navegar a lista de sesiones
}
```

---

## 5. UI Sugerida

### Lista de Sesiones
```
┌─────────────────────────────────────┐
│ Consulta sobre horario          ... │  ← Menú contextual
│ Hace 5 minutos                      │
├─────────────────────────────────────┤
│ Actividades pendientes          ... │
│ Hace 1 hora                         │
└─────────────────────────────────────┘

Menú contextual:
  ├── ✏️ Renombrar
  └── 🗑️ Eliminar
```

### Renombrar (Modal/Bottom Sheet)
```
┌─────────────────────────────────────┐
│ Renombrar conversación              │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Mi título personalizado        │ │
│ └─────────────────────────────────┘ │
│                                     │
│     [Cancelar]    [Guardar]         │
└─────────────────────────────────────┘
```

### Eliminar (Confirmación)
```
┌─────────────────────────────────────┐
│ ¿Eliminar conversación?             │
│                                     │
│ Esta acción no se puede deshacer.   │
│                                     │
│     [Cancelar]    [Eliminar]        │
└─────────────────────────────────────┘
```

---

## Checklist de Implementación

- [ ] Agregar menú contextual en lista de sesiones
- [ ] Implementar modal de renombrar con validación (max 100 chars)
- [ ] Implementar confirmación de eliminación
- [ ] Manejar HTTP 410 en interceptor/handler global
- [ ] Actualizar lista local al eliminar (sin refetch)
- [ ] Mostrar título auto-generado (ya viene del backend)
