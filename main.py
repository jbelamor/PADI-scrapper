import requests
from datetime import datetime, timedelta
import config as vars
from auxiliar_functions import send_telegram_message, get_telephone_ies
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

from datetime import datetime, timedelta

def fecha_segun_hora():
    ahora = datetime.now()
    limite = ahora.replace(hour=15, minute=0, second=0, microsecond=0)

    # 1. Elegir fecha base según la hora
    if ahora < limite:
        fecha = ahora.date()
    else:
        fecha = (ahora + timedelta(days=1)).date()

    # 2. Ajustar si cae en fin de semana
    # weekday(): lunes=0 ... domingo=6
    if fecha.weekday() == 5:  # sábado
        fecha += timedelta(days=2)  # pasa a lunes
    elif fecha.weekday() == 6:  # domingo
        fecha += timedelta(days=1)  # pasa a lunes

    return fecha.strftime("%Y-%m-%d")

json_data = {
    'fcpublico': fecha_segun_hora(),
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
    "📞 *Teléfono IES*: {telefono_ies}\n"
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
        "causa": record.get("causa", ""),
        "ccentro": record.get("ccentro", "")
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
    print(result_json)
    aux_telephone = get_telephone_ies(result_json.get("ccentro", ""))
    result_json['telefono_ies'] = '[' + aux_telephone + '](tel:' + aux_telephone + ')'
    message = MESSAGE_TEMPLATE.format(**result_json)
    # message = message.replace("{telefono_ies}", ))
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

def check_for_user(username):
    user_info = vars.users.get(username)
    # print(user_info)
    aux_message = ''
    for n in user_info["asignaturas"]:
        # For every subject, I request the data from PADI
        subject_name = n['name']
        subject_code = n['code']
        all_results = fetch_data(subject_code)
        new_records = process_all_results(all_results, subject_name)
        # print(new_records)
        for record in new_records:
            aux_message += parse_response(record) + '\n'
    if aux_message != '':
        final_message = "📚 *Nueva actualización de PADI*\n\n" + aux_message.replace('_', ' ')
        # print(final_message)
        res = send_telegram_message(vars.TOKEN, user_info["user_id"], final_message)

def main():
    for username in vars.users.keys():
        check_for_user(username)

if __name__ == "__main__":
    main()