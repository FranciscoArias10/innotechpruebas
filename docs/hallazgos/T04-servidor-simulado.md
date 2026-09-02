# T4 · Servidor Simulado (Mock Server) con Prism

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~4 h |
| **Rama** | `T04-mock-server` |
| **Material** | `package.json`, `README.md`, Prism CLI |

## Qué se pedía

Levantar un servidor simulado que sirva las 20 rutas de las 12 especificaciones OpenAPI 3.0 mediante un único comando (`npm run mock`) y documentar su procedimiento de uso en el README del repositorio.

## Método

1. **Configuración de Prism CLI**:
   Se instaló y configuró `@stoplight/prism-cli` dentro de `package.json` para ejecutar la simulación de la API en el puerto `4010`.

2. **Empaquetado de Especificaciones**:
   El comando `npm run mock` ejecuta el script `scripts/bundle_openapi.py` para asegurar que el contrato `openapi/openapi.yaml` esté actualizado con las 20 rutas antes de iniciar el servidor HTTP simulado.

3. **Documentación en README**:
   Se redactó la sección *Servidor Simulado (Mock)* en [README.md](file:///home/fkhalil/Desktop/sige-ube-api-pasantes/README.md) detallando las instrucciones de arranque y las URLs de prueba.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Script de Ejecución | `npm run mock` en `package.json` | Operativo | ✅ Válido |
| Servidor Simulado | Prism CLI v5.x | Escuchando en `http://127.0.0.1:4010` | ✅ Válido |
| Cobertura de Rutas | 20 rutas OpenAPI (12 módulos) | 100% de rutas servidas | ✅ Válido |
| Documentación | Sección *Servidor Simulado* en `README.md` | Redactada en raíz | ✅ Válido |

## Verificación

```bash
# 1. Iniciar servidor simulado
npm run mock

# 2. Probar petición cURL
curl -s http://127.0.0.1:4010/student/summary/ -H "Authorization: Bearer test" -H "X-Period-ID: 6"
```

El servidor responde en tiempo real con la estructura esperada: `{"isSuccess": true, "message": "...", "data": {...}}`.
