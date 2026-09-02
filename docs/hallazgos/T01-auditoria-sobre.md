# T1 · Auditoría del sobre de respuesta

| | |
|---|---|
| **Estado** | Entregado |
| **Tiempo** | ~5 h |
| **Rama** | `T01-auditoria-sobre` |
| **Material** | `specs-originales/` (12 documentos) |

## Qué se pedía

Determinar, para cada una de las 12 especificaciones, si el campo del sobre de
respuesta que documenta coincide con el que la API devuelve de verdad.

## Método

Tres pasos. Los tres son reproducibles: cualquiera puede correrlos y obtener lo
mismo.

**1. Contar qué dice cada documento.**

```bash
for f in specs-originales/*.md; do
  printf "%-42s %s %s\n" "$(basename $f)" \
    "$(grep -c '"success"' $f)" "$(grep -c '"isSuccess"' $f)"
done
```

**2. Rastrear qué produce el código.** No alcanza con mirar una vista: hay que
seguir la cadena hasta donde se arma el diccionario.

```
vista  ->  controller / service  ->  HelperResponseApi.to_dict()
       ->  MY_Response.to_array()  ->  {"isSuccess": ..., "message": ...}
```

**3. Buscar excepciones.** Un solo endpoint que no pase por ahí invalidaría la
conclusión, así que se revisaron los 12 archivos de vistas y controladores.

## Resultado

| Documento | Dice `success` | Dice `isSuccess` | Veredicto |
|---|---:|---:|---|
| `AUTH_API_SPEC.md` | 12 | 0 | ❌ Incorrecto |
| `BRANDING_CONFIG_API_SPEC.md` | 2 | 0 | ❌ Incorrecto |
| `CHATIA_PUBLIC_CONFIG_API_SPEC.md` | 3 | 0 | ❌ Incorrecto |
| `STUDENT_SUMMARY_API_SPEC.md` | 3 | 0 | ❌ Incorrecto |
| `SUBJECT_CLASSMATES_API_SPEC.md` | 2 | 0 | ❌ Incorrecto |
| `SUBJECT_STUDENTS_TEACHER_API_SPEC.md` | 2 | 0 | ❌ Incorrecto |
| `SUBJECT_GRADES_API_SPEC.md` | 1 | 7 | ⚠️ Se contradice |
| `CALENDAR_API_SPEC_FRONTEND.md` | 0 | 2 | ✅ Correcto |
| `CHATIA_SESSION_MANAGEMENT_API.md` | 0 | 5 | ✅ Correcto |
| `CLASS_PLANNING_API_SPEC.md` | 0 | 2 | ✅ Correcto |
| `STUDENT_ATTENDANCE_REPORT_API_SPEC.md` | 0 | 1 | ✅ Correcto |
| `STUDENT_SUBJECTS_API_SPEC.md` | 0 | 2 | ✅ Correcto |

**6 correctos, 6 incorrectos, 1 de ellos contradiciéndose a sí mismo.**

## Por qué estamos seguros del lado del código

Todas las respuestas se arman en un único lugar, `MY_Response.to_array()`, y la
clave está escrita literalmente ahí: `"isSuccess"`. No hay forma de que un
endpoint devuelva `success` sin saltarse el helper.

Se verificó que ninguno se lo salta. Dos casos parecían excepciones y no lo son:

- `auth/views.py` no importa el helper — pero sus clases son envoltorios vacíos
  de `auth/controller.py`, que sí lo usa.
- `config/` y `period/` tampoco lo importan en sus vistas — delegan en sus
  `service.py`, que sí lo usan.

## Hallazgos

### H1 · Seis documentos describen un campo que la API nunca devuelve
**Gravedad: alta.** Cualquiera que integre leyendo esos documentos escribe
`respuesta.success`, recibe `undefined` y trata toda respuesta correcta como
fallida. Es un error silencioso: no revienta, solo se comporta mal.

### H2 · `SUBJECT_GRADES_API_SPEC.md` se contradice
**Gravedad: alta.** Usa las dos formas en el mismo archivo. Quien lo lea va a
creer que depende del endpoint y va a programar las dos ramas.

### H3 · El prefijo de versión también difiere (hallazgo lateral)
**Gravedad: baja.** Los documentos escriben las rutas como `/api/v1_0_0/...`
mientras que el router registra `r'^v1.0.0/'`. Funciona por accidente: el punto
sin escapar en una expresión regular acepta cualquier carácter, así que `v1.0.0`
también hace match con `v1_0_0`. Conviene unificar y escapar los puntos.

## Qué NO se revisó

Para que nadie asuma de más:

- Solo se auditó **el nombre del campo del sobre**. La forma de `data` no se tocó.
- No se verificó si `message` viene siempre, ni si es null en éxito.
- No se auditaron los códigos de estado ni la forma de `errors`. Eso es T6.

## Recomendación

**Corregir los documentos, no el código.**

Hay una app móvil instalada en teléfonos reales que consume `isSuccess`.
Renombrar el campo en el código arreglaría la documentación y rompería a todos
los clientes que ya funcionan. La documentación es lo que está mal, y es lo
barato de arreglar.

Al pasar cada documento a OpenAPI (T2 y T3), usar `isSuccess` y dejar anotado el
cambio.
