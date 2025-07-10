import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('drive', 'v3', credentials=credentials)


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
        return files[0]['id']
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
