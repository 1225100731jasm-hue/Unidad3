# Lab 2.5 - Parte 2: eliminar la interfaz Loopback99 (DELETE)
import requests

# Oculta las advertencias del certificado SSL
requests.packages.urllib3.disable_warnings()

# Misma URL que apunta a Loopback99
api_url = "https://10.10.20.48/restconf/data/ietf-interfaces:interfaces/interface=Loopback99"

# Encabezados: formato YANG/JSON
headers = {
    "Accept": "application/yang-data+json",
    "Content-type": "application/yang-data+json"
}

# Usuario y contraseña
basicauth = ("developer", "C1sco12345")

# CAMBIO 1: se usa requests.delete en lugar de requests.put
# CAMBIO 2: ya no se envía "data", porque DELETE no necesita cuerpo
resp = requests.delete(api_url, auth=basicauth, headers=headers, verify=False)

# Códigos 200 a 299 significan éxito
if (resp.status_code >= 200 and resp.status_code <= 299):
    print("STATUS OK: {}".format(resp.status_code))
else:
    print("Error code {}, reply: {}".format(resp.status_code, resp.text))
