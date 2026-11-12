# Lab 2.5 - Parte 1: consultar interfaces con RESTCONF (GET)
import json
import requests

# Oculta las advertencias del certificado SSL
requests.packages.urllib3.disable_warnings()

# Dirección de la API del router (sandbox)
api_url = "https://10.10.20.48/restconf/data/ietf-interfaces:interfaces"

# Encabezados: formato YANG/JSON
headers = {
    "Accept": "application/yang-data+json",
    "Content-type": "application/yang-data+json"
}

# Usuario y contraseña
basicauth = ("developer", "C1sco12345")

# Enviar la petición GET
resp = requests.get(api_url, auth=basicauth, headers=headers, verify=False)

# Convertir la respuesta a formato Python
response_json = resp.json()

# Salida normal (pasos j y k del PDF)
print(response_json)

# Salida con formato bonito (pasos l y m del PDF)
print(json.dumps(response_json, indent=4))

