# Convenciones de la API

Copiadas del sistema real. No son preferencias: si su código no las cumple, no
se puede integrar.

## El sobre de respuesta

**Siempre** el mismo, en éxito y en error:

```json
{ "isSuccess": true, "message": "Dispositivo registrado.", "data": { } }
```

| Campo | Cuándo aparece |
|---|---|
| `isSuccess` | Siempre. Booleano |
| `message` | Siempre. Texto para la persona, en español |
| `data` | Cuando hay datos. Objeto |
| `errors` | Solo en validación fallida. `{campo: [mensajes]}` |

> **El campo es `isSuccess`, no `success`.** Siete de los doce documentos del
> sistema dicen `success` y están equivocados — el código nunca devolvió eso.
> Corregirlos es la tarea T1.

Toda respuesta sale por `RespuestaApi`. Nunca devuelvan un `Response` de DRF
directo: es la única forma de que el sobre no se desarme con el tiempo.

## Códigos de estado

| Código | Cuándo |
|---|---|
| 200 | Consulta correcta, o escritura que actualizó algo existente |
| 201 | Escritura que creó algo |
| 400 | El cuerpo no pasó validación. Va con `errors` |
| 401 | Falta el JWT, o está vencido |
| 403 | Autenticado, pero ese dato no es suyo |
| 404 | El recurso no existe |
| 429 | Pasó el límite de tasa |
| 500 | Falla inesperada. **Nunca** con el detalle técnico en `message` |

El 403 es el que más se olvida y el más importante: un representante pidiendo
las notas de un estudiante que no representa **no** es un 404.

## Autenticación

JWT en `Authorization: Bearer <token>`. El access dura **15 minutos**, el refresh
rota y el anterior queda en lista negra.

Consecuencia práctica: el cliente tiene que renovar solo, sin sacar al usuario de
la pantalla. Sus pruebas deben cubrir el token vencido.

## El header de periodo

Casi todo el sistema es por periodo lectivo. Se manda así:

```
X-Period-ID: 6
```

> **Trampa documentada:** es el id de la tabla `periodo`, **no** de
> `periodolectivo`. Son tablas distintas con nombres casi iguales. Confundirlas
> devuelve datos de otro periodo sin dar error.

## Nombres

- Rutas en inglés, minúsculas, con barra final: `/device/register/`
- Campos del JSON en inglés y `snake_case`: `app_version`, `total_subjects`
- Código, comentarios y `message` en español
- Un endpoint, una responsabilidad

## Versionado

La API es `v1.0.0` y hay clientes instalados usándola.

**Permitido:** endpoints nuevos, campos nuevos opcionales, códigos de error nuevos
documentados.

**Prohibido sin versión nueva:** renombrar o quitar un campo, cambiar su tipo,
cambiar el significado de un código, volver obligatorio algo que era opcional.

Ante la duda: si un cliente viejo se rompe, es cambio mayor.

## Pruebas

Mínimo por endpoint: camino feliz, entrada inválida, sin autenticar, repetición.
Los que escriben, además: permiso denegado.

Una prueba que solo verifica el 200 no prueba nada.
