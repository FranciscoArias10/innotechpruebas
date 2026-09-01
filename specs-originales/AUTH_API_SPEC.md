# Authentication API Specification

Documentación técnica de los endpoints de autenticación para la API v1.0.0.

> [!IMPORTANT]
> Todos los endpoints de autenticación utilizan **JWT (JSON Web Tokens)** con el esquema `Bearer`.

---

## Configuración de Tokens

| Token | Duración | Propósito |
|-------|----------|-----------|
| **Access Token** | 1 minuto* | Autenticación de peticiones |
| **Refresh Token** | 24 horas | Obtener nuevos access tokens sin re-login |

> [!NOTE]
> *Actualmente configurado en 1 minuto para pruebas. En producción debería ser 15 minutos.
> Configuración: `base/my_base.py` → `MY_SIMPLE_JWT`

---

## Endpoints

### Base URL
```
/api/v1_0_0/auth/
```

---

## 1. Sign In (Login)

Autentica un usuario y devuelve tokens JWT.

### Request

```http
POST /api/v1_0_0/auth/sign-in/
Content-Type: application/json
```

**Body:**
```json
{
    "username": "jperez",
    "password": "MiClave123"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `username` | string | ✅ | Nombre de usuario o email |
| `password` | string | ✅ | Contraseña del usuario |

> [!TIP]
> El campo `username` acepta tanto el nombre de usuario como el email del usuario.

### Response - Success (200 OK)

```json
{
    "success": true,
    "message": "Login exitoso",
    "data": {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "user": {
            "id": 123,
            "username": "jperez",
            "email": "jperez@example.com",
            "first_name": "Juan",
            "last_name": "Pérez",
            "is_staff": false,
            "is_superuser": false,
            "is_active": true,
            "date_joined": "2024-01-15T10:30:00Z"
        },
        "profiles": ["student", "representative"],
        "password_change_required": false,
        "periods": [
            {
                "id": 5,
                "name": "2024-2025",
                "is_active": true
            }
        ],
        "active_period_id": 5
    }
}
```

**Campos de respuesta:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `access` | string | JWT Access Token (corta duración) |
| `refresh` | string | JWT Refresh Token (larga duración) |
| `user` | object | Información del usuario autenticado |
| `profiles` | array | Roles disponibles: `student`, `teacher`, `representative`, `admin` |
| `password_change_required` | boolean | `true` si el usuario debe cambiar su contraseña |
| `periods` | array | Períodos académicos disponibles |
| `active_period_id` | integer | ID del período académico activo |

### Response - Error (401 Unauthorized)

```json
{
    "success": false,
    "message": "Credenciales inválidas"
}
```

**Posibles mensajes de error:**
- `"Usuario no encontrado"`
- `"Credenciales inválidas"`
- `"Usuario inactivo"`
- `"Nombre de usuario requerido"`

### Ejemplo cURL

```bash
curl -X POST "http://localhost:8000/api/v1_0_0/auth/sign-in/" \
     -H "Content-Type: application/json" \
     -d '{"username": "jperez", "password": "MiClave123"}'
```

---

## 2. Token Refresh

Obtiene un nuevo access token usando el refresh token.

### Request

```http
POST /api/v1_0_0/auth/refresh/
Content-Type: application/json
```

**Body:**
```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `refresh` | string | ✅ | Refresh token válido |

### Response - Success (200 OK)

```json
{
    "success": true,
    "data": {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }
}
```

> [!IMPORTANT]
> La configuración `ROTATE_REFRESH_TOKENS: True` causa que **cada refresh genere un nuevo refresh token**.
> El refresh token anterior es invalidado (blacklisted).

### Response - Error (401 Unauthorized)

```json
{
    "success": false,
    "message": "Token is invalid or expired"
}
```

### Ejemplo cURL

```bash
curl -X POST "http://localhost:8000/api/v1_0_0/auth/refresh/" \
     -H "Content-Type: application/json" \
     -d '{"refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}'
```

---

## 3. Sign Out (Logout)

Cierra la sesión invalidando el refresh token.

