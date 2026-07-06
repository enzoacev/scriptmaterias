"""
Monitor de vacantes - Inscripciones UADE
==========================================
Chequea periodicamente si se abrio una vacante en la Clase 1941
(Proceso de Desarrollo de Software, turno noche) y avisa por Telegram
cuando pase de 0.

COMO FUNCIONA:
    1. Login manual de Microsoft (una sola vez, con perfil de Chrome
       persistente para no tener que repetirlo cada vez).
    2. Navega Inscribite -> INSCRIBITE -> pagina de busqueda de clases.
    3. Selecciona la materia y el turno NOCHE UNA SOLA VEZ.
    4. A partir de ahi, cada INTERVALO_SEGUNDOS simplemente vuelve a
       apretar "Buscar" en la misma pagina (sin repetir todo el
       flujo de navegacion) y lee el numero de vacantes actualizado.

REQUISITOS:
    pip install selenium webdriver-manager pip-system-certs

CONFIGURACION:
    Completar las variables de entorno antes de correr:
       $env:UADE_USUARIO="tu_usuario"
       $env:UADE_PASSWORD="tu_password_del_popup"
       $env:TELEGRAM_BOT_TOKEN="tu_token"
       $env:TELEGRAM_CHAT_ID="tu_chat_id"

USO:
    python monitor_vacantes.py
"""

"""
Monitor de vacantes - Inscripciones UADE
==========================================
Chequea periodicamente si se abrio una vacante en una clase especifica
y avisa por Telegram cuando pase de 0.

COMO FUNCIONA:
    1. Al arrancar, pregunta interactivamente los datos necesarios
       (usuario, contraseña, materia, clase, turno, Telegram) y los
       guarda en un archivo local para no tener que repetirlos la
       proxima vez que lo corras.
    2. Login manual de Microsoft (una sola vez por sesion de Chrome,
       con perfil persistente para no repetirlo cada vez que corres
       el script).
    3. Navega Inscribite -> INSCRIBITE -> pagina de busqueda de clases.
    4. Selecciona la materia y el turno indicados, UNA SOLA VEZ.
    5. A partir de ahi, cada tantos segundos simplemente vuelve a
       apretar "Buscar" en la misma pagina (sin repetir todo el
       flujo de navegacion) y lee el numero de vacantes actualizado.

REQUISITOS:
    pip install selenium webdriver-manager pip-system-certs

USO:
    python monitor_vacantes.py

    La primera vez te va a preguntar todos los datos. Las siguientes
    veces, te pregunta si queres reusar la configuracion guardada.
"""

import os
import time
import sys
import json
import getpass
import base64
import ssl
import ctypes
import platform
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import urllib.request
import urllib.parse
import urllib.error

# ----------------- CONFIG -----------------
# Estos valores se completan interactivamente al arrancar (ver
# cargar_configuracion() mas abajo). Quedan como variables globales para
# no tener que pasarlos como parametro por todas las funciones.

UADE_USUARIO = None
UADE_PASSWORD = None
NOMBRE_MATERIA = None
CLASE_OBJETIVO = None
TURNO = None
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None
INTERVALO_SEGUNDOS = 180

INSCRIPCIONES_URL = "https://inscripciones.uade.edu.ar/"
CONFIG_FILE = str(Path(__file__).parent / "config_usuario.json")

# -------------------------------------------


def preguntar(mensaje, secreto=False, default=None, obligatorio=True):
    """Pide un dato por consola. Si secreto=True, no lo muestra en pantalla."""
    sugerencia = f" [{default}]" if default else ""
    while True:
        if secreto:
            valor = getpass.getpass(f"{mensaje}{sugerencia}: ")
        else:
            valor = input(f"{mensaje}{sugerencia}: ").strip()
        if not valor and default is not None:
            return default
        if valor or not obligatorio:
            return valor
        print("  (Este dato es obligatorio, intenta de nuevo)")


