from flask import Flask, request, jsonify, render_template_string, send_from_directory
import pandas as pd
import os
import time
from datetime import datetime
import numpy as np
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# Ruta al archivo descargado
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

# Autenticación
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Inicializar cliente
service = build('drive', 'v3', credentials=credentials)

def obtener_sample_en_carpeta(ruta_carpeta):
    return [
        os.path.join(ruta_carpeta, f)
        for f in os.listdir(ruta_carpeta)
        if f.startswith('sample') and os.path.isfile(os.path.join(ruta_carpeta, f))
    ]

def obtener_archivos(ruta_carpeta, prefijo):
    return [
        os.path.join(ruta_carpeta, f)
        for f in os.listdir(ruta_carpeta)
        if f.startswith(prefijo) and os.path.isfile(os.path.join(ruta_carpeta, f))
    ]

def upload_file_to_drive(service, local_file_path, parent_folder_id):
    """
    Sube un archivo local a una carpeta de Google Drive.

    Args:
        service: cliente autenticado de Google Drive
        local_file_path (str): ruta del archivo local
        parent_folder_id (str): ID de la carpeta de destino en Drive

    Returns:
        str: ID del archivo subido
    """
    file_name = os.path.basename(local_file_path)
    media = MediaFileUpload(local_file_path, resumable=True)

    file_metadata = {
        'name': file_name,
        'parents': [parent_folder_id]
    }

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return uploaded_file['id']

def get_file_id_by_name_in_folder(service, folder_id, target_name):
    """
    Busca un archivo o carpeta con nombre `target_name` dentro de una carpeta dada por `folder_id`.

    Args:
        service: cliente de Google Drive API autenticado
        folder_id (str): ID de la carpeta donde buscar
        target_name (str): nombre exacto del archivo o subcarpeta a buscar

    Returns:
        str or None: ID del archivo encontrado, o None si no se encontró
    """
    query = (
        f"'{folder_id}' in parents and name = '{target_name}' "
        f"and trashed = false"
    )
    response = service.files().list(
        q=query,
        fields="files(id, name, mimeType)"
    ).execute()

    files = response.get('files', [])
    if files:
        return files[0]['id']  # Retorna el primero si hay coincidencias
    else:
        return None

def create_folder_in_drive(service, parent_folder_id, new_folder_name):
    """
    Crea una nueva carpeta dentro de otra carpeta en Google Drive.

    Args:
        service: cliente autenticado de Google Drive
        parent_folder_id (str): ID de la carpeta contenedora (padre)
        new_folder_name (str): nombre de la nueva carpeta a crear

    Returns:
        str: ID de la nueva carpeta creada
    """
    file_metadata = {
        'name': new_folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }

    folder = service.files().create(
        body=file_metadata,
        fields='id'
    ).execute()

    return folder['id']

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
DESCARGAS_FOLDER = "descargas"

# Crear carpetas base
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DESCARGAS_FOLDER, exist_ok=True)

# Subcarpetas por proyecto
PROYECTOS = ["dreamfit", "profitness", "mqa", "beup"]

for proyecto in PROYECTOS:
    os.makedirs(os.path.join(UPLOAD_FOLDER, proyecto), exist_ok=True)
    os.makedirs(os.path.join(DESCARGAS_FOLDER, proyecto), exist_ok=True)


