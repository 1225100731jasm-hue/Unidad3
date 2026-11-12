# Lab 2.5 - Parte 2: crear la interfaz Loopback99 con RESTCONF (PUT)
import json
import requests

# Oculta las advertencias del certificado SSL
requests.packages.urllib3.disable_warnings()

# URL que apunta directo a la interfaz Loopback99
api_url = "https://10.10.20.48/restconf/data/ietf-interfaces:interfaces/interface=Loopback99"

# Encabezados: formato YANG/JSON
headers = {
    "Accept": "application/yang-data+json",
    "Content-type": "application/yang-data+json"
}

# Usuario y contraseña
basicauth = ("developer", "C1sco12345")

# Datos de la interfaz que queremos crear
# (en Python "true" se escribe True con T mayúscula)
yangConfig = {
    "ietf-interfaces:interface": {
        "name": "Loopback99",
        "description": "WHATEVER99",
        "type": "iana-if-type:softwareLoopback",
        "enabled": True,
        "ietf-ip:ipv4": {
            "address": [
                {
                    "ip": "99.99.99.99",
                    "netmask": "255.255.255.0"
                }
            ]
        },
        "ietf-ip:ipv6": {}
    }
}

# Enviar la petición PUT (json.dumps convierte el diccionario a texto JSON)
resp = requests.put(api_url, data=json.dumps(yangConfig), auth=basicauth,
                    headers=headers, verify=False)

# Códigos 200 a 299 significan éxito
if (resp.status_code >= 200 and resp.status_code <= 299):
    print("STATUS OK: {}".format(resp.status_code))
else:
    print("Error code {}, reply: {}".format(resp.status_code, resp.json()))
