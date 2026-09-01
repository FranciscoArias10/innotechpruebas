# Backlog

En orden. No arranquen una tanda sin cerrar la anterior: cada una construye la
herramienta que la siguiente necesita.

Las horas son estimaciones para alguien que ya sabe Python y algo de Django. Si
están aprendiendo Django sobre la marcha, sumen entre 40 y 60 horas al total.

---

## Tanda 1 · El contrato · 70–115 h

Ninguna de estas tareas toca el sistema. Sirven para levantar la red de seguridad
que hoy no existe.

### T1 · Auditoría del sobre de respuesta · 4–6 h
Recorrer las 12 especificaciones del sistema y listar cuáles dicen `success` y
cuáles `isSuccess`. Ya sabemos que son 7 y 6, y que `SUBJECT_GRADES` usa las dos.

**Entregable:** tabla endpoint → qué dice el documento → qué devuelve la API.
**Listo cuando:** están las 12 revisadas y la tabla dice cuál corregir.

### T2 · Primer OpenAPI: autenticación · 6–10 h
Formalizar `AUTH_API_SPEC.md` (571 líneas: sign-in, refresh, recuperación de
clave y de usuario, cambio de clave) a OpenAPI 3. Plantilla:
`openapi/device_register.yaml`.

**Listo cuando:** valida sin advertencias y describe todos los códigos de error,
no solo el 200.

### T3 · Las 11 especificaciones restantes · 30–40 h
Unas 3 h cada una. Empiecen por las del rol estudiante.

**Listo cuando:** los 12 archivos validan y comparten los mismos `components`
para el sobre.

### T4 · Servidor simulado · 4–8 h
Levantar un mock desde el OpenAPI (Prism u otro) con un comando.

**Listo cuando:** `npm run mock` —o el equivalente— sirve las 12 rutas con
ejemplos, y está documentado en el README.

### T5 · Pruebas de contrato en CI · 16–24 h
Schemathesis contra staging, corriendo en cada push. Ver `contrato/README.md`.

**Listo cuando:** la CI falla si una respuesta deja de cumplir su contrato.

### T6 · Informe de desfase · 8–16 h
Correr T5 contra staging y documentar cada diferencia.

**Listo cuando:** hay una tabla de hallazgos priorizada. Esta es la entrega más
valiosa de la tanda: nadie sabe hoy qué tan lejos está la API de su documentación.

---

## Tanda 2 · Endpoints propios · 50–73 h

Modelos nuevos, tabla nueva, cero dependencia del dominio del sistema. Son de
ustedes de punta a punta: modelo, migración, serializer, vista, pruebas y OpenAPI.

`POST /movil/device/register/` ya está hecho y es la plantilla.

### T7 · `GET /movil/app/version/` · 10–14 h
Versión mínima soportada y si hay que forzar actualización. Sin autenticación
—la app lo consulta antes de que alguien inicie sesión— pero con límite de tasa.

### T8 · `GET|PUT /movil/notifications/preferences/` · 12–16 h
Qué avisos quiere recibir cada usuario. El PUT es parcial y idempotente.

### T9 · `POST /movil/feedback/` · 10–14 h
Reporte de problema desde la app, con versión, plataforma y modelo. Límite de
tasa más estricto: es un formulario abierto.

### T10 · Panel de administración · 6–10 h
Registrar los tres modelos en el admin de Django, con listados y filtros útiles.
Quien opere el sistema necesita ver esto sin entrar a la base.

---

## Tanda 3 · Contra puertos · 35–50 h

Aquí ya usan datos del sistema real, siempre a través de `sige_ports.portal`.

### T11 · `GET /representative/students/<id>/grades/` · 10–14 h
Notas de un estudiante representado. El puerto entrega los datos; ustedes
resuelven la forma, la paginación y los errores.

**Ojo con el 403:** verificar con `portal.representa_a()` que sea suyo. La prueba
del caso denegado es obligatoria y se hace con `mock.patch`.

### T12 · `GET /representative/students/<id>/attendance/` · 8–12 h
### T13 · `GET /representative/students/<id>/schedule/` · 8–12 h
### T14 · `GET /representative/students/<id>/summary/` · 8–12 h

Los cuatro comparten la verificación de parentesco. Extráiganla a un permiso
reutilizable en la primera, no la copien cuatro veces.

---

## Fuera de alcance

- Cualquier cosa del módulo DECE. Son datos psicosociales de menores bajo LOPDP.
- Escribir sobre notas, matrícula o calificaciones.
- Conectarse a la base de producción, en cualquier circunstancia.

Si una tarea parece exigir algo de esta lista, está mal planteada. Pregunten.
