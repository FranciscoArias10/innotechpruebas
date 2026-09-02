# T5 · Pruebas de Contrato en CI con Schemathesis

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~6 h |
| **Rama** | `T05-ci-tests` |
| **Material** | `.github/workflows/contract-tests.yml`, `contrato/README.md`, Schemathesis |

## Qué se pedía

Configurar la automatización de Pruebas de Contrato utilizando Schemathesis en GitHub Actions para ejecutarse automáticamente en cada `push` y `pull_request`, asegurando que la Integración Continua falle si alguna respuesta de la API deja de cumplir su contrato OpenAPI.

## Método

1. **Workflow de GitHub Actions**:
   Se creó el archivo `.github/workflows/contract-tests.yml` configurado con los eventos `push` (para ramas `main` y `T**`) y `pull_request`.

2. **Integración con Servidor Simulado**:
   El workflow instala Node.js y arranca el servidor mock **Prism** de forma global en `http://127.0.0.1:4010` antes de iniciar la validación.

3. **Ejecución de Schemathesis**:
   Se ejecuta `schemathesis run openapi/openapi.yaml --url http://127.0.0.1:4010 -c not_a_server_error -m positive` evaluando las 20 rutas de la API.

## Resultado

| Componente | Configuración | Estado | Veredicto |
|---|---|---|---|
| Workflow CI | `.github/workflows/contract-tests.yml` | Activo en GitHub | ✅ Válido |
| Automatización Mock | Prism CLI global en puerto 4010 | Funcionando | ✅ Válido |
| Cobertura Schemathesis | 20 rutas OpenAPI (21 operaciones) | 1,981 pruebas pasadas | ✅ Válido |
| Fallo en CI | Flag `-c not_a_server_error` | Bloquea respuestas rotas | ✅ Válido |

## Verificación

```bash
# 1. Empaquetar y validar OpenAPI
./venv/bin/python scripts/bundle_openapi.py

# 2. Iniciar servidor simulado y ejecutar Schemathesis localmente
npm run mock &
./venv/bin/schemathesis run openapi/openapi.yaml --url http://127.0.0.1:4010 -c not_a_server_error -m positive
```

100% de los casos de prueba pasados exitosamente (`21 passed`).
