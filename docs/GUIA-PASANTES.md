# Guía de trabajo

## Cómo está montado esto, y por qué

Ustedes van a escribir endpoints para un sistema escolar que no van a ver. Eso
suena raro pero es normal: pasa en cualquier equipo grande donde nadie conoce
todo el código. Lo que hace falta no es el código ajeno, es el **contrato**.

Un contrato dice: «llama a esta función con estos argumentos y te devuelve un
diccionario con esta forma». Con eso alcanza para construir todo lo que rodea al
dato: la vista, la validación, los errores, las pruebas.

En este repositorio los contratos viven en `sige_ports/portal.py`, y su
implementación es falsa: lee un archivo de `fixtures/`. En el sistema real hay
un paquete con **el mismo nombre y las mismas firmas** cuya implementación
consulta la base de datos.

```python
from sige_ports import portal

datos = portal.resumen_estudiante(persona_id=7, periodo_id=6)
```

Esa línea funciona en los dos lados. Ustedes la escriben una vez.

## El ciclo de trabajo

### 1. Antes de escribir código, escriban el contrato

Cada endpoint nuevo arranca con su archivo en `openapi/`. Ahí definen la ruta,
el cuerpo que recibe, la forma exacta de la respuesta y **todos** los códigos de
error. Usen `openapi/device_register.yaml` de plantilla.

Esto no es burocracia. Es lo que otro equipo va a leer para consumir su endpoint,
y es contra lo que las pruebas de contrato van a verificar.

### 2. Escriban la prueba antes que la vista

En `app/tests/`. Como mínimo, cuatro casos por endpoint:

1. **Camino feliz** — entrada válida, respuesta correcta.
2. **Entrada inválida** — 400 con el detalle en `errors`.
3. **Sin autenticar** — 401.
4. **Repetición** — mandar lo mismo dos veces. Un cliente móvil reintenta
   siempre: al perder señal, al reinstalar, al rotar el token.

Si el endpoint escribe algo, agreguen el caso de permiso denegado: el usuario
autenticado que no debería poder tocar ese dato.

### 3. Ahora sí, la vista

En `app/views.py`, siguiendo el patrón de `DeviceRegisterView`. Está comentado
justo para eso.

### 4. Corran todo

```bash
python manage.py test
```

## Las reglas que no se negocian

**No importen nada del sistema real.** Ni `ctr`, ni `helpers`, ni `base`. Si su
endpoint necesita un dato que no está en `sige_ports/portal.py`, no inventen la
consulta: **pidan el puerto**, con la forma exacta que necesitan. Se los agregan
con su fixture y siguen.

Por qué importa: si inventan la consulta, están adivinando cómo funciona un
sistema que no ven, y el error aparece recién al integrar — cuando ya construyeron
encima.

**No modifiquen `sige_ports/` para que su prueba pase.** Si el doble no alcanza,
el problema está en el contrato, no en el doble.

**No toquen `proyecto/`.** Es el arnés. Si necesitan cambiar la configuración de
Django, es señal de que están haciendo algo que no corresponde a este repositorio.

**Todo es aditivo.** Ya hay una app móvil instalada en teléfonos reales
consumiendo esta API. Pueden agregar endpoints y campos opcionales. **No pueden**
cambiar la forma de una respuesta que ya existe: eso rompe a quien ya la usa.

## Cómo se entrega

Rama por tarea, con el nombre de la tarea:

```
git checkout -b T05-device-register
```

Pull request cuando esté lista. En la descripción, tres cosas:

- Qué endpoint es y su archivo en `openapi/`.
- Los casos que cubrieron en las pruebas.
- Qué puertos usaron, y si pidieron alguno nuevo.

Nadie aprueba su propio PR.

## Preguntas frecuentes

**¿Puedo ver el código del sistema para entender cómo funciona X?**
No, y no hace falta. Si el contrato no alcanza para construir, el contrato está
incompleto: eso es un hallazgo válido y hay que reportarlo. Que necesiten leer el
código para entender un endpoint es exactamente el problema que estamos
resolviendo.

**El fixture que necesito no existe.**
Pídanlo. Se generan desde el sistema corriendo, no se escriben a mano.

**¿Puedo cambiar la versión de Django o de DRF?**
No. Están fijadas a las del sistema real a propósito.

**Encontré algo que parece un error en el sistema.**
Repórtenlo con el detalle: qué endpoint, qué esperaba el documento, qué devolvió
la API. Eso es trabajo útil, no una molestia — es literalmente una de las tareas.
