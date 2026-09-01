# sige_ports — la costura

**Este paquete no viaja.** Cuando su código se integre al sistema real, esta
carpeta se queda aquí y allá se usa otra con el mismo nombre y las mismas
firmas, pero conectada a la base de datos de verdad.

Por eso funciona sin cambiar nada:

```python
# En app/views.py — se escribe una sola vez y sirve en los dos lados
from sige_ports import RespuestaApi, portal

datos = portal.resumen_estudiante(persona_id=7, periodo_id=6)
```

| Aquí (`sige-ube-api-pasantes`) | Allá (`sige-ube`) |
|---|---|
| `portal.resumen_estudiante` lee `fixtures/resumen_estudiante.json` | Consulta `ctr.models` y arma el mismo diccionario |
| `ModeloBase` declara los campos de auditoría | Es el `ModeloBase` real, con su manager y su caché |
| `RespuestaApi` arma el sobre `isSuccess/message/data` | Es `HelperResponseApi` |

## Reglas

1. **No modifiquen los dobles para que su prueba pase.** Si el doble no
   alcanza, el problema es el contrato: pídanlo.
2. **No agreguen puertos por su cuenta.** Un puerto es una promesa que alguien
   tiene que cumplir del otro lado.
3. **Prueben también el camino de error.** `representa_a` siempre devuelve
   `True` aquí; su prueba del caso `False` va con `mock.patch`.
