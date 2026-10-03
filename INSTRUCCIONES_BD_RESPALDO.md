# Guía de Restauración y Limpieza de Base de Datos (SIGE UNIEBEC)

> **Destinatario:** Esta guía está diseñada para que un agente de IA o desarrollador en el proyecto **`sige ube api` (backend)** configure la base de datos PostgreSQL local a partir del respaldo proporcionado, la limpie y la deje lista para el entorno de desarrollo.

---

## 1. Contexto y Archivos

- **Archivo de respaldo:** `respaldo-pasantes-2026-09-30.dump` (Formato binario de PostgreSQL, ~3.0 MB).
- **Ruta actual del archivo:**  
  `/home/fkhalil/Desktop/Proyectos/App UNIEBEC/respaldo-pasantes-2026-09-30.dump`  
  *(Puedes copiarlo a la raíz de tu proyecto backend o referenciarlo directamente desde esta ruta).*
- **Nombre de la base de datos objetivo:** `uniebec_dev`
- **Entorno del sistema:** Arch Linux con PostgreSQL instalado (`psql`, `createdb`, `pg_restore` en `/usr/bin/`).

> [!WARNING]
> **No subir el respaldo al repositorio:** Asegúrate de que `*.dump`, `*.backup` y `.env` estén en el `.gitignore` de tu proyecto.

---

## 2. Paso a Paso para Restaurar y Limpiar

### Paso 1: Iniciar el servicio de PostgreSQL en el sistema
El servicio de PostgreSQL en Arch Linux debe estar activo.

```bash
# Verificar estado
systemctl status postgresql

# Iniciar servicio (requiere permisos sudo)
sudo systemctl start postgresql
```

*(Si el cluster nunca fue inicializado en Arch Linux, inicializar con: `sudo -u postgres initdb -D /var/lib/postgres/data` y luego iniciar el servicio).*

---

### Paso 2: Crear la base de datos `uniebec_dev`
Crea la base de datos de desarrollo:

```bash
createdb uniebec_dev
```

*Si tu configuración de PostgreSQL requiere ejecutar como el usuario `postgres`:*
```bash
sudo -u postgres createdb uniebec_dev
```

---

### Paso 3: Restaurar el archivo `.dump`
Ejecuta la restauración ignorando dueños y listas de control de acceso previas (`--no-owner --no-acl`):

```bash
pg_restore --no-owner --no-acl -d uniebec_dev "/home/fkhalil/Desktop/Proyectos/App UNIEBEC/respaldo-pasantes-2026-09-30.dump"
```

*O ejecutándolo como superusuario `postgres`:*
```bash
sudo -u postgres pg_restore --no-owner --no-acl -d uniebec_dev "/home/fkhalil/Desktop/Proyectos/App UNIEBEC/respaldo-pasantes-2026-09-30.dump"
```

> [!NOTE]
> Es normal que `pg_restore` emita algunas advertencias (`WARNING`) sobre roles o extensiones existentes, siempre y cuando finalice cargando las tablas.

---

### Paso 4: Limpieza y Estandarización de Usuarios y Contraseñas
**¿Por qué es necesario?**  
En el respaldo, ninguna contraseña sirve para ingresar y los nombres de usuario aún reflejan nombres reales. Debes ejecutar el siguiente script SQL sobre la base `uniebec_dev`.

#### Consulta SQL:
```sql
UPDATE auth_user SET
  username   = 'usuario' || id,
  first_name = '',
  last_name  = '',
  email      = 'usuario' || id || '@ejemplo.test',
  password   = 'pbkdf2_sha256$600000$w7hIyIoONpDfiaGEdLwYt1$7MKVLruZ7T5j4QHL0VhjfyplajWzRtVjiAfMnzj/3G8=';
```

#### Comando bash directo para ejecutarlo:
```bash
psql -d uniebec_dev -c "UPDATE auth_user SET username = 'usuario' || id, first_name = '', last_name = '', email = 'usuario' || id || '@ejemplo.test', password = 'pbkdf2_sha256\$600000\$w7hIyIoONpDfiaGEdLwYt1\$7MKVLruZ7T5j4QHL0VhjfyplajWzRtVjiAfMnzj/3G8=';"
```

*O si usas el usuario postgres:*
```bash
sudo -u postgres psql -d uniebec_dev -c "UPDATE auth_user SET username = 'usuario' || id, first_name = '', last_name = '', email = 'usuario' || id || '@ejemplo.test', password = 'pbkdf2_sha256\$600000\$w7hIyIoONpDfiaGEdLwYt1\$7MKVLruZ7T5j4QHL0VhjfyplajWzRtVjiAfMnzj/3G8=';"
```

---

## 3. Resultado de las Credenciales de Prueba

Tras ejecutar la limpieza:

- **Usuario:** `usuario` seguido del ID numérico (`usuario15`, `usuario42`, `usuario230`...).
- **Contraseña universal:** **`Pasantes2026*`**
- **Formato del Hash:** Django `pbkdf2_sha256` (600.000 iteraciones).
- **Correos:** Formato `usuario<id>@ejemplo.test`.
- **Cédulas anonimizadas:** Inician en `30...`.

---

## 4. Verificación Rápida

Ejecuta esta consulta para confirmar que los datos se actualizaron correctamente:

```bash
psql -d uniebec_dev -c "SELECT id, username, email FROM auth_user ORDER BY id ASC LIMIT 5;"
```

Deberías ver registros con formato:
```text
 id | username  |          email          
----+-----------+-------------------------
  1 | usuario1  | usuario1@ejemplo.test
  2 | usuario2  | usuario2@ejemplo.test
...
```

---

## 5. Próximos pasos para el Backend (`sige ube api`)

1. **Configuración en el backend:**
   - Asegurar que el archivo `.env` o `settings.py` de Django apunte a la base de datos `uniebec_dev`.
2. **Regla de oro del proyecto:**
   - **La base manda:** La estructura de la base de datos cambió desde versiones anteriores de la API. Se deben ajustar los modelos, consultas y serializadores de Django a la estructura actual de PostgreSQL. **No modifiques la estructura de la base de datos para forzarla a encajar con la API.**
3. **Periodo Lectivo (`X-Period-ID`):**
   - Todos los endpoints de estudiante deben filtrar por la cabecera `X-Period-ID` (en especial corregir `student/grades/` y `student/attendance/`, que antes lo ignoraban).
4. **Habilitar ruta de cierre de sesión:**
   - Crear la ruta `/api/v1.0.0/auth/sign-out/` para invalidar el refresh token al cerrar sesión.
