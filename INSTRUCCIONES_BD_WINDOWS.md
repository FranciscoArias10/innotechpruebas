# Guía de Restauración de Base de Datos para Windows 11 (SIGE UNIEBEC)

> **Destinatario:** Esta guía está diseñada para los desarrolladores del equipo que trabajan en **Windows 11** para configurar la base de datos PostgreSQL local a partir del respaldo proporcionado, anonimizarla y conectar el backend (`sige-ube-api`).

---

## 1. Requisitos Previos en Windows 11

1. **Python 3.11:**
   - Descargar e instalar desde [python.org](https://www.python.org/downloads/release/python-3119/).
   - ⚠️ **Importante al instalar:** Marcar la casilla **"Add python.exe to PATH"**.
2. **PostgreSQL para Windows (versión 15 o 16):**
   - Descargar el instalador oficial de [EnterpriseDB / postgresql.org](https://www.postgresql.org/download/windows/).
   - Durante la instalación, se te pedirá una **contraseña para el superusuario `postgres`**. **Anota esta contraseña**, la necesitarás en los pasos siguientes.
   - Dejar el puerto por defecto: `5432`.
3. **El archivo de respaldo:**
   - Tener a mano el archivo `respaldo-pasantes-2026-09-30.dump` (colócalo en una ruta accesible, por ejemplo en la raíz de este proyecto o en tu carpeta de Descargas/Proyectos).

---

## 2. Configurar la consola (PowerShell o CMD)

Por defecto en Windows, las herramientas de PostgreSQL (`psql`, `pg_restore`, `createdb`) se instalan en:
`C:\Program Files\PostgreSQL\16\bin` *(o `15\bin` según la versión instalada)*.

Abre **PowerShell** y verifica si reconoce los comandos:
```powershell
psql --version
```

Si PowerShell dice que el comando no se reconoce, agrega la ruta temporalmente a tu sesión actual de PowerShell con este comando:
```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
```
*(Opcional: puedes agregar `C:\Program Files\PostgreSQL\16\bin` a las Variables de Entorno del Sistema en Windows para que quede permanente).*

---

## 3. Paso a Paso para Restaurar y Anonimizar

### Paso 1: Verificar que el servicio de PostgreSQL esté activo
En Windows, PostgreSQL corre como un servicio del sistema. Puedes verificarlo en PowerShell:
```powershell
Get-Service postgresql*
```
Debe indicar `Status: Running`. Si no está iniciado:
```powershell
Start-Service postgresql*
```
*(O puedes presionar `Win + R`, escribir `services.msc`, buscar `postgresql-x64-...` y darle a "Iniciar").*

---

### Paso 2: Crear la base de datos `uniebec_dev`

#### Opción A (Por PowerShell o CMD):
```powershell
createdb -U postgres uniebec_dev
```
*(Te pedirá la contraseña que definiste al instalar PostgreSQL).*

#### Opción B (Usando la interfaz gráfica pgAdmin 4):
1. Abre **pgAdmin 4** desde el menú inicio.
2. Despliega los servidores a la izquierda e ingresa tu contraseña de `postgres`.
3. Clic derecho en **Databases** > **Create** > **Database...**
4. En **Database**, escribe `uniebec_dev` y haz clic en **Save**.

---

### Paso 3: Restaurar el archivo `.dump`

#### Opción A (Por consola PowerShell / CMD - Recomendado):
Ejecuta `pg_restore` indicando la ruta entre comillas donde guardaste el archivo `.dump`:

```powershell
pg_restore -U postgres --no-owner --no-acl -d uniebec_dev "respaldo-pasantes-2026-09-30.dump"
```
*(Ingresa tu contraseña de PostgreSQL cuando te la solicite).*

> [!NOTE]
> Es completamente normal que aparezcan advertencias (`WARNING`) sobre roles o extensiones durante la importación. Lo importante es que finalice sin errores fatales.

#### Opción B (Usando pgAdmin 4):
1. En pgAdmin, haz clic derecho sobre la base de datos `uniebec_dev` recién creada y selecciona **Restore...**
2. En **Format**, selecciona **Custom or tar**.
3. En **Filename**, busca el archivo `.dump` (asegúrate de cambiar el filtro de archivos en la ventana de exploración a *All Files (\*.\*)* para poder seleccionarlo).
4. Ve a la pestaña **Restore options**, y activa:
   - **Do not save: Owner** (`--no-owner`)
   - **Do not save: Privilege** (`--no-acl`)
5. Haz clic en el botón **Restore**.

---

### Paso 4: Limpieza y Anonimización de Usuarios (Obligatorio)

En el respaldo original, ninguna contraseña sirve para iniciar sesión. Debemos ejecutar una consulta SQL para estandarizar los usuarios y habilitar una contraseña universal de pruebas.

#### Opción A (Directo en pgAdmin 4 - Más sencillo en Windows):
1. Haz clic derecho sobre `uniebec_dev` y selecciona **Query Tool** (Herramienta de consulta).
2. Pega la siguiente consulta SQL:
```sql
UPDATE auth_user SET
  username   = 'usuario' || id,
  first_name = '',
  last_name  = '',
  email      = 'usuario' || id || '@ejemplo.test',
  password   = 'pbkdf2_sha256$600000$w7hIyIoONpDfiaGEdLwYt1$7MKVLruZ7T5j4QHL0VhjfyplajWzRtVjiAfMnzj/3G8=';
```
3. Presiona **F5** (o el botón de Play) para ejecutar. Verás el mensaje `UPDATE 72`.

#### Opción B (Por PowerShell):
> En PowerShell el signo `$` debe escaparse con un acento grave (`` `$ ``) para que no lo interprete como variable:
```powershell
psql -U postgres -d uniebec_dev -c "UPDATE auth_user SET username = 'usuario' || id, first_name = '', last_name = '', email = 'usuario' || id || '@ejemplo.test', password = 'pbkdf2_sha256`$600000`$w7hIyIoONpDfiaGEdLwYt1`$7MKVLruZ7T5j4QHL0VhjfyplajWzRtVjiAfMnzj/3G8=';"
```

---

### Paso 5: Credenciales de Prueba Disponibles

Tras la anonimización, cualquier usuario de la base puede autenticarse con:
- **Usuario:** `usuario` + el ID (ejemplos: `usuario1`, `usuario2`, `usuario73`, etc.).
- **Contraseña universal:** **`Pasantes2026*`**
- **Correo:** `usuario<id>@ejemplo.test`

Para verificarlo en consola:
```powershell
psql -U postgres -d uniebec_dev -c "SELECT id, username, email FROM auth_user ORDER BY id ASC LIMIT 5;"
```

---

## 4. Conectar el Backend Django en Windows 11

Una vez restaurada la base, dentro de la carpeta del proyecto `sige-ube-api`:

1. **Crear tu archivo `.env`:**
   Copia el archivo `.env.example` y nómbralo `.env`:
   ```powershell
   copy .env.example .env
   ```
   Abre `.env` en tu editor y pon tu contraseña de PostgreSQL:
   ```env
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=uniebec_dev
   DB_USER=postgres
   DB_PASSWORD=tu_contraseña_aqui
   DB_HOST=localhost
   DB_PORT=5432
   ```

2. **Crear y activar el entorno virtual:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   *(Si PowerShell muestra error de scripts deshabilitados, ejecuta: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activar).*

3. **Instalar dependencias y correr migraciones:**
   ```powershell
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py test
   ```
   *(Si las pruebas pasan con `OK`, el entorno está listo).*

4. **Levantar el servidor local:**
   ```powershell
   python manage.py runserver
   ```
   *O de forma aún más sencilla:* puedes hacer doble clic en el archivo **`iniciar.bat`** (o ejecutar `.\iniciar.bat` en PowerShell/CMD), el cual verifica PostgreSQL, activa el entorno y enciende el servidor automáticamente.

   El servidor quedará disponible en `http://127.0.0.1:8000/`.
