# Integración — para quien mantiene SIGE-UBE

> Este documento no es para los pasantes. Es el procedimiento para llevar su
> trabajo al sistema real.

## La idea en una frase

Su código importa `sige_ports`. Aquí ese paquete son dobles; en `sige-ube` es un
paquete con **el mismo nombre y las mismas firmas** conectado a la base real. Por
eso `app/` se copia tal cual y funciona: lo único que cambia es qué hay detrás
del import.

| En el repo de pasantes | ¿Viaja? |
|---|---|
| `app/` | **Sí** — se copia como `pasantes_movil/` |
| `sige_ports/` | No — allá existe la versión real |
| `proyecto/`, `fixtures/` | No — son andamio |
| `openapi/`, `contrato/` | Se publican junto a las specs; no son código del sistema |

---

## Preparación, una sola vez

### 1. Crear `sige-ube/sige_ports/__init__.py`

```python
# -*- coding: utf-8 -*-
"""Fachada para el código escrito en el repositorio de pasantías.

Mismo nombre y mismas firmas que el paquete de dobles de aquel repositorio,
pero conectado al sistema real. Gracias a esto su código se integra sin
modificaciones.
"""
from helpers.model_helper import ModeloBase
from helpers.response_api_helper import HelperResponseApi as RespuestaApi
from sige_ports import portal

__all__ = ['ModeloBase', 'RespuestaApi', 'portal']
```

### 2. Crear `sige-ube/sige_ports/portal.py`

Una función por puerto, con **la firma y la forma de retorno idénticas** a las
documentadas en el repositorio de pasantes. Aquí sí va la consulta real:

```python
def resumen_estudiante(persona_id, periodo_id):
    """Ver el contrato en sige-ube-api-pasantes/sige_ports/portal.py"""
    # La lógica ya existe: api/v1_0_0/student/views.py::StudentSummaryView.
    # Extráela a esta función y haz que la vista la use también, para que no
    # queden dos implementaciones del mismo cálculo.
    ...
```

**Regla:** si cambia la forma que devuelve un puerto, se avisa y se actualiza el
doble del otro repositorio el mismo día. Un puerto que se desincroniza reproduce
exactamente el problema que estamos resolviendo.

### 3. Preparar staging

- Base con datos sintéticos (`limpiar_bd_produccion` + los `seed_*_demo`).
- `.env` con credenciales inventadas. Nada de `credentials/` ni el `.p12`.
- Un usuario JWT por pasante, con rol acotado vía `Modulo` / `GrupoModulo`.
- El origen del mock agregado a `CORS_ALLOWED_ORIGINS`.

### 4. Cerrar los dos huecos de configuración

- **Throttling:** `MY_REST_FRAMEWORK` no define `DEFAULT_THROTTLE_CLASSES` ni
  `DEFAULT_THROTTLE_RATES`. El arnés de los pasantes ya los trae puestos
  (`proyecto/settings.py`); cópienlos al sistema real antes de exponer nada.
- **CORS:** en `sige/settings.py`, `CORS_ALLOWED_ORIGIN_REGEXES` recibe la misma
  lista literal que `CORS_ALLOWED_ORIGINS`. Como regex y con `re.match`,
  `http://localhost` acepta también `http://localhost.loquesea.com`. **Esa línea
  sobra: bórrenla.**

---

## Por cada entrega

### 1. Revisar el pull request en el repositorio de pasantes

Lista de verificación:

- [ ] `app/` no importa `ctr`, `helpers` ni `base` — solo `sige_ports`
- [ ] No hay cambios en `sige_ports/` ni en `proyecto/`
- [ ] Toda respuesta sale por `RespuestaApi` (sobre `isSuccess`/`message`/`data`)
- [ ] Existe el archivo OpenAPI del endpoint
- [ ] Las pruebas cubren: feliz, inválido, sin autenticar, repetición; y permiso
      denegado si escribe
- [ ] El cambio es **aditivo** — no altera la forma de ninguna respuesta existente

### 2. Copiar la app

```bash
cp -r sige-ube-api-pasantes/app  sige-ube/pasantes_movil
rm -rf sige-ube/pasantes_movil/migrations/0*.py
```

Se borran las migraciones a propósito: se regeneran del lado del sistema (paso 5).

Editar `pasantes_movil/apps.py` y `pasantes_movil/urls.py` para que digan
`pasantes_movil` en vez de `app`.

### 3. Registrar la app — una línea

En `base/my_base.py`, dentro de `MY_INSTALLED_APPS`:

```python
    'pasantes_movil',
```

### 4. Registrar las rutas — una línea

En `api/v1_0_0/urls.py`:

```python
    re_path(r'^movil/', include('pasantes_movil.urls')),
```

### 5. Generar la migración — **el paso que se olvida**

```bash
python manage.py makemigrations pasantes_movil
```

> **Por qué es fácil olvidarlo:** este repositorio tiene 173 migraciones en disco
> y solo 9 rastreadas por git — `**/migrations/*.py` está en `.gitignore`. La
> migración que ellos generaron **no llega**. Si no la generan aquí, la tabla no
> existe y falla en el servidor, no en pruebas.

### 6. Correr sus pruebas contra el sistema real

```bash
python manage.py test pasantes_movil
```

Aquí es donde aparece cualquier supuesto falso sobre un puerto. Es el punto del
diseño: revienta en su máquina, antes de desplegar, no en producción.

### 7. Desplegar

`migrate` en el servidor. Recuerden que las migraciones no viajan por git: hay
que generarlas allá o llevarlas a mano, como con cualquier otro cambio de modelo.

---

## Qué mirar en la revisión

Más allá de la lista de arriba, tres cosas que un pasante suele pasar por alto:

1. **El 403 contra el 404.** Un representante pidiendo notas de un estudiante
   ajeno debe recibir 403. Devolver 404 filtra información y devolver 200 es un
   incidente de datos.
2. **La transacción.** Toda escritura que toque más de una fila va en
   `transaction.atomic()`.
3. **Qué termina en el log.** Ningún `message` de error debe llevar el detalle
   técnico, y ningún log debe llevar datos personales.

## Si el trabajo crece

Cuando `pasantes_movil` sea grande, conviene partirlo por dominio
(`movil_dispositivos`, `movil_representante`). La frontera de app ya está puesta:
partirla después es barato.
