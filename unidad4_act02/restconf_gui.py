import ipaddress
import json
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import quote

import requests

# El router usa un certificado autofirmado: se desactivan las advertencias SSL
# (equivale a poner "SSL certificate verification" en OFF en Postman).

requests.packages.urllib3.disable_warnings()


# Valores por defecto del sandbox; se pueden cambiar desde la propia ventana.
DEFAULT_HOST = "10.10.20.48"
DEFAULT_USER = "developer"
DEFAULT_PASS = "C1sco12345"

# Encabezados HTTP que exige RESTCONF para trabajar con JSON:
#   Accept       -> formato en el que queremos RECIBIR la respuesta
#   Content-Type -> formato del cuerpo que ENVIAMOS (PUT)
HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}

# Segundos máximos de espera por el router. Evita que la ventana se quede
# "congelada" si no hay conexión (por ejemplo, si se cae la VPN).
TIMEOUT = 10

# Colores de la barra de estado
COLOR_OK = "#2e7d32"      # verde  -> operación exitosa
COLOR_ERROR = "#c62828"   # rojo   -> error
COLOR_INFO = "#455a64"    # gris   -> mensajes informativos

# Mensajes legibles para los códigos HTTP más comunes
ERROR_MESSAGES = {
    400: "Error 400: solicitud mal formada.",
    401: "Error 401: usuario o contraseña incorrectos.",
    403: "Error 403: acceso prohibido.",
    404: "Error 404: la interfaz o la URL no existe.",
    415: "Error 415: formato de contenido no soportado.",
    500: "Error 500: error interno del router.",
}


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES (no dependen de la ventana, por eso son fáciles de probar)
# ---------------------------------------------------------------------------

def validate_name(name):
    """Valida el nombre de la interfaz para crear/actualizar/eliminar.

    Por seguridad solo se permiten interfaces Loopback: modificar o borrar
    GigabitEthernet1 (la interfaz de administración) podría cortar el acceso
    al router. Devuelve un mensaje de error, o None si el nombre es válido.
    """
    if not name:
        return "Escribe el nombre de la interfaz."
    if not name.lower().startswith("loopback"):
        return "Solo se pueden crear/modificar/eliminar interfaces Loopback (ej. Loopback25)."
    return None


def validate_form(name, ip, mask):
    """Valida los datos del formulario. Devuelve un mensaje de error o None."""
    error = validate_name(name)
    if error:
        return error
    try:
        ipaddress.IPv4Address(ip)
    except ValueError:
        return "La dirección IP no es válida (ej. 25.25.25.25)."
    try:
        # Truco: una máscara válida (255.255.255.0) funciona como prefijo de red
        ipaddress.IPv4Network(f"0.0.0.0/{mask}")
    except ValueError:
        return "La máscara no es válida (ej. 255.255.255.0)."
    return None


def build_yang_config(name, ip, mask, description):
    """Arma el diccionario ``yangConfig`` con el modelo YANG ietf-interfaces.

    Convierte los textos capturados en los tk.Entry en la estructura JSON que
    espera el router. Nota: el ``True`` de Python se convierte en ``true`` de
    JSON cuando se aplica json.dumps().
    """
    return {
        "ietf-interfaces:interface": {
            "name": name,
            "description": description,
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {"ip": ip, "netmask": mask}
                ]
            },
            "ietf-ip:ipv6": {},
        }
    }


def parse_interface(data):
    """Extrae del JSON del router solo los datos que se muestran en pantalla.

    En lugar de imprimir el JSON completo, devuelve un diccionario ordenado
    con: nombre, descripción, tipo, estado, IP y máscara.
    """
    iface = data.get("ietf-interfaces:interface", {})
    if isinstance(iface, list):                 # el router puede devolver una lista
        iface = iface[0] if iface else {}
    addresses = iface.get("ietf-ip:ipv4", {}).get("address", [])
    first = addresses[0] if addresses else {}   # primera IP configurada (si hay)
    return {
        "Nombre": iface.get("name", "-"),
        "Descripción": iface.get("description", "(sin descripción)"),
        "Tipo": iface.get("type", "-"),
        "Estado": "Habilitada" if iface.get("enabled") else "Deshabilitada",
        "Dirección IP": first.get("ip", "Sin IP"),
        "Máscara": first.get("netmask", "-"),
    }


def describe_error(resp):
    """Devuelve un texto claro para una respuesta HTTP con error."""
    return ERROR_MESSAGES.get(resp.status_code,
                              f"Error {resp.status_code}: {resp.reason}")


# ---------------------------------------------------------------------------
# CLASE PRINCIPAL DE LA INTERFAZ
# ---------------------------------------------------------------------------

