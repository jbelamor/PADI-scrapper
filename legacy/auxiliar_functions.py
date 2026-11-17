import requests

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    res = requests.post(url, json=payload)
    return res


headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8,es-ES;q=0.7,es;q=0.6',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://gestiona.comunidad.madrid',
    'Referer': 'https://gestiona.comunidad.madrid/wpad_pub/run/j/BusquedaSencilla.icm',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
    'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

cookies = {
    'srv_id': 'b1e3a22d4e9e59eebaa5b1e8f80cba3b',
    'selectedTab': 'solapas%3D0%3B%3B%3B%3B%3B%3B%3B%3B%3B%3B%3B',
    'JSESSIONID': 'KUmc7hbMqIR2LZvZzFPr0I6T6QqIIzNm0WgRqkyMXhxxrhHw18G5!-356330672!-1099776152',
    'TS01a48228': '0119867edcc318569c853b3cf0250c0a8759d11d346622406144d015f069f68e80164c8c4a15e423e001cf1b94e771954053fc97ca',
    'QueueFair-Store-madrid': 'u:6909bf4d',
    'QueueFair-Pass-prsalaesperaeducacion': 'qfqid=BXDdb1M7C6MdXUpv7JRGKFxMb&qfts=1763567649&qfa=madrid&qfq=prsalaesperaeducacion&qfpt=SafeGuard&qfh=af7f00fa24d868754ae31084384c8703fa69c4d51337d45ad973b02ab05b39c0',
    'srv_id': 'abb43b160db18271d811e05bb983ca0a',
    'TS017d34da': '0119867edcda11eba243d189e9b1ed094e59609588b37bb11f3d32a40c9b6ff567cf9add51c9f5ef8acfc8b8ed5eb803a47816fbca',
    'TS018f9923': '0119867edcda11eba243d189e9b1ed094e59609588b37bb11f3d32a40c9b6ff567cf9add51c9f5ef8acfc8b8ed5eb803a47816fbca',
}

data = 'navegador=Netscape&cdCentro=&dsCentro=&codCentrosNav={0}&formularioConsulta=busquedaSencilla&codCentrosComp=&dscCentrosComp=&siPrivadoComp=&basica.strCodNomMuni={0}&prox_cdmuni=&prox_cddis=0&prox_txtvial=Calle%2C+n%FAmero&prox_cdTpvial=&prox_cdvial=&prox_nmpoliciapk=&prox_distancia='

def get_telephone_ies(ies_id):
    formated_data = data.format(ies_id)
    response = requests.post(
        'https://gestiona.comunidad.madrid/wpad_pub/run/j/BusquedaSencilla.icm',
        # cookies=cookies,
        headers=headers,
        data=formated_data,
        )
    try:
        aux_telephone = response.text.split("title='Teléfono")[1].split("'>")[0].strip()
        aux_telephone = aux_telephone.split(':')[1].strip()
        if 'Fax' in aux_telephone:
            telephone = aux_telephone.split(';')[0].strip()
        else:
            telephone = aux_telephone.strip()
    except IndexError:
        # print(response.text)
        telephone = "No disponible"
    return telephone