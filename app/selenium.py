import os
import time
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from .processing import obtener_archivos

def acceder_backend(path_excel, DESCARGA_SEMANAL_ROUTE, test_mode, proyecto):
    if proyecto == "dreamfit":
        back_url = "https://backend.encuesta.com/scripts/trackings/dreamfit"
    elif proyecto == "profitness":
        back_url = "https://backend.encuesta.com/scripts/trackings/profitness"
    elif proyecto == "mqa":
        back_url = "https://backend.encuesta.com/scripts/trackings/mqa"
    elif proyecto == "beup":
        back_url = "https://backend.encuesta.com/scripts/trackings/beup"
    options = Options()
    options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(DESCARGA_SEMANAL_ROUTE),
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(back_url)
        driver.find_element(By.NAME, "username").send_keys("angel.martinez@webtools.es")
        driver.find_element(By.NAME, "password").send_keys("Test2020")
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        wait = WebDriverWait(driver, 15)
        input_file = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))
        input_file.send_keys(os.path.abspath(path_excel))

        if test_mode:
            driver.find_element(By.XPATH, '//*[@id="test"]').click()
        boton_enviar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']")))
        boton_enviar.click()
        time.sleep(1)

        timeout = 30
        start_time = time.time()
        archivo_descargado = None

        while time.time() - start_time < timeout:
            archivos = os.listdir(DESCARGA_SEMANAL_ROUTE)
            archivos = [f for f in archivos if not f.endswith(".crdownload")]
            if archivos:
                archivo_descargado = archivos[0]
                break
            time.sleep(1)

        return archivo_descargado
    finally:
        driver.quit()

def dividir_dataframe(df, filas_por_parte=1500):
    partes = []
    total = len(df)
    for i in range(0, total, filas_por_parte):
        parte = df.iloc[i:i+filas_por_parte]
        partes.append(parte)
    return partes

def ready_for_survey(DESCARGA_SEMANAL_ROUTE, path, n_semana, carpeta_semanal, test_mode):
    df = pd.read_excel(path)

    # Insertar nueva columna entre la tercera y cuarta posición
    df.insert(3, "Semana - Invite Custom 4", n_semana)

    # Definir columnas finales en orden correcto
    columnas_finales = [
        "Centro - Invite Custom 1",
        "Año - Invite Custom 2",
        "Mes - Invite Custom 3",
        "Semana - Invite Custom 4",
        "Sexo - Invite Custom 5",
        "Tramo Edad - Invite Custom 6",
        "Codigo Cliente - Invite Custom 7",
        "Ultimo Acceso - custom invite 8",
        "Dia de ultimo Acceso - Invite Custom 10",
        "Email"
    ]

    # Renombrar columnas existentes si hay variantes o errores
    df.columns = columnas_finales[:len(df.columns)]  # Asigna hasta el número de columnas reales

     # 🔄 Reemplazar LOGRONO por LOGROÑO en la columna de Centro
    df["Centro - Invite Custom 1"] = df["Centro - Invite Custom 1"].replace("LOGRONO", "LOGROÑO")
    partes = dividir_dataframe(df, filas_por_parte=1500)
    letra = ["A", "B", "C", "D"]
    archivos_generados = []

    for idx, parte in enumerate(partes, start=1):
        nombre_archivo = f"DREAMFIT_{n_semana}_{letra[idx-1]}.csv"
        ruta_descarga = os.path.join(DESCARGA_SEMANAL_ROUTE, nombre_archivo)

        # Reordenar columnas justo antes de guardar (por seguridad)
        parte = parte[columnas_finales]

        # Guardar archivo local
        parte.to_csv(ruta_descarga, index=False)
        archivos_generados.append(nombre_archivo)
        print(f"Guardado local: {nombre_archivo}")

        # Subir archivo al Drive
        if not test_mode:
            file_id = upload_file_to_drive(service, ruta_descarga, carpeta_semanal)
            print(f"📤 Subido a Drive: {nombre_archivo} (ID: {file_id})")

    return archivos_generados