class RestconfApp:
    """Ventana principal del cliente RESTCONF.

    Cada botón está conectado a un método "manejador" (callback). Tkinter
    llama a ese método solo cuando el usuario hace clic; mientras tanto el
    mainloop mantiene la ventana activa y esperando eventos.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Cliente RESTCONF - IOS XE")
        self.root.geometry("760x680")
        self.root.minsize(720, 640)

        # Variables ligadas a los campos de texto (StringVar).
        # Con .get() se lee lo que el usuario escribió.
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.user_var = tk.StringVar(value=DEFAULT_USER)
        self.pass_var = tk.StringVar(value=DEFAULT_PASS)
        self.query_name_var = tk.StringVar(value="GigabitEthernet1")
        self.form_name_var = tk.StringVar()
        self.ip_var = tk.StringVar()
        self.mask_var = tk.StringVar(value="255.255.255.0")
        self.desc_var = tk.StringVar()

        # La barra de estado se crea primero para que quede pegada abajo.
        self._build_status_bar()
        self._build_connection_frame()
        self._build_query_frame()
        self._build_form_frame()

        self._set_status("Listo. Conecta la VPN y presiona un botón.", "info")

    # -- Construcción de la interfaz ---------------------------------------

    def _build_connection_frame(self):
        """Datos de conexión: host, usuario y contraseña (Basic Auth)."""
        frame = ttk.LabelFrame(self.root, text="Conexión al router")
        frame.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(frame, text="IP / Host:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        ttk.Entry(frame, textvariable=self.host_var, width=18).grid(row=0, column=1, padx=4)

        ttk.Label(frame, text="Usuario:").grid(row=0, column=2, padx=8, sticky="e")
        ttk.Entry(frame, textvariable=self.user_var, width=14).grid(row=0, column=3, padx=4)

        ttk.Label(frame, text="Contraseña:").grid(row=0, column=4, padx=8, sticky="e")
        # show="*" oculta la contraseña mientras se escribe
        ttk.Entry(frame, textvariable=self.pass_var, width=16, show="*").grid(row=0, column=5, padx=(4, 8))

    def _build_query_frame(self):
        """Desafío 1: campo + botón para consultar (GET) y tabla de resultados."""
        frame = ttk.LabelFrame(self.root, text="Consultar interfaz (GET)")
        frame.pack(fill="both", expand=True, padx=12, pady=6)

        top = ttk.Frame(frame)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Nombre de la interfaz:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.query_name_var, width=26)
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", lambda event: self.consult_interface())  # Enter también consulta

        ttk.Button(top, text="Consultar Interfaz",
                   command=self.consult_interface).pack(side="left")

        # Treeview: tabla de dos columnas (Campo / Valor) para mostrar el
        # resultado de forma ordenada, sin el JSON completo.
        self.table = ttk.Treeview(frame, columns=("campo", "valor"),
                                  show="headings", height=6)
        self.table.heading("campo", text="Campo")
        self.table.heading("valor", text="Valor")
        self.table.column("campo", width=170, anchor="w")
        self.table.column("valor", width=480, anchor="w")
        self.table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_form_frame(self):
        """Desafíos 2 y 3: formulario para crear/actualizar (PUT) y eliminar (DELETE)."""
        frame = ttk.LabelFrame(self.root, text="Crear / Actualizar / Eliminar interfaz Loopback (PUT / DELETE)")
        frame.pack(fill="x", padx=12, pady=6)

        fields = [
            ("Nombre de interfaz:", self.form_name_var),
            ("Dirección IP:", self.ip_var),
            ("Máscara:", self.mask_var),
            ("Descripción:", self.desc_var),
        ]
        for row, (label, var) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, padx=8, pady=4, sticky="e")
            ttk.Entry(frame, textvariable=var, width=48).grid(row=row, column=1, padx=4, pady=4, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Crear/Actualizar Interfaz",
                   command=self.create_interface).pack(side="left", padx=8)
        ttk.Button(buttons, text="Eliminar Interfaz",
                   command=self.delete_interface).pack(side="left", padx=8)

    def _build_status_bar(self):
        """Desafío 4: barra de estado inferior que cambia de color y texto."""
        self.status = tk.Label(self.root, text="", anchor="w", padx=12, pady=8,
                               fg="white", bg=COLOR_INFO,
                               font=("Segoe UI", 10, "bold"))
        self.status.pack(side="bottom", fill="x")

    # -- Utilidades internas -----------------------------------------------

    def _set_status(self, text, kind):
        """Cambia texto y color de la barra. kind: 'ok' (verde), 'error' (rojo) o 'info' (gris)."""
        colors = {"ok": COLOR_OK, "error": COLOR_ERROR, "info": COLOR_INFO}
        self.status.config(text=text, bg=colors[kind])
        self.root.update_idletasks()   # refresca la pantalla antes de seguir

    def _url(self, name):
        """Construye la URL RESTCONF de una interfaz.

        quote(..., safe="") codifica caracteres especiales; por ejemplo,
        'GigabitEthernet0/0/0' se convierte en 'GigabitEthernet0%2F0%2F0'.
        """
        host = self.host_var.get().strip()
        return (f"https://{host}/restconf/data/"
                f"ietf-interfaces:interfaces/interface={quote(name, safe='')}")

    def _request(self, method, name, body=None):
        """Envía la petición HTTP al router dentro de un try-except.

        Devuelve una tupla (respuesta, mensaje_de_error). Si hubo un problema
        de red, la respuesta es None y el mensaje explica qué pasó; así la
        ventana nunca se cae por un error de conexión.
        """
        if not self.host_var.get().strip():
            return None, "Escribe la IP o host del router."
        try:
            resp = requests.request(
                method,
                self._url(name),
                auth=(self.user_var.get().strip(), self.pass_var.get()),  # Basic Auth
                headers=HEADERS,
                data=json.dumps(body) if body is not None else None,
                verify=False,      # certificado autofirmado
                timeout=TIMEOUT,
            )
            return resp, None
        except requests.exceptions.Timeout:
            return None, "Tiempo de espera agotado. ¿La VPN sigue conectada?"
        except requests.exceptions.ConnectionError:
            return None, "No se pudo conectar con el router. Revisa la VPN y la IP."
        except requests.exceptions.RequestException as exc:
            return None, f"Error de red: {exc}"

    def _clear_table(self):
        """Vacía la tabla de resultados."""
        for item in self.table.get_children():
            self.table.delete(item)

    # -- Manejadores de los botones (callbacks) ----------------------------

    def consult_interface(self):
        """Botón 'Consultar Interfaz': GET de una interfaz y muestra IP, máscara y estado."""
        name = self.query_name_var.get().strip()
        if not name:
            self._set_status("Escribe el nombre de la interfaz a consultar.", "error")
            return

        self._set_status(f"Consultando {name}...", "info")
        resp, error = self._request("GET", name)

        if error:                                   # fallo de red / VPN
            self._clear_table()
            self._set_status(error, "error")
            return

        if resp.status_code == 200:
            try:
                data = resp.json()                  # convierte el JSON a diccionario Python
            except ValueError:
                self._clear_table()
                self._set_status("El router respondió algo que no es JSON válido.", "error")
                return
            self._clear_table()
            for campo, valor in parse_interface(data).items():
                self.table.insert("", "end", values=(campo, valor))
            self._set_status(f"Operación exitosa (STATUS {resp.status_code})", "ok")
        else:                                       # 401, 404, 500, etc.
            self._clear_table()
            self._set_status(describe_error(resp), "error")

    def create_interface(self):
        """Botón 'Crear/Actualizar Interfaz': arma el JSON desde el formulario y hace PUT."""
        name = self.form_name_var.get().strip()
        ip = self.ip_var.get().strip()
        mask = self.mask_var.get().strip()
        description = self.desc_var.get().strip()

        problem = validate_form(name, ip, mask)
        if problem:
            self._set_status(problem, "error")
            return

        # Los datos de los Entry se empaquetan en el diccionario yangConfig
        yang_config = build_yang_config(name, ip, mask, description)

        self._set_status(f"Enviando configuración de {name}...", "info")
        resp, error = self._request("PUT", name, yang_config)

        if error:
            self._set_status(error, "error")
            return

        if 200 <= resp.status_code <= 299:
            # PUT devuelve 201 Created si la interfaz es nueva
            # y 204 No Content si ya existía y solo se actualizó.
            accion = "creada" if resp.status_code == 201 else "actualizada"
            self._set_status(f"Operación exitosa (STATUS {resp.status_code})", "ok")
            messagebox.showinfo("Éxito",
                                f"La interfaz {name} fue {accion} correctamente.\n"
                                f"Código HTTP: {resp.status_code}")
            self.query_name_var.set(name)   # deja lista la consulta para verificarla
        else:
            self._set_status(describe_error(resp), "error")

    def delete_interface(self):
        """Botón 'Eliminar Interfaz': pide confirmación y luego hace DELETE."""
        name = self.form_name_var.get().strip()

        problem = validate_name(name)
        if problem:
            self._set_status(problem, "error")
            return

        # askyesno devuelve True si el usuario presiona "Sí"
        confirmed = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Seguro que deseas eliminar la interfaz {name}?\n"
            "Esta acción no se puede deshacer.")
        if not confirmed:
            self._set_status("Eliminación cancelada.", "info")
            return

        self._set_status(f"Eliminando {name}...", "info")
        resp, error = self._request("DELETE", name)

        if error:
            self._set_status(error, "error")
            return

        if 200 <= resp.status_code <= 299:          # normalmente 204 No Content
            self._set_status(f"Operación exitosa (STATUS {resp.status_code})", "ok")
            messagebox.showinfo("Éxito",
                                f"La interfaz {name} fue eliminada.\n"
                                f"Código HTTP: {resp.status_code}")
            self._clear_table()
        else:
            self._set_status(describe_error(resp), "error")


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA
# ---------------------------------------------------------------------------

def main():
    """Crea la ventana y arranca el ciclo de eventos de Tkinter."""
    root = tk.Tk()
    RestconfApp(root)
    root.mainloop()     # la ventana queda esperando clics hasta que se cierre


if __name__ == "__main__":
    main()