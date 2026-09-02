# SIGE-UBE · API móvil — repositorio de pasantías

Este repositorio es donde ustedes trabajan. **No contiene el sistema SIGE-UBE**
y no lo va a contener: todo lo que necesitan del sistema real llega por dos
caminos, los contratos en `openapi/` y los puertos en `sige_ports/`.

Pueden construir, correr y probar todo sin tener el monolito.

---

# 👉 Empieza aquí

**1. Lee estos tres archivos, en este orden:**

| | Archivo | Qué te dice |
|---|---|---|
| 1 | **[docs/GUIA-PASANTES.md](docs/GUIA-PASANTES.md)** | Cómo se trabaja aquí: el ciclo, las reglas, cómo se entrega |
| 2 | **[docs/CONVENCIONES-API.md](docs/CONVENCIONES-API.md)** | Las reglas que tu código tiene que cumplir |
| 3 | **[docs/TAREAS.md](docs/TAREAS.md)** | **Las tareas.** Están numeradas y en orden |

**2. Mira una entrega terminada.** La tarea T1 ya está resuelta, a propósito, para
que veas qué se espera: [docs/hallazgos/T01-auditoria-sobre.md](docs/hallazgos/T01-auditoria-sobre.md)

**3. Monta el entorno** (abajo) y toma la primera tarea libre: **T2**.

```bash
git checkout -b T02-openapi-auth
```

Trabajas, y cuando esté lista abres un pull request. Nadie aprueba su propio PR.

---

## Arranque

Necesitan **Python 3.11**, que es la versión del sistema real. Compruébenlo con
`python --version` antes de crear el entorno: con otra versión, pip puede
instalar dependencias distintas y el código se comporta diferente al integrarse.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py test
```

Si las 8 pruebas pasan, el entorno está listo. Levanten el servidor con
`python manage.py runserver` y el endpoint de ejemplo queda en
`http://127.0.0.1:8000/api/v1.0.0/movil/device/register/`.

### Servidor Simulado (Mock)

Para levantar un servidor simulado que sirva las 12 rutas OpenAPI con respuestas de ejemplo:

```bash
npm run mock
```

El servidor quedará escuchando en `http://127.0.0.1:4010`.
## Qué hay aquí

| Carpeta | Qué es | ¿Se integra al sistema? |
|---|---|---|
| `app/` | El código de ustedes: modelos, vistas, serializers, urls, pruebas | **Sí** |
| `sige_ports/` | Dobles de las piezas del sistema real | No — allá existe la versión de verdad |
| `tests_andamio/` | Prueba que los puertos respondan y estén documentados | No |
| `proyecto/` | Arnés mínimo de Django para poder correr | No |
| `openapi/` | Los contratos de la API | Se publican, no se integran |
| `fixtures/` | Respuestas de ejemplo generadas del sistema | No |
| `contrato/` | Pruebas que verifican que la API cumple su contrato | No |
| `docs/` | Cómo trabajar aquí | — |

La regla de oro: **si está en `app/`, viaja. Si no, es andamio.**

## Sobre el trabajo que hagan aquí

Todo lo que se escriba en este repositorio pertenece a la institución y se
integra a su sistema. No es un proyecto personal ni material de portafolio
publicable, y el contenido del repositorio —incluidas las especificaciones en
`specs-originales/`— es confidencial.

Lo concreto que se espera: no publicarlo, no copiarlo a repositorios propios y
no compartirlo fuera del equipo. Los detalles están en el convenio de pasantía;
esto es solo el recordatorio en el lugar donde van a trabajar.

## Por dónde seguir

1. [docs/GUIA-PASANTES.md](docs/GUIA-PASANTES.md) — cómo se trabaja, paso a paso.
2. [docs/CONVENCIONES-API.md](docs/CONVENCIONES-API.md) — las reglas que su código debe cumplir.
3. [docs/TAREAS.md](docs/TAREAS.md) — el backlog, con criterios de aceptación.

Léanlos en ese orden antes de escribir nada.

## Lo primero que van a encontrar

El sistema real tiene 12 documentos de especificación de API. **Siete dicen que
la respuesta trae un campo `success`. Es falso: siempre ha sido `isSuccess`.**
Uno de ellos usa las dos formas en el mismo archivo.

Eso es el trabajo, resumido: la documentación y la realidad se separaron, y hay
una app móvil que dejó de funcionar por cosas así. Lo que van a construir es la
manera de que no vuelva a pasar sin que nadie se entere.
