# Monitor de Vacantes UADE - Instructivo

Este script chequea automáticamente si se abrió una vacante en una clase
específica y te avisa por Telegram apenas pase de 0.

## 1. Requisitos previos

- Tener **Python** instalado (3.8 o superior).
- Tener **Google Chrome** instalado.

## 2. Instalación

1. Descargá los 3 archivos: `monitor_vacantes.py`, `requirements.txt`, `.gitignore`
2. Ponelos todos en la misma carpeta.
3. Abrí PowerShell en esa carpeta y corré:

```powershell
python -m pip install -r requirements.txt
```

## 3. Conseguir tu bot de Telegram (para recibir el aviso)

1. En Telegram, buscá **@BotFather** → escribile `/newbot` → seguí los pasos → te da un **TOKEN**.
2. Buscá el bot que acabas de crear, abrilo y apretá **"Iniciar"**.
3. Mandale cualquier mensaje (ej: "hola").
4. Abrí en el navegador (reemplazando `<TU_TOKEN>`):
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
5. Buscá `"chat":{"id": 123456789...}` — ese número es tu **Chat ID**.

Guardá el TOKEN y el Chat ID, te los va a pedir el script.

## 4. Correr el script

```powershell
python monitor_vacantes.py
```

Te va a preguntar, en orden:
- Tu usuario y contraseña de `inscripcionespia.uade.edu.ar` (el popup que aparece al buscar clases)
- El **nombre exacto** de la materia (tal cual aparece en "Seleccione sus Materias")
- El **número de Clase** que querés monitorear (columna "Clase" en los resultados)
- El turno (MAÑANA / TARDE / NOCHE / INTENSIVO / ONLINE)
- El TOKEN y Chat ID de Telegram (paso 3)

Al final te pregunta si querés **guardar esa configuración** para no tener que
volver a tipearla la próxima vez. Decile que sí.

La primera vez se va a abrir una ventana de Chrome pidiéndote el login de
Microsoft — logueate normal y volvé a la consola a apretar ENTER.

## 5. Dejarlo corriendo

- Dejá la ventana de PowerShell abierta.
- Andá a **Configuración → Sistema → Energía y batería** y poné
  "Suspender" en **Nunca** (mientras esté enchufado), para que la compu
  no se apague sola.
- El script ya evita que Windows bloquee la pantalla mientras corre.

Chequea cada 3 minutos. Cuando se abra un lugar, te llega el aviso a Telegram.

## ⚠️ Importante

- **No compartas** el archivo `config_usuario.json` que se genera — tiene tu
  contraseña guardada en texto plano.
- Si van a subir esto a GitHub, el `.gitignore` incluido ya excluye ese
  archivo y las carpetas de sesión de Chrome automáticamente.