def cargar_configuracion():
    """
    Pregunta el usuario UADE primero, y busca si ya existe una
    configuracion guardada para ESE usuario especifico (el archivo puede
    contener configuraciones de varios compañeros distintos, cada uno
    identificado por su propio usuario).
    """
    global UADE_USUARIO, UADE_PASSWORD, NOMBRE_MATERIA, CLASE_OBJETIVO
    global TURNO, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, INTERVALO_SEGUNDOS

    todas_las_configs = {}
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                todas_las_configs = json.load(f)
        except Exception as e:
            print(f"[WARN] No se pudo leer el archivo de configuraciones: {e}")

    print("\n" + "=" * 70)
    print("CONFIGURACION DEL MONITOR DE VACANTES UADE")
    print("=" * 70 + "\n")

    usuario_ingresado = preguntar("Tu usuario UADE (para identificar tu configuracion)")

    config_guardada = todas_las_configs.get(usuario_ingresado)
    if config_guardada:
        respuesta = input(
            f"Se encontro una configuracion guardada para '{usuario_ingresado}'. "
            "¿Usarla? (s/n): "
        ).strip().lower()
        if respuesta == "s":
            UADE_USUARIO = usuario_ingresado
            UADE_PASSWORD = config_guardada.get("uade_password", "")
            NOMBRE_MATERIA = config_guardada.get("nombre_materia", "")
            CLASE_OBJETIVO = config_guardada.get("clase_objetivo", "")
            TURNO = config_guardada.get("turno", "NOCHE")
            TELEGRAM_BOT_TOKEN = config_guardada.get("telegram_bot_token", "")
            TELEGRAM_CHAT_ID = config_guardada.get("telegram_chat_id", "")
            INTERVALO_SEGUNDOS = config_guardada.get("intervalo_segundos", 180)
            print("[INFO] Configuracion cargada.\n")
            return

    print(
        "\nVas a necesitar:\n"
        "  - Tu contraseña del popup de inscripcionespia.uade.edu.ar\n"
        "    (el que te pide al entrar a buscar clases, distinto del login\n"
        "    de Microsoft).\n"
        "  - El nombre EXACTO de la materia, tal como aparece en el listado\n"
        "    de 'Seleccione sus Materias' (mayusculas, sin errores de tipeo).\n"
        "  - El numero de Clase que queres monitorear (columna 'Clase' en\n"
        "    los resultados de busqueda).\n"
        "  - Opcional: datos de un bot de Telegram para recibir el aviso.\n"
    )

    UADE_USUARIO = usuario_ingresado
    UADE_PASSWORD = preguntar("Contraseña UADE (para el popup de login)", secreto=True)
    NOMBRE_MATERIA = preguntar("Nombre EXACTO de la materia").upper()
    CLASE_OBJETIVO = preguntar("Numero de Clase a monitorear (ej: 1941)")
    TURNO = preguntar(
        "Turno (MAÑANA / TARDE / NOCHE / INTENSIVO / ONLINE)", default="NOCHE"
    ).upper()

    print("\n--- Telegram (opcional, para recibir el aviso automatico) ---")
    print("Si no tenes un bot armado todavia, dejá estos dos vacios (Enter)")
    print("y el script va a imprimir el aviso en la consola en vez de mandarlo.\n")
    TELEGRAM_BOT_TOKEN = preguntar("Token del bot de Telegram", obligatorio=False, default="")
    TELEGRAM_CHAT_ID = preguntar("Chat ID de Telegram", obligatorio=False, default="")

    intervalo_str = preguntar("Cada cuantos segundos chequear", default="180")
    try:
        INTERVALO_SEGUNDOS = int(intervalo_str)
    except ValueError:
        INTERVALO_SEGUNDOS = 180

    respuesta = input("\n¿Guardar esta configuracion para la proxima vez? (s/n): ").strip().lower()
    if respuesta == "s":
        try:
            todas_las_configs[UADE_USUARIO] = {
                "uade_password": UADE_PASSWORD,
                "nombre_materia": NOMBRE_MATERIA,
                "clase_objetivo": CLASE_OBJETIVO,
                "turno": TURNO,
                "telegram_bot_token": TELEGRAM_BOT_TOKEN,
                "telegram_chat_id": TELEGRAM_CHAT_ID,
                "intervalo_segundos": INTERVALO_SEGUNDOS,
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(todas_las_configs, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Configuracion guardada en: {CONFIG_FILE}")
            print("[AVISO] La contraseña queda guardada en TEXTO PLANO en ese archivo.")
            print("        No lo compartas ni lo subas a ningun repositorio publico.")
        except Exception as e:
            print(f"[WARN] No se pudo guardar la configuracion: {e}")

    print()


def evitar_suspension_windows():
    """
    Le pide a Windows que no suspenda el equipo NI apague/bloquee la
    pantalla por inactividad mientras el script este corriendo.
    """
    if platform.system() != "Windows":
        return
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        print("[INFO] Se le pidio a Windows que no suspenda ni bloquee la pantalla mientras corre el script.")
    except Exception as e:
        print(f"[WARN] No se pudo evitar la suspension automaticamente: {e}")


def restaurar_suspension_windows():
    """Le devuelve a Windows el control normal de suspension al terminar."""
    if platform.system() != "Windows":
        return
    ES_CONTINUOUS = 0x80000000
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


def enviar_telegram(mensaje: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Falta configurar TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. Mensaje no enviado.")
        print("Mensaje:", mensaje)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
        print("[INFO] Aviso de Telegram enviado.")
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            print("[WARN] Error de certificado SSL, reintentando sin verificacion estricta...")
            try:
                contexto_inseguro = ssl.create_default_context()
                contexto_inseguro.check_hostname = False
                contexto_inseguro.verify_mode = ssl.CERT_NONE
                urllib.request.urlopen(url, data=data, timeout=10, context=contexto_inseguro)
                print("[INFO] Aviso de Telegram enviado (con fallback SSL).")
            except Exception as e2:
                print(f"[ERROR] No se pudo enviar Telegram ni con el fallback: {e2}")
        else:
            print(f"[ERROR] No se pudo enviar Telegram: {e}")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar Telegram: {e}")


def click_seguro(driver, elemento):
    """Click normal; si algo lo tapa visualmente, hace click via JavaScript."""
    try:
        elemento.click()
    except Exception:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", elemento)


def find_first(driver, wait, locators, description="elemento", clickable=True):
    """Prueba una lista de (By, selector) en orden y devuelve el primero que encuentre."""
    ultimo_error = None
    for by, selector in locators:
        try:
            condicion = EC.element_to_be_clickable((by, selector)) if clickable \
                else EC.presence_of_element_located((by, selector))
            return WebDriverWait(driver, 8).until(condicion)
        except Exception as e:
            ultimo_error = e
            continue
    raise TimeoutException(f"No se encontro {description}. Ultimo error: {ultimo_error}")


def esta_logueado(driver) -> bool:
    try:
        driver.find_element(By.XPATH, "//*[contains(text(), 'Salir')]")
        return True
    except NoSuchElementException:
        return False


def asegurar_login(driver):
    """Va a inscripciones.uade.edu.ar. Si no esta logueado, pausa para login manual."""
    driver.get(INSCRIPCIONES_URL)
    time.sleep(2)

    if esta_logueado(driver):
        print("[INFO] Sesion de Microsoft activa, continuando...")
        return

    print("\n" + "=" * 70)
    print("ACCION REQUERIDA: Completa el login de Microsoft en la ventana de Chrome.")
    print("Cuando veas la pagina de Inscripciones con tu nombre arriba a la derecha,")
    print("volve aca y apreta ENTER.")
    print("=" * 70 + "\n")
    input("Presiona ENTER cuando hayas terminado de loguearte... ")


def inyectar_basic_auth(driver):
    """Le pasa usuario/contraseña al navegador via CDP para evitar el popup nativo."""
    credenciales_b64 = base64.b64encode(f"{UADE_USUARIO}:{UADE_PASSWORD}".encode()).decode()
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
        "headers": {"Authorization": f"Basic {credenciales_b64}"}
    })


def navegar_a_busqueda(driver, wait):
    """Inscribite -> modal Continuar -> boton INSCRIBITE -> pagina de busqueda de clases."""
    print("[INFO] Navegando a la pagina de busqueda de clases...")

    tab_inscribite = find_first(
        driver, wait,
        [(By.XPATH, "//a[contains(text(), 'Inscribite')] | //button[contains(text(), 'Inscribite')]")],
        "pestaña Inscribite"
    )
    click_seguro(driver, tab_inscribite)
    time.sleep(2)

    boton_inscribite = find_first(
        driver, wait,
        [(By.XPATH,
          "//*[contains(text(), 'Asignaturas 2do Cuatrimestre')]"
          "/following::*[contains(text(), 'INSCRIBITE') or contains(text(), 'Inscribite')][1]")],
        "boton INSCRIBITE de Asignaturas 2do Cuatrimestre"
    )

    ventanas_antes = driver.window_handles
    inyectar_basic_auth(driver)
    click_seguro(driver, boton_inscribite)
    time.sleep(2)

    # Modal de advertencia con boton "Continuar" (libreria Bootbox)
    try:
        boton_continuar = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-bb-handler='ok']"))
        )
        click_seguro(driver, boton_continuar)
        time.sleep(2)
    except TimeoutException:
        pass  # No aparecio el modal esta vez

    ventanas_despues = driver.window_handles
    if len(ventanas_despues) > len(ventanas_antes):
        nueva_ventana = [v for v in ventanas_despues if v not in ventanas_antes][0]
        driver.switch_to.window(nueva_ventana)
        inyectar_basic_auth(driver)
        driver.refresh()

    time.sleep(2)
    print("[INFO] Llegamos a la pagina de busqueda.")


