# Contratos OpenAPI

Cada endpoint tiene su archivo aquí. Es la fuente de verdad: lo que dice este
archivo es lo que la API promete.

`device_register.yaml` es la plantilla — está completo y comentado. Cópienlo.

## Reglas

1. **El sobre se define una vez** en `components/schemas/Sobre` y se reutiliza
   con `allOf`. No lo repitan en cada respuesta.
2. **Documenten los errores**, no solo el 200. Un contrato que solo describe el
   camino feliz no sirve para probar nada.
3. **Ejemplos reales.** Los valores de `example` salen de `fixtures/`, que se
   generan del sistema corriendo. No inventen datos.
4. **Validen antes del PR.** Un YAML que no valida no se revisa.

## Los 12 documentos por formalizar

Están en el sistema real, en `api/v1_0_0/docs/`. Se los entregan aparte:

| Documento | Líneas | Prioridad |
|---|---|---|
| `AUTH_API_SPEC.md` | 571 | 1 — sin esto no hay nada |
| `STUDENT_SUMMARY_API_SPEC.md` | 309 | 2 |
| `STUDENT_SUBJECTS_API_SPEC.md` | 434 | 2 |
| `SUBJECT_GRADES_API_SPEC.md` | 310 | 2 |
| `STUDENT_ATTENDANCE_REPORT_API_SPEC.md` | 132 | 3 |
| `SUBJECT_CLASSMATES_API_SPEC.md` | 283 | 3 |
| `CLASS_PLANNING_API_SPEC.md` | 500 | 3 |
| `CALENDAR_API_SPEC_FRONTEND.md` | 497 | 3 |
| `SUBJECT_STUDENTS_TEACHER_API_SPEC.md` | 344 | 4 |
| `BRANDING_CONFIG_API_SPEC.md` | 208 | 4 |
| `CHATIA_PUBLIC_CONFIG_API_SPEC.md` | 259 | 4 |
| `CHATIA_SESSION_MANAGEMENT_API.md` | 201 | 4 |

Al pasarlos, **anoten toda diferencia entre el documento y lo que responde la
API real**. Ese registro es la entrega T6 y es lo más valioso de la tanda.