# HTML frontend
HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tracking Automatizado</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 font-sans">
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-white shadow-xl rounded-xl p-5 w-full max-w-md">
      <h1 class="text-xl font-bold text-center text-gray-800 mb-6">Tracking Automatizado</h1>

      <!-- Selector de proyecto -->
      <label for="proyecto" class="block mb-2 text-gray-700 font-medium">Proyecto</label>
      <select id="proyecto" name="proyecto" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg">
        <option value="dreamfit">Dreamfit</option>
        <option value="profitness">ProFitness</option>
        <option value="mqa">MQA</option>
        <option value="beup">BeUp</option>
      </select>

      <label for="entero" class="block mb-2 text-gray-700 font-medium">Semana actual</label>
      <input type="number" id="entero" name="entero" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg" required>

      <label for="close_day" class="block mb-2 text-gray-700 font-medium">Fecha cierre (ej. aaaa-mm-dd hh:mm:ss)</label>
      <input type="text" id="close_day" name="close_day" placeholder="YYYY-MM-DD HH:MM:SS" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg" required>

      <label for="recordatorio" class="block mb-2 text-gray-700 font-medium">Fecha recordatorio (ej. mm-dd-aaaa)</label>
      <input type="text" id="recordatorio" name="recordatorio" placeholder="DD-MM-YYYY" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg" required>

      <div class="flex items-center mb-4">
        <input type="checkbox" id="test_mode" name="test_mode" class="mr-2 h-4 w-4 text-blue-600 border-gray-300 rounded">
        <label for="test_mode" class="text-gray-700 font-medium">Test:</label>
      </div>

      <!-- Drop area normal -->
      <div id="drop-area" class="w-full h-40 border-2 border-dashed border-gray-400 rounded-lg flex flex-col items-center justify-center cursor-pointer bg-gray-50 hover:bg-gray-100 transition mb-4">
        <p class="text-gray-500">Arrastra y suelta un archivo .xlsx o haz clic</p>
        <input type="file" id="fileElem" accept=".xlsx" class="hidden">
      </div>

      <!-- Drop areas específicos para BeUp -->
      <div id="beup-dropareas" class="hidden">
        <div class="mb-4">
          <p class="text-gray-700 font-medium mb-2">Barakaldo - BeUp</p>
          <div id="drop-area-1" class="drop-area">
            <p class="text-gray-500">Arrastra y suelta Archivo 1</p>
            <input type="file" id="fileElem1" accept=".xlsx" class="hidden">
          </div>
        </div>
        <div class="mb-4">
          <p class="text-gray-700 font-medium mb-2">Burgos - BeUp</p>
          <div id="drop-area-2" class="drop-area">
            <p class="text-gray-500">Arrastra y suelta Archivo 2</p>
            <input type="file" id="fileElem2" accept=".xlsx" class="hidden">
          </div>
        </div>
        <div class="mb-4">
          <p class="text-gray-700 font-medium mb-2">Santander - BeUp</p>
          <div id="drop-area-3" class="drop-area">
            <p class="text-gray-500">Arrastra y suelta Archivo 3</p>
            <input type="file" id="fileElem3" accept=".xlsx" class="hidden">
          </div>
        </div>
      </div>

      <button id="enviar" class="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition">Enviar</button>

      <div id="message" class="mt-4 text-sm text-gray-700 text-center"></div>
    </div>
  </div>

  <style>
    .drop-area {
      width: 100%;
      height: 150px;
      border: 2px dashed #ccc;
      border-radius: 0.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: #f9fafb;
      cursor: pointer;
    }
  </style>

  <script>
    function getWeekNumber(d) {
      d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
      const dayNum = d.getUTCDay() || 7;
      d.setUTCDate(d.getUTCDate() + 4 - dayNum);
      const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    }

    window.addEventListener('load', () => {
      const today = new Date();
      document.getElementById('entero').value = getWeekNumber(today);

      const closeDate = new Date(today);
      closeDate.setDate(closeDate.getDate() + 7);
      document.getElementById('close_day').value = closeDate.toISOString().split('T')[0] + ' 23:00:00';

      const reminderDate = new Date(today);
      reminderDate.setDate(reminderDate.getDate() + 2);
      const dd = String(reminderDate.getDate()).padStart(2, '0');
      const mm = String(reminderDate.getMonth() + 1).padStart(2, '0');
      const yyyy = reminderDate.getFullYear();
      document.getElementById('recordatorio').value = `${mm}-${dd}-${yyyy}`;
    });

    // Mostrar/ocultar drop areas según proyecto
    document.getElementById("proyecto").addEventListener("change", () => {
      const proyecto = document.getElementById("proyecto").value;
      const beupDropAreas = document.getElementById("beup-dropareas");
      const normalDropArea = document.getElementById("drop-area");
      if (proyecto === "beup") {
        beupDropAreas.classList.remove("hidden");
        normalDropArea.classList.add("hidden");
      } else {
        beupDropAreas.classList.add("hidden");
        normalDropArea.classList.remove("hidden");
      }
    });

    // Drag & Drop común
    const dropArea = document.getElementById("drop-area");
    const fileInput = document.getElementById("fileElem");
    const message = document.getElementById("message");
    const button = document.getElementById("enviar");

    dropArea.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFiles);

    ['dragenter', 'dragover'].forEach(eventName => {
      dropArea.addEventListener(eventName, e => {
        e.preventDefault();
        dropArea.classList.add("border-blue-500");
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropArea.addEventListener(eventName, e => {
        e.preventDefault();
        dropArea.classList.remove("border-blue-500");
      });
    });

    dropArea.addEventListener("drop", e => {
      const dt = e.dataTransfer;
      const files = dt.files;
      fileInput.files = files;
      handleFiles();
    });

    function handleFiles() {
      if (fileInput.files.length) {
        message.innerText = `Archivo: ${fileInput.files[0].name}`;
      }
    }

    // Drag & Drop para BeUp (3 areas)
    for (let i = 1; i <= 3; i++) {
      const area = document.getElementById(`drop-area-${i}`);
      const input = document.getElementById(`fileElem${i}`);

      area.addEventListener("click", () => input.click());
      input.addEventListener("change", () => {
        if (input.files.length) {
          area.querySelector("p").innerText = `Archivo: ${input.files[0].name}`;
        }
      });

      ['dragenter', 'dragover'].forEach(eventName => {
        area.addEventListener(eventName, e => {
          e.preventDefault();
          area.classList.add("border-blue-500");
        });
      });

      ['dragleave', 'drop'].forEach(eventName => {
        area.addEventListener(eventName, e => {
          e.preventDefault();
          area.classList.remove("border-blue-500");
        });
      });

      area.addEventListener("drop", e => {
        const dt = e.dataTransfer;
        const files = dt.files;
        input.files = files;
        if (input.files.length) {
          area.querySelector("p").innerText = `Archivo: ${input.files[0].name}`;
        }
      });
    }

    // Enviar
    button.addEventListener("click", () => {
      const proyecto = document.getElementById("proyecto").value;
      const numero = document.getElementById("entero").value;
      const closeDay = document.getElementById("close_day").value;
      const recordatorio = document.getElementById("recordatorio").value;
      const testMode = document.getElementById("test_mode").checked ? "1" : "0";

      const formData = new FormData();
      formData.append("entero", numero);
      formData.append("close_day", closeDay);
      formData.append("recordatorio", recordatorio);
      formData.append("test_mode", testMode);
      formData.append("proyecto", proyecto);

      if (proyecto === "beup") {
        for (let i = 1; i <= 3; i++) {
          const input = document.getElementById(`fileElem${i}`);
          if (!input.files[0]) {
            message.innerText = `Falta Archivo ${i}.`;
            return;
          }
          formData.append(`file${i}`, input.files[0]);
        }
      } else {
        const file = fileInput.files[0];
        if (!file || !numero || !closeDay || !recordatorio) {
          message.innerText = "Faltan uno o más campos.";
          return;
        }
        formData.append("file", file);
      }

      message.innerText = "Enviando...";

      fetch(`/upload`, {
        method: "POST",
        body: formData
      })
      .then(res => res.json())
      .then(data => {
        message.innerHTML = data.message || "Éxito";
        if (data.archivos_partidos) {
          data.archivos_partidos.forEach(nombre => {
            message.innerHTML += `<br><a class="text-blue-600 underline" href="/descargar/${nombre}" download>${nombre}</a>`;
          });
        }
      })
      .catch(err => {
        message.innerText = "Error en la petición.";
        console.error(err);
      });
    });
  </script>
</body>
</html>

'''

def ready_for_back_dreamfit(path, UPLOAD_SEMANAL_ROUTE):
    # Leer todas las hojas
    xls = pd.read_excel(path, sheet_name=None)
    output_path = os.path.join(UPLOAD_SEMANAL_ROUTE, "1_transformation.xlsx")

    # Crear un ExcelWriter para guardar varias hojas
    with pd.ExcelWriter(output_path, engine='openpyxl', datetime_format='DD/MM/YYYY') as writer:
        for sheet_name, df in xls.items():
            # Eliminar registros con Email nulo y hacer copia explícita
            if "Email" in df.columns:
                df = df[df["Email"].notna()].copy()

            # Insertar columna vacía al inicio
            df.insert(0, 'Null_Col', np.nan)

            # Convertir UltimoAcceso a datetime con formato
            if "UltimoAcceso" in df.columns:
                df["UltimoAcceso"] = pd.to_datetime(df["UltimoAcceso"], errors='coerce', dayfirst=True).dt.strftime("%d/%m/%Y")

            # Forzar nombres duplicados para 'IdPersona'
            df.columns = [col.replace('.1', '') if col.startswith('IdPersona') else col for col in df.columns]

            # Escribir hoja transformada
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return output_path

def ready_for_back_profitness(path, UPLOAD_SEMANAL_ROUTE):
    # Leer la única hoja directamente como DataFrame
    df = pd.read_excel(path, skiprows=1, header=0)

    # Eliminar registros con Email nulo
    if "E-Mail" in df.columns:
        df = df[df["E-Mail"].notna()].copy()
        df["E-Mail"] = df["E-Mail"].str.strip()

    # Definir ruta de salida
    output_path = os.path.join(UPLOAD_SEMANAL_ROUTE, "1_transformation.xlsx")

    # Guardar la única hoja transformada
    df.to_excel(output_path, index=False, engine='openpyxl')

    return output_path

def ready_for_back_mqa(path, UPLOAD_SEMANAL_ROUTE):
    # Leer la única hoja directamente como DataFrame
    df = pd.read_excel(path, skiprows=3, header=0)

    df['Puerta'] = df['Puerta'].ffill()
    # Eliminar registros con Email nulo
    if "Email" in df.columns:
        df = df[df["Email"].notna()].copy()
        df["Email"] = df["Email"].str.strip()
        df['Email'] = df['Email'].str.replace(' ', '', regex=False)

    # Definir ruta de salida
    output_path = os.path.join(UPLOAD_SEMANAL_ROUTE, "1_transformation.xlsx")

    # Guardar la única hoja transformada
    df.to_excel(output_path, index=False, engine='openpyxl')

    return output_path

def ready_for_back_beup(path, UPLOAD_SEMANAL_ROUTE):

    # Leer la única hoja directamente como DataFrame
    centro = path[-10:-5]
    print(centro)
    if centro == "kaldo":
        df = pd.read_excel(path, skiprows=3, header=0)
        df = df.drop(columns=['Entrada'])

        df.insert(0, 'Centro', 'BARAKALDO')
        df = df[df['Categoria'].notna()]

        mapeo = {
            '1. JOVEN': 'Individual',
            '2. ADULTO': 'Individual',
            '3. SENIOR': 'Individual',
            '4. FAMILIAR': 'Familiar',

        }

        # Aplicar el mapeo en una nueva columna
        df['Categoria'] = df['Categoria'].map(mapeo)
        # Eliminar registros con Email nulo
        if "Email" in df.columns:
            df = df[df["Email"].notna()].copy()
            df["Email"] = df["Email"].str.strip()
            df['Email'] = df['Email'].str.replace(' ', '', regex=False)

        # Definir ruta de salida
        output_path = os.path.join(UPLOAD_SEMANAL_ROUTE, "1_transformation_barakaldo.xlsx")


    elif centro == "urgos":
        df = pd.read_excel(path)
        df = df.drop(columns=['Fecha','OrigenPago', 'Puerta'])
        df = df.rename(columns={'TipoUltimoAbono': 'Origen'})
        df = df.rename(columns={'AltaUltAbono': 'FechaAntiguedad'})
        df.insert(1, 'Categoria', 'Individual')
        df.insert(0, 'Centro', 'BURGOS')# Filtrar eliminando ese registro
        df = df[df['Origen'] != "(nulo)"]
        df.loc[df['Origen'].str.contains('FAMILIAR', case=False, na=False), 'Categoria'] = "Familiar"
        df.columns = [col.replace('.1', '') if col.startswith('IdPersona') else col for col in df.columns]

        if "Email" in df.columns:
            df = df[df["Email"].notna()].copy()
            df["Email"] = df["Email"].str.strip()
            df['Email'] = df['Email'].str.replace(' ', '', regex=False)

        output_path = os.path.join(UPLOAD_SEMANAL_ROUTE, "1_transformation_burgos.xlsx")

    elif centro == "ander":
        df = pd.read_excel(path)
        df = df.drop(columns=['Fecha','OrigenPago', 'Puerta'])
        df = df.rename(columns={'TipoUltimoAbono': 'Origen'})
        df = df.rename(columns={'AltaUltAbono': 'FechaAntiguedad'})
        df = df.rename(columns={'CategoriaUltimoAbono': 'Categoria'})
        df.insert(0, 'Centro', 'SANTANDER')# Filtrar eliminando ese registro
        df = df[df['Origen'] != "(nulo)"]
        mapeo = {
            '1. JOVEN': 'Individual',
            '2. ADULTO': 'Individual',
            '3. SENIOR': 'Individual',
            '4. FAMILIAR': 'Familiar',
        }
        df['FechaAntiguedad'] = pd.to_datetime(df['FechaAntiguedad'], origin='1899-12-30', unit='D')
        df['FechaAntiguedad'] = df['FechaAntiguedad'].dt.strftime('%d/%m/%Y')
        # Aplicar el mapeo en una nueva columna
        df['Categoria'] = df['Categoria'].map(mapeo)
        df.columns = [col.replace('.1', '') if col.startswith('IdPersona') else col for col in df.columns]

        if "Email" in df.columns:
            df = df[df["Email"].notna()].copy()
            df["Email"] = df["Email"].str.strip()
            df['Email'] = df['Email'].str.replace(' ', '', regex=False)
        print(df)
        output_path = os.path.join(UPLOAD_SEMANAL_ROUTE, "1_transformation_santander.xlsx")

    # Guardar la única hoja transformada
    df.to_excel(output_path, index=False, engine='openpyxl')
    return output_path

# Automatización con Selenium
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

def acceder_survey_beup(ruta_archivos_partidos, n_semana, close_day, recordatorio, test_mode):
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

        driver.get("https://app.alchemer.com/distribute/share/id/4066595")

        # seleccioanr campaña
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="grid-links"]/div[1]/div[5]/div/table/tbody/tr[1]/td[1]/a'))).click()
        time.sleep(1)

        # Ir a contactos
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div/div/article/div/div[1]/ol/li[2]/a'))).click()


        # Anadir contactos
        for i in archivo:
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="InviteContacts"]/form/div[1]/div[1]/div/div/div/button'))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="contacts-add"]/div/div/div[1]/div[1]/div[2]/a'))).click()

            # Subir archivo
            input_file = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="listcontactimport"]')))
            input_file.send_keys(os.path.abspath(i))
            time.sleep(1)

            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="no-dedupe-csv"]'))).click()

            # Continuar
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="js-contact-upload" and contains(text(), "Continue")]'))).click()
            time.sleep(1)
        # ----------------------------------------------------------------



            # Seleccionar columna "Email"
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[5]/div[3]/select')))
            Select(dropdown).select_by_visible_text("Email")
            time.sleep(1)

            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[2]/div[3]/select')))
            Select(dropdown).select_by_visible_text("Invite Custom Field 1")
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[3]/div[3]/select')))
            Select(dropdown).select_by_visible_text("Invite Custom Field 5")
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[4]/div[3]/select')))
            Select(dropdown).select_by_visible_text("Invite Custom Field 3")
            dropdown = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="importcontactfromcsv"]/div[1]/div[6]/div[3]/select')))
            Select(dropdown).select_by_visible_text("Invite Custom Field 4")
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

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload', methods=['POST'])
def upload():

    try:
        # Obtener parámetros comunes
        proyecto = request.form['proyecto']
        n_semana = int(request.form['entero'])
        close_day = request.form['close_day']
        recordatorio = request.form['recordatorio']
        test_mode = request.form['test_mode']
        test_text = "(Testing)" if test_mode else ""

        # Validaciones comunes
        if not n_semana or not close_day or not recordatorio:
            return jsonify({"error": "Faltan campos obligatorios."}), 400

        # Creación de Carpeta semanal
        UPLOAD_SEMANAL = f"S.{n_semana} {test_text}"
        UPLOAD_SEMANAL_ROUTE = os.path.join(UPLOAD_FOLDER, proyecto, UPLOAD_SEMANAL)
        os.makedirs(UPLOAD_SEMANAL_ROUTE, exist_ok=True)
        DESCARGA_SEMANAL = f"S.{n_semana} {test_text}"
        DESCARGA_SEMANAL_ROUTE = os.path.join(DESCARGAS_FOLDER, proyecto, DESCARGA_SEMANAL)
        os.makedirs(DESCARGA_SEMANAL_ROUTE, exist_ok=True)

        # BEUP: requiere tres archivos
        if proyecto == "beup":
            files = []
            beup_files = []
            mapeo = ["Barakaldo", "Burgos", "Santander"]
            for i in range(1, 4):
                file_key = f'file{i}'
                if file_key not in request.files:
                    return jsonify({"error": f"Falta archivo {i}"}), 400
                f = request.files[file_key]
                if not f.filename.endswith('.xlsx'):
                    return jsonify({"error": f"Archivo {i} no es .xlsx"}), 400

                # Se guarda el archivo subido en upload de la semana actual
                archivo_original_path = os.path.join(UPLOAD_SEMANAL_ROUTE, mapeo[i-1]+".xlsx")
                beup_files.append(archivo_original_path)
                f.save(archivo_original_path)

        else:
            # Otros proyectos: un solo archivo
            if 'file' not in request.files:
                return jsonify({"error": "Falta archivo"}), 400

            f = request.files['file']
            if not f.filename.endswith('.xlsx'):
                return jsonify({"error": "Solo se aceptan archivos .xlsx"}), 400

            # Se guarda el archivo subido en upload de la semana actual
            archivo_original_path = os.path.join(UPLOAD_SEMANAL_ROUTE, f.filename)
            f.save(archivo_original_path)

        print("1. Archivo recibido y validado")



        print("2. directorios de upload y download creados")
        if proyecto == "dreamfit":
            # Añadir columna vacía y arreglar tipo fecha
            archivo_transformado_1_path = ready_for_back_dreamfit(archivo_original_path, UPLOAD_SEMANAL_ROUTE)
            print("3. Archivo transformado para back")

            # Abrir el back de encuestas y obtener el detallado
            archivo_backend_nombre = acceder_backend(archivo_transformado_1_path, DESCARGA_SEMANAL_ROUTE, test_mode, proyecto)
            if not archivo_backend_nombre:
                return jsonify({"error": "No se pudo descargar el archivo desde encuesta.com"}), 500

            print("4. Archivo obtenido desde el back")
            carpeta_semanal = ""
            # Guardarlo en drive
            if not test_mode :
                carpeta_tracking = '1UcVpon9EHccyIMRit8Pub0mr32-80HKE'
                dreamfit_nueva = get_file_id_by_name_in_folder(service, carpeta_tracking, 'Dreamfit Nueva')
                DF_2025  = get_file_id_by_name_in_folder(service, dreamfit_nueva, 'DF 2025')
                nombre_semana_carpeta = "S." + str(n_semana) + " (Testing)"
                carpeta_semanal = create_folder_in_drive(service, DF_2025, nombre_semana_carpeta)

                print("5. Archivo guardado en Drive")

            # Partir el archivo en verioso exceles para poder subirlo a survey
            lista_archivo_backend = obtener_sample_en_carpeta(DESCARGA_SEMANAL_ROUTE)

            archivos_partidos = ready_for_survey(DESCARGA_SEMANAL_ROUTE, lista_archivo_backend[0], n_semana, carpeta_semanal, test_mode)
            print("6. Archivo transformado para survey")

            acceder_survey_dreamfit(DESCARGA_SEMANAL_ROUTE, n_semana, close_day, recordatorio, test_mode)

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}",
                "archivos_partidos":    archivos_partidos
            })

        # ---------------------------------------------------------------------------------------------------------
        elif proyecto == "profitness":
            # Añadir columna vacía y arreglar tipo fecha
            archivo_transformado_1_path = ready_for_back_profitness(archivo_original_path, UPLOAD_SEMANAL_ROUTE)
            print("3. Archivo transformado para back")

            # Abrir el back de encuestas y obtener el detallado
            archivo_backend_nombre = acceder_backend(archivo_transformado_1_path, DESCARGA_SEMANAL_ROUTE, test_mode, proyecto)
            if not archivo_backend_nombre:
                return jsonify({"error": "No se pudo descargar el archivo desde encuesta.com"}), 500

            print("4. Archivo obtenido desde el back")

            carpeta_semanal = ""
            # Guardarlo en drive
            if not test_mode :
                carpeta_tracking = '1UcVpon9EHccyIMRit8Pub0mr32-80HKE'
                dreamfit_nueva = get_file_id_by_name_in_folder(service, carpeta_tracking, 'Profitness')
                DF_2025  = get_file_id_by_name_in_folder(service, dreamfit_nueva, '2025')
                nombre_semana_carpeta = "S." + str(n_semana) + " (Testing)"
                carpeta_semanal = create_folder_in_drive(service, DF_2025, nombre_semana_carpeta)

                print("5. Archivo guardado en Drive")

            # # Partir el archivo en verioso exceles para poder subirlo a survey
            # lista_archivo_backend = obtener_sample_en_carpeta(DESCARGA_SEMANAL_ROUTE)

            # archivos_partidos = ready_for_survey(DESCARGA_SEMANAL_ROUTE, lista_archivo_backend[0], n_semana, carpeta_semanal, test_mode)
            # print("6. Archivo transformado para survey")

            acceder_survey_profitness(DESCARGA_SEMANAL_ROUTE, recordatorio, test_mode)
            print("JJAJA")

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}"
                # , "archivos_partidos":    archivos_partidos
            })

        elif proyecto == "mqa":
            # Añadir columna vacía y arreglar tipo fecha
            archivo_transformado_1_path = ready_for_back_mqa(archivo_original_path, UPLOAD_SEMANAL_ROUTE)
            print("3. Archivo transformado para back")

            # Abrir el back de encuestas y obtener el detallado
            archivo_backend_nombre = acceder_backend(archivo_transformado_1_path, DESCARGA_SEMANAL_ROUTE, test_mode, proyecto)
            if not archivo_backend_nombre:
                return jsonify({"error": "No se pudo descargar el archivo desde encuesta.com"}), 500

            print("4. Archivo obtenido desde el back")

            carpeta_semanal = ""
            # Guardarlo en drive
            if not test_mode :
                carpeta_tracking = '1UcVpon9EHccyIMRit8Pub0mr32-80HKE'
                dreamfit_nueva = get_file_id_by_name_in_folder(service, carpeta_tracking, 'MQA')
                DF_2025  = get_file_id_by_name_in_folder(service, dreamfit_nueva, '2025')
                nombre_semana_carpeta = "S." + str(n_semana) + " (Testing)"
                carpeta_semanal = create_folder_in_drive(service, DF_2025, nombre_semana_carpeta)

                print("5. Archivo guardado en Drive")

            # # Partir el archivo en verioso exceles para poder subirlo a survey
            # lista_archivo_backend = obtener_sample_en_carpeta(DESCARGA_SEMANAL_ROUTE)

            # archivos_partidos = ready_for_survey(DESCARGA_SEMANAL_ROUTE, lista_archivo_backend[0], n_semana, carpeta_semanal, test_mode)
            # print("6. Archivo transformado para survey")

            acceder_survey_mqa(DESCARGA_SEMANAL_ROUTE, n_semana, close_day, recordatorio, test_mode)
            print("JJAJA")

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}"
                #, "archivos_partidos":    archivos_partidos
            })

        elif proyecto == "beup":
            # Añadir columna vacía y arreglar tipo fecha
            for idx, file_path in enumerate(beup_files):
                print(idx, file_path)
                archivo_transformado_1_path = ready_for_back_beup(file_path, UPLOAD_SEMANAL_ROUTE)
                print("3. Archivo transformado para back")

                # Abrir el back de encuestas y obtener el detallado
                archivo_backend_nombre = acceder_backend(archivo_transformado_1_path, DESCARGA_SEMANAL_ROUTE, test_mode, proyecto)
                if not archivo_backend_nombre:
                    return jsonify({"error": "No se pudo descargar el archivo desde encuesta.com"}), 500

            print("4. Archivo obtenido desde el back")

            carpeta_semanal = ""
            # Guardarlo en drive
            if not test_mode :
                carpeta_tracking = '1UcVpon9EHccyIMRit8Pub0mr32-80HKE'
                dreamfit_nueva = get_file_id_by_name_in_folder(service, carpeta_tracking, 'MQA')
                DF_2025  = get_file_id_by_name_in_folder(service, dreamfit_nueva, '2025')
                nombre_semana_carpeta = "S." + str(n_semana) + " (Testing)"
                carpeta_semanal = create_folder_in_drive(service, DF_2025, nombre_semana_carpeta)

                print("5. Archivo guardado en Drive")

            # # Partir el archivo en verioso exceles para poder subirlo a survey
            # lista_archivo_backend = obtener_sample_en_carpeta(DESCARGA_SEMANAL_ROUTE)

            # archivos_partidos = ready_for_survey(DESCARGA_SEMANAL_ROUTE, lista_archivo_backend[0], n_semana, carpeta_semanal, test_mode)
            # print("6. Archivo transformado para survey")

            acceder_survey_beup(DESCARGA_SEMANAL_ROUTE, n_semana, close_day, recordatorio, test_mode)
            print("JJAJA")

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}"
                #, "archivos_partidos":    archivos_partidos
            })

    except Exception as e:
        print("❌ Se produjo un error durante la automatización:")
        traceback.print_exc()  # Muestra el traceback completo
        # También podrías guardar el error en un log:
        with open("errores_automatizacion.log", "a", encoding="utf-8") as f:
            f.write("Error en acceder_survey:\n")
            f.write(traceback.format_exc())
            f.write("\n" + "-"*60 + "\n")

@app.route('/descargar/<filename>')
def descargar(filename):
    return send_from_directory(DESCARGAS_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
