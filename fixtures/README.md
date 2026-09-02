# fixtures — respuestas de ejemplo

**No viajan.** Son la materia prima de los dobles de `sige_ports`.

## De dónde salen

Se **generan** desde el sistema real corriendo con datos sintéticos, con un
comando de Django que recorre los endpoints y guarda la respuesta tal cual.
No se escriben a mano.

Eso importa: un fixture escrito a mano envejece y miente. Uno generado se
vuelve a generar y muestra el cambio. De hecho, comparar la versión vieja con
la nueva es la forma más barata de detectar que un endpoint cambió de forma —
que es exactamente lo que le pasó a la app móvil heredada sin que nadie se
diera cuenta.

## Si les falta uno

Pídanlo. **No lo inventen.** Un fixture inventado los hace construir contra una
forma que no existe, y el error aparece recién al integrar.