def seleccionar_materia_y_turno(driver, wait):
    """
    Se ejecuta UNA SOLA VEZ al arrancar: tilda la materia y selecciona el
    turno. Despues de esto, para actualizar resultados solo hace falta
    volver a apretar Buscar (ver click_buscar).
    """
    print(f"[INFO] Seleccionando materia '{NOMBRE_MATERIA}'...")

    materias_btn = find_first(
        driver, wait,
        [(By.ID, "ContentPlaceHolder1_btnSeleccionarMaterias")],
        "boton de Materias"
    )
    click_seguro(driver, materias_btn)
    time.sleep(1.5)

    checkbox = find_first(
        driver, wait,
        [(By.XPATH,
          f"//td[@class='colMateria' and normalize-space(text())='{NOMBRE_MATERIA}']"
          "/ancestor::tr[1]//input[@type='checkbox']"),
         (By.XPATH,
          f"//td[contains(@class, 'colMateria')][contains(normalize-space(.), '{NOMBRE_MATERIA}')]"
          "/ancestor::tr[1]//input[@type='checkbox']")],
        "checkbox de la materia",
        clickable=False
    )

    # Verificamos que la fila realmente corresponda a la materia esperada
    fila_del_checkbox = checkbox.find_element(By.XPATH, "./ancestor::tr[1]")
    if NOMBRE_MATERIA not in fila_del_checkbox.text.upper():
        raise Exception(f"El checkbox encontrado no pertenece a la materia esperada: {fila_del_checkbox.text}")

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila_del_checkbox)
    time.sleep(0.3)

    # Destildamos cualquier otra materia que haya quedado marcada de antes
    todos_los_checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
    for otro in todos_los_checkboxes:
        if otro != checkbox and otro.is_selected():
            click_seguro(driver, otro)
            time.sleep(0.3)

    if not checkbox.is_selected():
        click_seguro(driver, checkbox)
        time.sleep(0.5)

    if not checkbox.is_selected():
        raise Exception("El checkbox de la materia no quedo tildado.")

    print("[INFO] Materia seleccionada correctamente.")

    cerrar_btn = find_first(
        driver, wait,
        [(By.XPATH, "//span[@class='ui-button-text' and contains(text(), 'Cerrar')]"),
         (By.XPATH, "//span[contains(text(), 'Cerrar')]")],
        "boton Cerrar del popup"
    )
    click_seguro(driver, cerrar_btn)
    time.sleep(1)

    print(f"[INFO] Seleccionando turno {TURNO}...")
    turno_select_el = find_first(
        driver, wait,
        [(By.ID, "ContentPlaceHolder1_cboTurno")],
        "dropdown de Turno",
        clickable=False
    )
    Select(turno_select_el).select_by_visible_text(TURNO)
    time.sleep(0.5)


