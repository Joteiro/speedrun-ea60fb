"""
Autorización OAuth2 con Oura — ejecutar UNA sola vez.

Abre el navegador, hacés clic en "Autorizar", y este script captura
el código automáticamente en http://localhost:8000/callback,
lo intercambia por tokens y los guarda en tokens.json.
"""
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import oura_client as oc

PORT = 8000
_auth_code = {"value": None}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        _auth_code["value"] = code
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = (
            "<h2>Listo</h2><p>Autorizacion recibida. "
            "Ya podes cerrar esta pestana y volver a la terminal.</p>"
            if code
            else "<h2>Error</h2><p>No se recibio el codigo.</p>"
        )
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, *args):
        pass  # silenciar logs del servidor


def main():
    query = urllib.parse.urlencode(
        {
            "client_id": oc.CLIENT_ID,
            "redirect_uri": oc.REDIRECT_URI,
            "response_type": "code",
            "scope": oc.SCOPES,
        }
    )
    auth_url = f"{oc.AUTH_URL}?{query}"

    print("Abriendo el navegador para autorizar...")
    print(f"Si no se abre solo, pega esta URL en el navegador:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print(f"Esperando el callback en http://localhost:{PORT}/callback ...")
    server = HTTPServer(("localhost", PORT), CallbackHandler)
    while _auth_code["value"] is None:
        server.handle_request()

    code = _auth_code["value"]
    print("Codigo recibido. Intercambiando por tokens...")
    oc.exchange_code(code)
    print("OK: tokens guardados en tokens.json")
    print("Ya podes ejecutar: python 2_fetch.py")


if __name__ == "__main__":
    main()