> [!CAUTION]
> Este endpoint requiere autenticación con un access token válido.

### Request

```http
POST /api/v1_0_0/auth/sign-out/
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `refresh` | string | ✅ | Refresh token a invalidar |

### Response - Success (205 Reset Content)

```json
{
    "success": true,
    "message": "Sesión cerrada exitosamente"
}
```

### Response - Error (400 Bad Request)

```json
{
    "success": false,
    "message": "Refresh token is required"
}
```

### Ejemplo cURL

```bash
curl -X POST "http://localhost:8000/api/v1_0_0/auth/sign-out/" \
     -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
     -H "Content-Type: application/json" \
     -d '{"refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}'
```

---

## 4. Recover Password

Resetea la contraseña a una aleatoria y la envía por correo.

### Request

```http
POST /api/v1_0_0/auth/recover-password/
Content-Type: application/json
```

**Body:**
```json
{
    "username": "jperez"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `username` | string | ✅ | Nombre de usuario |

### Response - Success (200 OK)

```json
{
    "success": true,
    "message": "Se ha enviado una nueva contraseña a su correo electrónico.",
    "data": {
        "emails": "jperez@gmail.com, jperez@institution.edu.ec"
    }
}
```

> [!WARNING]
> Después del reset, el usuario deberá cambiar su contraseña en el próximo login (`password_change_required: true`).

### Response - Error (400 Bad Request)

```json
{
    "success": false,
    "message": "No se encontró ningún correo para notificar la nueva clave. Contacte al administrador del sistema."
}
```

**Posibles mensajes de error:**
- `"Complete correctamente su nombre de usuario"`
- `"Persona no existe"`
- `"Usuario no existe"`
- `"No se encontró ningún correo para notificar la nueva clave..."`

---

## 5. Recover Username

Recupera el nombre de usuario usando la cédula.

### Request

```http
POST /api/v1_0_0/auth/recover-username/
Content-Type: application/json
```

**Body:**
```json
{
    "cedula": "1234567890"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `cedula` | string | ✅ | Número de cédula del usuario |

### Response - Success (200 OK)

```json
{
    "success": true,
    "message": "Usuario encontrado",
    "data": {
        "username": "jperez",
        "full_name": "Juan Carlos Pérez López"
    }
}
```

### Response - Error (400 Bad Request)

```json
{
    "success": false,
    "message": "Persona no existe"
}
```

---

## 6. Change Password

Cambia la contraseña del usuario autenticado.

> [!CAUTION]
> Este endpoint requiere autenticación con un access token válido.

### Request

```http
POST /api/v1_0_0/auth/change-password/
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
    "old_password": "MiClaveAnterior123",
    "new_password": "MiNuevaClave456",
    "repeat_password": "MiNuevaClave456"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `old_password` | string | ✅ | Contraseña actual |
| `new_password` | string | ✅ | Nueva contraseña |
| `repeat_password` | string | ✅ | Confirmación de nueva contraseña |

### Requisitos de Contraseña

La nueva contraseña debe cumplir:
- ✅ Mínimo **8 caracteres**
- ✅ Al menos una **letra mayúscula**
- ✅ Al menos una **letra minúscula**
- ✅ Al menos un **número**
- ❌ Sin espacios
- ❌ No puede ser igual a la contraseña anterior
- ❌ No puede ser igual al número de cédula

### Response - Success (200 OK)

```json
{
    "success": true,
    "message": "Contraseña actualizada correctamente"
}
```

### Response - Error (400 Bad Request)

```json
{
    "success": false,
    "message": "La clave elegida no es segura: debe contener letras minúsculas, mayúsculas, números y al menos 8 caracteres."
}
```

**Posibles mensajes de error:**
- `"Todos los campos son requeridos"`
- `"Las claves nuevas no coinciden"`
- `"La clave no puede contener espacios."`
- `"La clave elegida no es segura..."`
- `"Clave nueva no puede ser igual a la clave actual."`
- `"No puede usar como clave su numero de Cédula."`
- `"Clave anterior no coincide."`
- `"Persona no encontrada"`

---

## Flujo de Autenticación

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB

    Note over Client,DB: Login Flow
    Client->>API: POST /auth/sign-in/
    API->>DB: Validate credentials
    DB-->>API: User data
    API-->>Client: access + refresh tokens

    Note over Client,DB: API Request with Token
    Client->>API: GET /student/summary/ (Bearer token)
    API->>API: Validate access token
    API-->>Client: Response data

    Note over Client,DB: Token Refresh Flow
    Client->>API: POST /auth/refresh/ (expired access)
    API->>DB: Validate & blacklist old refresh
    DB-->>API: OK
    API-->>Client: New access + refresh tokens

    Note over Client,DB: Logout Flow
    Client->>API: POST /auth/sign-out/
    API->>DB: Blacklist refresh token
    API-->>Client: 205 Reset Content
```

---

## Manejo de Tokens en el Cliente

### Estrategia Recomendada

```typescript
// 1. Login - Guardar ambos tokens
async function login(username: string, password: string) {
    const response = await fetch('/api/v1_0_0/auth/sign-in/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    
    if (data.success) {
        await SecureStore.setItemAsync('accessToken', data.data.access);
        await SecureStore.setItemAsync('refreshToken', data.data.refresh);
        
        // Verificar si requiere cambio de contraseña
        if (data.data.password_change_required) {
            navigateTo('/change-password');
        }
    }
    return data;
}

// 2. Interceptor para refresh automático
async function apiRequest(url: string, options: RequestInit) {
    let accessToken = await SecureStore.getItemAsync('accessToken');
    
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${accessToken}`
        }
    });
    
    if (response.status === 401) {
        // Intentar refresh
        const refreshed = await refreshTokens();
        if (refreshed) {
            // Reintentar petición original
            accessToken = await SecureStore.getItemAsync('accessToken');
            return fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    'Authorization': `Bearer ${accessToken}`
                }
            });
        } else {
            // Refresh falló - redirigir a login
            navigateTo('/login');
        }
    }
    
    return response;
}

// 3. Función de refresh
async function refreshTokens(): Promise<boolean> {
    const refreshToken = await SecureStore.getItemAsync('refreshToken');
    
    try {
        const response = await fetch('/api/v1_0_0/auth/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: refreshToken })
        });
        const data = await response.json();
        
        if (data.success) {
            await SecureStore.setItemAsync('accessToken', data.data.access);
            await SecureStore.setItemAsync('refreshToken', data.data.refresh);
            return true;
        }
    } catch (error) {
        console.error('Refresh failed:', error);
    }
    return false;
}

// 4. Logout
async function logout() {
    const accessToken = await SecureStore.getItemAsync('accessToken');
    const refreshToken = await SecureStore.getItemAsync('refreshToken');
    
    await fetch('/api/v1_0_0/auth/sign-out/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({ refresh: refreshToken })
    });
    
    await SecureStore.deleteItemAsync('accessToken');
    await SecureStore.deleteItemAsync('refreshToken');
    navigateTo('/login');
}
```

---

## Códigos de Estado HTTP

| Código | Significado | Acción del Cliente |
|--------|-------------|-------------------|
| **200** | Éxito | Procesar respuesta normalmente |
| **205** | Reset Content (logout exitoso) | Limpiar tokens y redirigir a login |
| **400** | Bad Request | Mostrar mensaje de error al usuario |
| **401** | No autenticado | Intentar refresh, si falla ir a login |

---

## Archivos de Implementación

| Archivo | Descripción |
|---------|-------------|
| [urls.py](api/v1_0_0/auth/urls.py) | Definición de rutas |
| [views.py](api/v1_0_0/auth/views.py) | Vistas que delegan a controllers |
| [controller.py](api/v1_0_0/auth/controller.py) | Controladores de endpoints |
| [service.py](api/v1_0_0/auth/service.py) | Lógica de negocio |
| [serializer.py](api/v1_0_0/auth/serializer.py) | Serialización/validación |
| [my_base.py](base/my_base.py#L94-L129) | Configuración JWT (`MY_SIMPLE_JWT`) |
