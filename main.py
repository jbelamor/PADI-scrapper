import requests
from datetime import datetime
import config as vars
from telegram_function import send_telegram_message
import json
import os

###############
# GLOBAL VARS #
###############
file_tracker = "historial_padi.jsonl"

############
# REQUESTS #
############
headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8,es-ES;q=0.7,es;q=0.6',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://gestiona.comunidad.madrid',
    'Referer': 'https://gestiona.comunidad.madrid/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
    'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

json_data = {
    'fcpublico': datetime.now().strftime('%Y-%m-%d'),
    'cfunc': '0590107',
    'coddat': 'T',
    'itperfilacto': 'E',
}

subjects_dict = {
    'INFORMÁTICA': '0590107',
    'SISTEMAS Y APLICACIONES INFORMÁTICAS': '0590227',
}

request_URL = 'https://gestiona7.madrid.org/nsus_rest_ares/v1/ActosPublicosSustituciones/consultaNecesidades'

###########
# STRINGS #
###########
MESSAGE_TEMPLATE = (
    "🏫 *Centro*: {centro}\n"
    "📍 *Localidad*: {localidad}\n"
    "📘 *Asignatura*: {asignatura}\n"
    "🕒 *Horario*: {horario}\n"
    "📌 *Observaciones*: {observaciones}\n"
    "🗓️ *Hasta*: {hasta}\n"
    "⚠️ *Causa*: {causa}\n"
)

########### FUNCTIONS ###########
def save_record(record, asignatura, file_path=file_tracker):
    """
    Guarda el registro en formato JSONL.
    """

    registro = {
        "timestamp": datetime.now().isoformat(),
        "id_susti": record.get("idnsustituciones"),
        "centro": record.get("centro", ""),
        "localidad": record.get("localidad", ""),
        "asignatura": asignatura,
        "horario": record.get("dtipopuesto") or "JORNADA COMPLETA",
        "observaciones": record.get("observaciones", "").strip(),
        "hasta": record.get("fhasta", ""),
        "causa": record.get("causa", "")
    }

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    return registro


def is_new_record(record, file_path=file_tracker):
    """
    Comprueba si el campo id_susti ya está en el fichero JSONL.
    Retorna True → si es nuevo
    Retorna False → si ya existía
    """

    id_susti = record.get("idnsustituciones")

    # Si el archivo no existe aún → todo es nuevo
    if not os.path.exists(file_path):
        return True

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
                if existing.get("id_susti") == id_susti:
                    return False
            except json.JSONDecodeError:
                pass  # líneas corruptas → ignorar

    return True

def process_all_results(results_json, asignatura, file_path=file_tracker):
    """
    Recorre la lista completa de resultados. Para cada registro:
        - comprueba si existe
        - si no existe → lo guarda
        - devuelve una lista de los registros nuevos
    """
    nuevos = []

    for record in results_json:
        if is_new_record(record, file_path):
            new_record = save_record(record, asignatura, file_path)
            nuevos.append(new_record)
    return nuevos

def parse_date(date_str):
    y, m, d = date_str.split('-')
    return(f"{d}/{m}/{y}")

def parse_response(result_json):
    message = MESSAGE_TEMPLATE.format(**result_json)
    return(message)

def fetch_data(subject_code):
    json_data['cfunc'] = subject_code
    response = requests.post(
        request_URL,
        json=json_data,
        headers=headers
        )
    result = response.json()
    return(result)

def main():
    aux_message = ''
    for subject_name, subject_code in subjects_dict.items():
        # For every subject, I request the data from PADI
        all_results = fetch_data(subject_code)
        new_records = process_all_results(all_results)
        for record in new_records:
            aux_message += parse_response(record, subject_name) + '\n'
    if aux_message != '':
        final_message = "📚 *Nueva actualización de PADI*\n\n" + aux_message.replace('_', ' ')
        print(final_message)
        res = send_telegram_message(vars.TOKEN, vars.CHAT_ID, final_message)
if __name__ == "__main__":
    main()