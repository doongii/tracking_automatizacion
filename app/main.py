from flask import Flask, request, jsonify, render_template_string, send_from_directory
import os
import traceback

from .templates import HTML
from .drive import service, get_file_id_by_name_in_folder, create_folder_in_drive
from .processing import (
    ready_for_back_dreamfit,
    ready_for_back_profitness,
    ready_for_back_mqa,
    ready_for_back_beup,
    obtener_sample_en_carpeta,
    ready_for_survey
)
from .selenium import (
    acceder_backend,
    acceder_survey_dreamfit,
    acceder_survey_profitness,
    acceder_survey_mqa,
    acceder_survey_beup
)

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

            acceder_survey_profitness(DESCARGA_SEMANAL_ROUTE, recordatorio, test_mode)
            print("JJAJA")

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}"
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

            acceder_survey_mqa(DESCARGA_SEMANAL_ROUTE, n_semana, close_day, recordatorio, test_mode)
            print("JJAJA")

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}"
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

            acceder_survey_beup(DESCARGA_SEMANAL_ROUTE, n_semana, close_day, recordatorio, test_mode)
            print("JJAJA")

            return jsonify({
                "message": f"Archivo procesado y subido correctamente. Semana_actual {n_semana}"
            })

    except Exception as e:
        print("❌ Se produjo un error durante la automatización:")
        traceback.print_exc()
        with open("errores_automatizacion.log", "a", encoding="utf-8") as f:
            f.write("Error en acceder_survey:\n")
            f.write(traceback.format_exc())
            f.write("\n" + "-"*60 + "\n")


@app.route('/descargar/<filename>')
def descargar(filename):
    return send_from_directory(DESCARGAS_FOLDER, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
