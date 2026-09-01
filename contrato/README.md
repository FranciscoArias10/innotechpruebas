# Pruebas de contrato

Verifican que la API **cumple lo que su documento promete**. No prueban que el
cálculo sea correcto — prueban que la promesa se cumple.

| | Prueba unitaria (`app/tests/`) | Prueba de contrato (aquí) |
|---|---|---|
| Pregunta | ¿El registro guardó bien? | ¿La respuesta tiene la forma documentada? |
| Necesita | El código | El OpenAPI y una URL |
| Detecta | Un error de lógica | Un cambio de **forma** |

La segunda columna es la que faltaba: el sistema tiene 94 archivos de prueba y
**ninguno** verifica la API. Por eso la app móvil se desactualizó durante meses
sin que nadie lo notara.

## Nunca contra producción

Schemathesis **genera entradas basura a propósito**: ids negativos, cadenas
larguísimas, fechas imposibles. Eso es lo que le da valor, y es exactamente lo
que no se le hace a un servidor con datos reales.

Antes de correrlo, confirmen que `--base-url` apunta a staging. Si tienen duda,
pregunten en vez de probar.

## Cómo se corre

```bash
schemathesis run ../openapi/device_register.yaml \
  --base-url https://sige.innotech-solutions.com.ec/api/v1.0.0 \
  -H "Authorization: Bearer $TOKEN" \
  --checks all
```

Schemathesis lee el contrato, llama a la API real y compara. Además genera
entradas raras a partir del esquema —ids negativos, cadenas larguísimas, fechas
imposibles— y encuentra los 500 que nadie probó. En una API sin pruebas es casi
seguro que aparecen varios.

## Qué hacer con lo que encuentren

Cada diferencia entre el documento y la respuesta real es un hallazgo. Anótenlo
así:

| Endpoint | Dice el documento | Devuelve la API | ¿Cuál está mal? |
|---|---|---|---|
| `/student/summary/` | `success` | `isSuccess` | El documento |

La última columna no siempre es obvia y no siempre les toca decidirla a ustedes.
Reporten con el detalle y que lo resuelva quien conoce el dominio.

## Meta

Que esto corra en CI en cada cambio. Cuando esté puesto, la próxima vez que una
respuesta cambie de forma se entera la CI, no el usuario de la app.
