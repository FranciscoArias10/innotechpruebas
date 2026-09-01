# Branding Config API Specification

## Resumen

Endpoint público para obtener la configuración de branding institucional. Diseñado para que aplicaciones frontend/móviles personalicen la interfaz de usuario (splash screens, colores, logos, redes sociales) sin requerir autenticación.

---

## Endpoint

### GET `/api/v1_0_0/config/branding/`

Retorna la configuración completa de branding institucional.

#### Características

| Atributo | Valor |
|----------|-------|
| **Autenticación** | REQUERIDA (JWT Bearer Token) |
| **Rate Limiting** | No aplica |
| **Método HTTP** | GET |
| **Content-Type Response** | `application/json` |

---

## Request

### Headers

```http
GET /api/v1_0_0/config/branding/ HTTP/1.1
Host: sige.example.edu.ec
Accept: application/json
Authorization: Bearer <access_token>
```

### Parámetros

Este endpoint no acepta parámetros.

---

## Response

### Respuesta Exitosa (200 OK)

```json
{
    "success": true,
    "data": {
        "name": "Sistema Integrado de Gestión Educativa",
        "name_key": "SIGE",
        "slogan": "Educación de calidad para todos",
        "base_path": "https://sige.example.edu.ec/",
        "email_domain": "example.edu.ec",
        "phone": "0994390246",
        "address": "Av. Principal #123, Guayaquil, Ecuador",
        "website_url": "https://example.edu.ec",
        "logo_sign_in": "/media/repositorio/pdf/2024/01/logo-sign-in.png",
        "logo_sm_sign_in": "/media/repositorio/pdf/2024/01/logo-sm-sign-in.png",
        "logo_admin": "/media/repositorio/pdf/2024/01/logo-admin.png",
        "logo_sm_admin": "/media/repositorio/pdf/2024/01/logo-admin-sm.png",
        "favicon": "/static/v-1.0.0/img/favicon.png",
        "logo_email_banner": "/static/v-1.0.0/img/logo-email-banner.png",
        "logo_email_footer": "/static/v-1.0.0/img/logo-email-footer.png",
        "color_primary": "#04205b",
        "color_secondary": "#ffaa46",
        "social": {
            "facebook": "https://www.facebook.com/miinstitucion",
            "instagram": "https://www.instagram.com/miinstitucion",
            "twitter": null,
            "youtube": null
        },
        "platform_version": "0.1.5"
    },
    "status_code": 200
}
```

### Campos de Respuesta

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `name` | `string` | Nombre completo de la institución | `PlatformSetting.name` |
| `name_key` | `string` | Nombre corto / siglas | `PlatformSetting.name_key` |
| `slogan` | `string` | Slogan institucional | `PlatformSetting.slogan` |
| `base_path` | `string` | URL base de la plataforma | `PlatformSetting.base_path` |
| `email_domain` | `string` | Dominio del correo institucional | `PlatformSetting.email_domain` |
| `phone` | `string` | Teléfono institucional | `PlatformSetting.phone` |
| `address` | `string` | Dirección física | `PlatformSetting.address` |
| `website_url` | `string` | Sitio web institucional | `PlatformSetting.website_url` |
| `logo_sign_in` | `string` | URL del logo para login | `PlatformTemplate.logo_sign_in` |
| `logo_sm_sign_in` | `string` | URL del logo pequeño para login | `PlatformTemplate.logo_sm_sign_in` |
| `logo_admin` | `string` | URL del logo para admin/sidebar | `PlatformTemplate.logo_admin` |
| `logo_sm_admin` | `string` | URL del logo pequeño admin | `PlatformTemplate.logo_sm_admin` |
| `favicon` | `string` | URL del favicon | `PlatformTemplate.favicon` |
| `logo_email_banner` | `string` | URL del logo para banner de email | `PlatformTemplate.logo_email_banner` |
| `logo_email_footer` | `string` | URL del logo para footer de email | `PlatformTemplate.logo_email_footer` |
| `color_primary` | `string` | Color primario hex (ej: `#04205b`) | `PlatformTemplate.color_primary` |
| `color_secondary` | `string` | Color secundario hex (ej: `#ffaa46`) | `PlatformTemplate.color_secondary` |
| `social.facebook` | `string\|null` | URL de Facebook | `PlatformSetting.social_facebook` |
| `social.instagram` | `string\|null` | URL de Instagram | `PlatformSetting.social_instagram` |
| `social.twitter` | `string\|null` | URL de Twitter/X | `PlatformSetting.social_twitter` |
| `social.youtube` | `string\|null` | URL de YouTube | `PlatformSetting.social_youtube` |
| `platform_version` | `string` | Versión de la plataforma | `MY_VERSION_STATIC` |

---

## Casos de Uso

### 1. Carga post-login en App Móvil

```typescript
// React Native — llamar después del sign-in exitoso
async function loadBranding(accessToken: string) {
  const response = await fetch(`${API_BASE}/config/branding/`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  });
  const data = await response.json();
  
  if (data.isSuccess) {
    AppConfig.institutionName = data.data.name;
    AppConfig.logo = data.data.logo_sign_in;
    AppConfig.primaryColor = data.data.color_primary;
    AppConfig.secondaryColor = data.data.color_secondary;
  }
}
```

### 2. Cache de Configuración

> [!TIP]
> Como estos valores cambian raramente, se recomienda cachearlos localmente con un TTL largo (24 horas).

```javascript
const BRANDING_CACHE_KEY = 'platform_branding';
const BRANDING_CACHE_TTL = 24 * 60 * 60 * 1000; // 24 horas

async function getBranding() {
    const cached = await AsyncStorage.getItem(BRANDING_CACHE_KEY);
    if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        if (Date.now() - timestamp < BRANDING_CACHE_TTL) {
            return data;
        }
    }
    
    const response = await fetch(`${API_BASE}/config/branding/`);
    const fresh = await response.json();
    await AsyncStorage.setItem(BRANDING_CACHE_KEY, JSON.stringify({
        data: fresh.data,
        timestamp: Date.now()
    }));
    return fresh.data;
}
```

---

## Respuestas de Error

### Error Interno (500)

```json
{
    "success": false,
    "message": "Error al obtener configuración de branding: ...",
    "status_code": 500
}
```

---

## Testing

### cURL

```bash
# Local
curl -X GET http://127.0.0.1:8000/api/v1_0_0/config/branding/

# Producción
curl -X GET https://sige.example.edu.ec/api/v1_0_0/config/branding/
```

---

## Archivos Relacionados

| Archivo | Descripción |
|---------|-------------|
| `api/v1_0_0/config/controller.py` | `BrandingController` — APIView + IsAuthenticated |
| `api/v1_0_0/config/service.py` | `BrandingService` — lógica de negocio |
| `api/v1_0_0/config/views.py` | `BrandingConfigView` — wrapper del controller |
| `api/v1_0_0/config/urls.py` | Registro de URL `/branding/` |
| `core/models.py` | Modelos `PlatformSetting` y `PlatformTemplate` |
| `helpers/functions_helper.py` | `HelperFunctions.platform_global()` |

---

## Changelog

| Versión | Fecha | Descripción |
|---------|-------|-------------|
| 1.0.0 | 2026-03-04 | Versión inicial del endpoint de branding |
