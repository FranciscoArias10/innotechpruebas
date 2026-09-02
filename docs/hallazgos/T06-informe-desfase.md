# T6 · Informe de Desfase y Auditoría de Contratos API

| | |
|---|---|
| **Estado** | Entregado |
| **Fecha** | 2026-09-02 |
| **Rama** | `T06-informe-desfase` |
| **Módulos Auditados** | 12 especificaciones de API (Autenticación, Estudiante, Docente, Configuración, ChatIA) |

---

## 1. Resumen Ejecutivo

Durante la formalización de las 12 especificaciones OpenAPI 3.0 en la Tanda 1, se realizó una auditoría exhaustiva comparando la documentación original (`specs-originales/`) contra el comportamiento real del código y los dobles de prueba (`sige_ports/`).

Se identificaron **4 categorías principales de desfase**:
1. **Discrepancia en el sobre de respuesta (`success` vs `isSuccess`)**: 6 de 12 documentos indicaban `success`.
2. **Discrepancia en prefijos de URL (`/v1_0_0/` vs `/v1.0.0/`)**: Los documentos antiguos usaban guiones bajos en el prefijo de versión.
3. **Pérdida silenciosa de datos en serialización de listas (`set_data` en `MY_Response`)**: 5 endpoints devuelven respuestas sin la clave `data`.
4. **Header de Periodo (`X-Period-ID`)**: Inconsistencias en nombres de parámetros de periodo entre la documentación vieja y las vistas reales.

---

## 2. Tabla Priorizada de Hallazgos

| ID | Endpoint / Módulo | Discrepancia / Hallazgo | Gravedad | Impacto | Recomendación |
|---|---|---|---|---|---|
| **H1** | `MY_Response.set_data()` | Rechaza listas silenciosamente en 5 endpoints (`/student/attendance/`, `/student/grades/`, etc.) retornando respuestas 200 sin datos. | 🔴 Alta | La app móvil recibe respuestas vacías pero "exitosas". | Modificar `set_data()` o envolver listas en dict `{items: [...]}`. |
| **H2** | 6 de 12 Documentos OpenAPI | Documentan el campo del sobre como `"success": true` en lugar de `"isSuccess": true`. | 🔴 Alta | Falsos positivos en clientes móviles que evalúen `response.success`. | Corregir la documentación y usar `isSuccess` en los contratos OpenAPI. |
| **H3** | `SUBJECT_GRADES_API_SPEC.md` | El documento se contradice mezclando `success` e `isSuccess` en distintas respuestas del mismo archivo. | 🟡 Media | Confusión para desarrolladores frontend. | Estandarizar a `isSuccess` en `openapi/subject_grades.yaml`. |
| **H4** | Rutas de API en 12 Especificaciones | Documentadas con guión bajo (`/api/v1_0_0/`) mientras que el router de Django expone `/api/v1.0.0/`. | 🟢 Baja | Funciona por regex en Django, pero puede fallar en clientes estrictos. | Estandarizar todas las rutas OpenAPI a `/api/v1.0.0/`. |
| **H5** | `CHATIA_SESSION_MANAGEMENT` | Nuevo código de error `410 Gone` para sesiones eliminadas que no figuraba en la especificación inicial de ChatIA. | 🟢 Baja | Clientes móviles antiguos no manejan el estado 410. | Documentar el código 410 en `openapi/chatia_session_management.yaml`. |

---

## 3. Plan de Acción y Mitigación

1. **Contratos OpenAPI (Completado)**: Los 12 archivos YAML en `openapi/` han sido unificados para utilizar `isSuccess`, las rutas con formato `/api/v1.0.0/` y las estructuras completas con `allOf`.
2. **Servidor Mock (`npm run mock`)**: Sirve datos que cumplen el contrato estandarizado (`isSuccess`), permitiendo al equipo móvil desarrollar independientemente de los defectos del monolito.
3. **CI Contract Testing (Schemathesis)**: Ejecuta validaciones automatizadas para alertar en caso de que alguna respuesta en staging difiera del contrato acordado.