def click_buscar(driver, wait):
    """Aprieta el boton Buscar y espera a que aparezca la tabla de resultados."""
    buscar_btn = find_first(
        driver, wait,
        [(By.ID, "ContentPlaceHolder1_btnBuscar")],
        "boton Buscar"
    )
    click_seguro(driver, buscar_btn)
    time.sleep(3)
    wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "table")))


def leer_vacantes(driver) -> dict:
    """
    Busca la fila de datos real de CLASE_OBJETIVO (filtrando filas
    "contenedoras" del layout que tambien puedan matchear el texto) y
    devuelve {'vacantes': int, 'fila_completa': [...]} o None.
    """
    filas = driver.find_elements(
        By.XPATH,
        f"//tr[.//td[normalize-space(text())='{CLASE_OBJETIVO}']]"
    )

    def es_fila_de_datos(row):
        if not row.is_displayed():
            return False
        celdas_directas = row.find_elements(By.XPATH, "./td")
        return len(celdas_directas) >= 8

    filas_validas = [f for f in filas if es_fila_de_datos(f)]

    if not filas_validas:
        print(f"[WARN] No se encontro la Clase {CLASE_OBJETIVO} en los resultados")
        return None

    fila = filas_validas[0]
    columnas = fila.find_elements(By.TAG_NAME, "td")
    fila_texto = [col.text.strip() for col in columnas if col.text.strip()]

    vacantes = None
    if len(fila_texto) >= 2 and fila_texto[-2].isdigit():
        vacantes = int(fila_texto[-2])

    if vacantes is None:
        print(f"[WARN] No se pudo interpretar el numero de vacantes: {fila_texto}")

    return {"vacantes": vacantes, "fila_completa": fila_texto}


