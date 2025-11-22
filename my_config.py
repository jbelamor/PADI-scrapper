TOKEN = "tu_bot_token"

subjects_dict = {
    'INFORMÁTICA': {'name': 'INFORMÁTICA', 'code': '0590107'},
    'SISTEMAS Y APLICACIONES INFORMÁTICAS': {'name': 'SISTEMAS Y APLICACIONES INFORMÁTICAS', 'code': '0590227'},
    'MATEMATICAS': {'name': 'MATEMATICAS', 'code': '0590006'},
    'TECNOLOGIA': {'name': 'TECNOLOGIA', 'code': '0590019'},
    'INSTALACIÓN Y MANTENIMIENTO DE EQUIPOS TÉRMICO Y DE FLUIDOS': {'name': 'INSTALACIÓN Y MANTENIMIENTO DE EQUIPOS TÉRMICO Y DE FLUIDOS', 'code': '0590205'},
    'ORGANIZACIÓN Y PROYECTOS DE SISTEMAS ENERGÉTICOS': {'name': 'ORGANIZACIÓN Y PROYECTOS DE SISTEMAS ENERGÉTICOS', 'code': '0590113'},
}

users = {
    "username": {
        "user_id": "tu_chat_id",
        "asignaturas": [subjects_dict['INFORMÁTICA'], 
                        subjects_dict['SISTEMAS Y APLICACIONES INFORMÁTICAS']],
        },
    "username2": {
        "user_id": "tu_chat_id",
        "asignaturas": [subjects_dict['MATEMATICAS'],
                        subjects_dict['TECNOLOGIA']],
        },
}