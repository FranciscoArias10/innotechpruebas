# H1 · Cinco endpoints del portal devuelven la respuesta sin datos

| | |
|---|---|
| **Gravedad** | Alta |
| **Rama revisada** | `pruebas` |
| **Estado** | Abierto — pendiente de decisión |

## Qué pasa

`MY_Response.set_data()` descarta en silencio cualquier cosa que no sea un
diccionario:

```python
def set_data(self, data=None):
    if not isinstance(data, dict):
        return self.data        # <- se va sin asignar nada
    self.data = data or {}
    return self
```

Cinco vistas le pasan `serializer.data` de un serializer con `many=True`, que es
una **lista**. La asignación no ocurre, `self.data` queda en `{}`, y como
`to_array()` solo incluye la clave cuando hay contenido, **la respuesta sale sin
`data`**.

## Comprobado ejecutando

```
LISTA (many=True) -> {'isSuccess': True, 'message': None}
DICT              -> {'isSuccess': True, 'message': None, 'data': {...}}
```

No hay error, no hay excepción, no hay log. Responde 200 y `isSuccess: true`.

## Endpoints afectados

| Endpoint | Vista | Archivo |
|---|---|---|
| `GET /representative/wards/` | `RepresentedStudentsView` | `api/v1_0_0/representative/views.py:60` |
| `GET /student/grades/` | `StudentGradesView` | `api/v1_0_0/student/views.py:641` |
| `GET /student/attendance/` | `StudentAttendanceView` | `api/v1_0_0/student/views.py:674` |
| `GET /teacher/schedule/` | `TeacherScheduleView` | `api/v1_0_0/teacher/views.py:59` |
| `GET /teacher/classes/` | `TeacherClassesView` | `api/v1_0_0/teacher/views.py:89` |

Un cliente que llame a cualquiera de ellos recibe una respuesta que dice que todo
salió bien y no trae nada. Es el peor modo de fallo posible: silencioso y
aparentemente exitoso.

## Por qué importa para este repositorio

Los fixtures de `fixtures/` describen **el contrato**, es decir lo que estos
endpoints deberían devolver — no lo que devuelven hoy. Cuando corran las pruebas
de contrato de T5 contra staging, estos cinco van a fallar. **Eso es correcto:
el defecto está en el código, no en el contrato.**

No ajusten los fixtures para que las pruebas pasen. Repórtenlo.

## Arreglo propuesto

Dos caminos, y la decisión no es de los pasantes:

1. **Envolver la lista**: `set_data(data={'items': serializer.data})`. Cambia la
   forma de la respuesta, así que rompe a cualquier cliente que ya funcione con
   estos endpoints — aunque hoy ninguno puede estar funcionando, porque no
   devuelven nada.
2. **Hacer que `set_data` acepte listas**. Toca una clase base que usa todo el
   sistema; hay que revisar qué más depende de que rechace no-diccionarios.

## Cómo se encontró

Contrastando los fixtures del repositorio contra el código real de la rama
`pruebas`, y ejecutando `set_data` con una lista para confirmarlo en vez de
deducirlo leyendo.