def main():
    from webdriver_manager.chrome import ChromeDriverManager

    cargar_configuracion()
    evitar_suspension_windows()

    # Perfil de Chrome especifico por usuario (para que, si varios
    # compañeros usan el mismo script en la misma compu, no se pisen
    # las sesiones de Microsoft entre ellos).
    usuario_sanitizado = "".join(c for c in UADE_USUARIO if c.isalnum())
    perfil_chrome_dir = str(Path(__file__).parent / f"chrome_profile_{usuario_sanitizado}")

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={perfil_chrome_dir}")
    # options.add_argument("--headless=new")  # Descomentar cuando quieras que corra sin ventana visible

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 10)

    try:
        # --- Configuracion inicial (una sola vez) ---
        asegurar_login(driver)
        navegar_a_busqueda(driver, wait)
        seleccionar_materia_y_turno(driver, wait)

        avisado = False
        print(f"\n[{datetime.now()}] Monitoreo iniciado para Clase {CLASE_OBJETIVO}. "
              f"Chequeando cada {INTERVALO_SEGUNDOS}s.\n")

        while True:
            try:
                click_buscar(driver, wait)
                resultado = leer_vacantes(driver)

                if resultado and resultado["vacantes"] is not None:
                    vacantes = resultado["vacantes"]
                    print(f"[{datetime.now()}] Vacantes actuales: {vacantes}")

                    if vacantes > 0 and not avisado:
                        msg = f"¡Se abrio una vacante en Clase {CLASE_OBJETIVO}! Vacantes disponibles: {vacantes}"
                        print(f"[ALERTA] {msg}")
                        enviar_telegram(msg)
                        avisado = True
                    elif vacantes == 0:
                        avisado = False
                else:
                    print(f"[{datetime.now()}] No se pudo leer el resultado esta vez.")

            except TimeoutException as e:
                print(f"[WARN] Timeout durante el chequeo: {e}")
                print("[INFO] Reintentando toda la navegacion desde cero en el proximo ciclo...")
                try:
                    navegar_a_busqueda(driver, wait)
                    seleccionar_materia_y_turno(driver, wait)
                except Exception as e2:
                    print(f"[ERROR] No se pudo recuperar la navegacion: {e2}")
            except Exception as e:
                print(f"[ERROR] {e}")

            time.sleep(INTERVALO_SEGUNDOS)

    finally:
        restaurar_suspension_windows()
        driver.quit()


if __name__ == "__main__":
    main()