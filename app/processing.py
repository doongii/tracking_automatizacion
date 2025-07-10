import os
import pandas as pd
import numpy as np

from .drive import upload_file_to_drive, service


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
