# T7 · Endpoint `GET /movil/app/version/`

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~8 h |
| **Rama** | `T07-app-version` |
| **Material** | `openapi/app_version.yaml`, `app/models.py`, `app/views.py`, `app/tests/test_app_version.py` |

## Qué se pedía

Implementar el endpoint `GET /movil/app/version/` para consultar la versión mínima soportada y si hay que forzar actualización. Debe funcionar sin autenticación (ya que la app lo consulta antes del inicio de sesión) e implementar un límite de tasa (*rate limit*) propio y estricto.

## Método

1. **Definición del Contrato (OpenAPI)**:
   Se definió `openapi/app_version.yaml` documentando las respuestas de éxito (`200`), errores de validación (`400`) y límite de tasa excedido (`429`). Se incluyó soporte para filtrar por plataforma (`android` o `ios`) vía query parameter.

2. **Modelo y Migración**:
   Se implementó el modelo `VersionAppMovil` heredando de `ModeloBase` para cumplir con la estructura del sistema real (sige_ports). Se separaron los registros por plataforma (Android / iOS) permitiendo flexibilidad a futuro.

3. **Límite de Tasa (Throttling) Aislado**:
   Se creó una clase propia `AppVersionRateThrottle` en `app/throttling.py` (con límite de 10 peticiones por minuto) sin contaminar la configuración global de `proyecto/settings.py`, respetando las convenciones arquitectónicas del proyecto.

4. **Vista y Pruebas Unitarias**:
   Se estructuró `AppVersionView` con `permission_classes = []` para acceso público y se integraron 3 pruebas automatizadas (`test_app_version.py`) validando escenarios positivos, comportamiento por defecto y parámetros inválidos.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Contrato | `openapi/app_version.yaml` | Creado | ✅ Válido |
| Modelo | `VersionAppMovil` | Migración ejecutada | ✅ Válido |
| Límite de Tasa | `AppVersionRateThrottle` | Activo (10/minuto) | ✅ Válido |
| Pruebas (TDD) | 3 Pruebas (Camino feliz y errores) | 100% pasando | ✅ Válido |

## Verificación

```bash
# 1. Levantar servidor local
python manage.py runserver

# 2. Probar petición (Sin autenticación)
curl -X GET "http://127.0.0.1:8000/api/v1.0.0/movil/app/version/?plataforma=ios"
```

El servidor responde estructuradamente bajo la convención de `isSuccess`:
```json
{
    "isSuccess": true,
    "message": "Versión recuperada con éxito.",
    "data": {
        "plataforma": "ios",
        "version_minima": "1.0.0",
        "version_actual": "1.0.0",
        "forzar_actualizacion": false
    }
}
```