def acceder_survey_dreamfit(ruta_archivos_partidos, n_semana, close_day, recordatorio, test_mode):
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    letra = ["A", "B", "C", "D", "E"]
    try:
        archivos = obtener_archivos(ruta_archivos_partidos, "DREAM")

        driver.get("https://app.alchemer.com/login/v1?email=emma.palacios%40webtools.es&legacy=1")

        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="password"]'))).send_keys("Alch3m3rw3bt00ls2025")
        driver.find_element(By.XPATH, '//*[@id="login-form"]/form/div[1]/div[3]/button').click()

        # Si hay sesión activa logearse
        try:
            while driver.title != "Alchemer - Dashboard":
                driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div/p/a").click()
        except:
            pass

        for idx, archivo in enumerate(archivos):
            driver.get("https://app.alchemer.com/distribute/share/id/2603226")

            # copiar campaña
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="grid-links"]/div[1]/div[5]/div/table/tbody/tr[1]/td[6]/div/a[1]'))).click()
            time.sleep(8)

            # Advanced settings
            wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div/div/article/div/div[1]/a/small'))).click()

            # Nombre campaña
            input_nombre = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="sName"]')))
            input_nombre.clear()
            input_nombre.send_keys(f"[S.{n_semana}]2025 - {letra[idx]}")

            # Fecha cierre
            input_fecha = driver.find_element(By.XPATH, '//*[@id="dScheduledClose"]')
            input_fecha.clear()
            input_fecha.send_keys(close_day)

            # Guardar campaña
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="save-campaign-settings"]'))).click()
            time.sleep(4)

            # Ir a contactos
            wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div/ol/li[2]/a'))).click()

            # Anadir contactos
            wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div[6]/div/a'))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="contacts-add"]/div/div/div[1]/div[1]/div[2]/a'))).click()



            # Subir archivo
            input_file = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="listcontactimport"]')))
            input_file.send_keys(os.path.abspath(archivo))
            time.sleep(2)

            # Continuar
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-contact-upload" and contains(text(), "Continue")]'))).click()
            time.sleep(2)
            # Seleccionar columna "Email"
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[11]/div[3]/select')))
            Select(dropdown).select_by_visible_text("Email")

            for i in range(1,9):
                j = i + 1
                dropdown = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[@id="importcontactfromcsv"]/div[1]/div[{j}]/div[3]/select')))
                Select(dropdown).select_by_visible_text(f"Invite Custom Field {i}")

            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[@id="importcontactfromcsv"]/div[1]/div[10]/div[3]/select')))
            Select(dropdown).select_by_visible_text(f"Invite Custom Field 10")

            time.sleep(1)

            # Confirmar importación
            driver.find_element(By.XPATH, '//*[@id="importcontactfromcsv"]/div[3]/div/button[1]').click()
            driver.find_element(By.XPATH, '//*[@id="send-email-when-done"]').click()
            driver.find_element(By.XPATH, '//*[@id="importcontactfromcsv"]/div[3]/div/button[2]').click()

            # Ir a Send Campaign
            driver.find_element(By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[1]/ol/li[3]/a').click()
            time.sleep(4)

            # Editar envío
            wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div/div/form/div[2]/table/tbody/tr[2]/td[3]/a'))).click()

            # Fecha/hora de envío
            input_fecha = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="invite-date"]')))
            input_fecha.send_keys(recordatorio)
            input_hora = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="calendar-send-hour"]')))
            input_hora.send_keys("3")

            driver.find_element(By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/button[3]').click()

            time.sleep(2)
            driver.refresh()
            time.sleep(4)

            # Confirmar envío
            wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div/div/form/div[2]/table/tbody/tr[1]/td[4]/a'))).click()
            time.sleep(2)

            if test_mode :
                #Cancelar
                wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/button'))).click()
                time.sleep(5)
            else:
                #Confirmar
                wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/a'))).click()


    except Exception as e:
            print("❌ Se produjo un error durante la automatización:")
            traceback.print_exc()  # Muestra el traceback completo
            # También podrías guardar el error en un log:
            with open("errores_automatizacion.log", "a", encoding="utf-8") as f:
                f.write("Error en acceder_survey:\n")
                f.write(traceback.format_exc())
                f.write("\n" + "-"*60 + "\n")

    finally:
        driver.quit()
        print("Driver cerrado.")

def acceder_survey_profitness(ruta_archivos_partidos, recordatorio, test_mode):
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    try:
        archivo = obtener_archivos(ruta_archivos_partidos, "sample")

        driver.get("https://app.alchemer.com/login/v1?email=emma.palacios%40webtools.es&legacy=1")


        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="password"]'))).send_keys("Alch3m3rw3bt00ls2025")
        driver.find_element(By.XPATH, '//*[@id="login-form"]/form/div[1]/div[3]/button').click()

        # Si hay sesión activa logearse
        try:
            while driver.title != "Alchemer - Dashboard":
                driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div/p/a").click()
        except:
            pass

        driver.get("https://app.alchemer.com/distribute/share/id/5666321")

        # Elegir la campaña
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="grid-links"]/div[1]/div[5]/div/table/tbody/tr[1]/td[1]/a'))).click()
        time.sleep(4)

        # Ir a contactos
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div/div/article/div/div[1]/ol/li[2]/a'))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="InviteContacts"]/form/div[1]/div[1]/div/div/div/button'))).click()

        # Anadir contactos
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="contacts-add"]/div/div/div[1]/div[1]/div[2]/a'))).click()

        # Subir archivo
        input_file = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="listcontactimport"]')))
        input_file.send_keys(os.path.abspath(archivo[0]))
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="no-dedupe-csv"]'))).click()

        # Continuar
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-contact-upload" and contains(text(), "Continue")]'))).click()
        time.sleep(2)
        # ----------------------------------------------------------------

        # Seleccionar columna "Email"
        dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[3]/div[3]/select')))
        Select(dropdown).select_by_visible_text("Email")

        dropdown = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[@id="importcontactfromcsv"]/div[1]/div[2]/div[3]/select')))
        Select(dropdown).select_by_visible_text(f"Invite Custom Field 1")

        time.sleep(1)

        # Confirmar importación
        driver.find_element(By.XPATH, '//*[@id="importcontactfromcsv"]/div[3]/div/button[1]').click()
        driver.find_element(By.XPATH, '//*[@id="send-email-when-done"]').click()
        driver.find_element(By.XPATH, '//*[@id="importcontactfromcsv"]/div[3]/div/button[2]').click()

        # Ir a Send Campaign
        driver.find_element(By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[1]/ol/li[3]/a').click()
        time.sleep(2)

        # Editar envío
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div/div/form/div[2]/table/tbody/tr[2]/td[3]/a'))).click()

        # Fecha/hora de envío
        input_fecha = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="invite-date"]')))
        input_fecha.send_keys(recordatorio)
        input_hora = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="calendar-send-hour"]')))
        input_hora.send_keys("3")

        driver.find_element(By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/button[3]').click()
        time.sleep(8)
        driver.refresh()

        # Confirmar envío
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div/div/form/div[2]/table/tbody/tr[1]/td[4]/a'))).click()

        if test_mode :
            #Cancelar
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/button'))).click()
        else:
            #Confirmar
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/a'))).click()


    except Exception as e:
            print("❌ Se produjo un error durante la automatización:")
            traceback.print_exc()  # Muestra el traceback completo
            # También podrías guardar el error en un log:
            with open("errores_automatizacion.log", "a", encoding="utf-8") as f:
                f.write("Error en acceder_survey:\n")
                f.write(traceback.format_exc())
                f.write("\n" + "-"*60 + "\n")

    finally:
        driver.quit()
        print("Driver cerrado.")

def acceder_survey_mqa(ruta_archivos_partidos, n_semana, close_day, recordatorio, test_mode):
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    try:
        archivo = obtener_archivos(ruta_archivos_partidos, "sample")

        driver.get("https://app.alchemer.com/login/v1?email=emma.palacios%40webtools.es&legacy=1")

        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="password"]'))).send_keys("Alch3m3rw3bt00ls2025")
        driver.find_element(By.XPATH, '//*[@id="login-form"]/form/div[1]/div[3]/button').click()

        # Si hay sesión activa logearse
        try:
            while driver.title != "Alchemer - Dashboard":
                driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div/p/a").click()
        except:
            pass

        # Buscar Profitness y filtrar
        driver.get("https://app.alchemer.com/distribute/share/id/3385629")

        # Share
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="project-nav"]/ul/li[4]/a'))).click()

        # copiar campaña
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="grid-links"]/div[1]/div[5]/div/table/tbody/tr[1]/td[1]/a'))).click()
        time.sleep(1)

        # Ir a contactos
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div/div/article/div/div[1]/ol/li[2]/a'))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="InviteContacts"]/form/div[1]/div[1]/div/div/div/button'))).click()

        # Anadir contactos
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="contacts-add"]/div/div/div[1]/div[1]/div[2]/a'))).click()

        # Subir archivo
        input_file = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="listcontactimport"]')))
        input_file.send_keys(os.path.abspath(archivo[0]))
        time.sleep(1)

        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="no-dedupe-csv"]'))).click()

        # Continuar
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-contact-upload" and contains(text(), "Continue")]'))).click()
        time.sleep(1)
        # ----------------------------------------------------------------



        # Seleccionar columna "Email"
        dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[5]/div[3]/select')))
        Select(dropdown).select_by_visible_text("Email")

        for i in range(1,4):
            j = i + 1
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[@id="importcontactfromcsv"]/div[1]/div[{j}]/div[3]/select')))
            Select(dropdown).select_by_visible_text(f"Invite Custom Field {i}")

        time.sleep(1)

        for i in range(4,7):
            j = i + 2
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[@id="importcontactfromcsv"]/div[1]/div[{j}]/div[3]/select')))
            Select(dropdown).select_by_visible_text(f"Invite Custom Field {i}")


        # Confirmar importación
        driver.find_element(By.XPATH, '//*[@id="importcontactfromcsv"]/div[3]/div/button[1]').click()
        driver.find_element(By.XPATH, '//*[@id="send-email-when-done"]').click()
        driver.find_element(By.XPATH, '//*[@id="importcontactfromcsv"]/div[3]/div/button[2]').click()

        # Ir a Send Campaign
        driver.find_element(By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[1]/ol/li[3]/a').click()
        time.sleep(2)

        # Editar envío
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div/div/form/div[2]/table/tbody/tr[2]/td[3]/a'))).click()

        # Fecha/hora de envío
        input_fecha = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="invite-date"]')))
        input_fecha.send_keys(recordatorio)
        input_hora = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="calendar-send-hour"]')))
        input_hora.send_keys("3")

        driver.find_element(By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/button[3]').click()
        time.sleep(4)
        driver.refresh()

        # Confirmar envío
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/article/div[2]/div[2]/div[2]/div/div/form/div[2]/table/tbody/tr[1]/td[4]/a'))).click()
        if test_mode :
            #Cancelar
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/button'))).click()
        else:
            #Confirmar
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-invite-form"]/div/div[3]/a'))).click()

        #Volver
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div/div/div/a'))).click()
    except Exception as e:
            print("❌ Se produjo un error durante la automatización:")
            traceback.print_exc()  # Muestra el traceback completo
            # También podrías guardar el error en un log:
            with open("errores_automatizacion.log", "a", encoding="utf-8") as f:
                f.write("Error en acceder_survey:\n")
                f.write(traceback.format_exc())
                f.write("\n" + "-"*60 + "\n")
    finally:
        driver.quit()
        print("Driver cerrado.")

