"""
Paso de nube: refresca el token de Oura usando OURA_REFRESH_TOKEN (secret)
y expone:
  - OURA_ACCESS_TOKEN  -> a $GITHUB_ENV  (para el paso de build)
  - el nuevo refresh    -> a $GITHUB_OUTPUT (para re-guardar el secret)

Como Oura rota el refresh token (single-use), esto se hace ANTES de bajar
datos: así el token nuevo se persiste aunque el build fallara.
"""
import os
import sys

import oura_client as oc


def emit(path_env, line):
    path = os.environ.get(path_env)
    if not path:
        print(f"(aviso: {path_env} no definido; corriendo fuera de Actions)")
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    rt = os.environ.get("OURA_REFRESH_TOKEN")
    if not rt:
        sys.exit("Falta OURA_REFRESH_TOKEN en el entorno.")

    tokens = oc.refresh_access(rt)
    access = tokens["access_token"]
    new_rt = tokens["refresh_token"]

    # Access token para el resto del job (no se imprime en logs)
    emit("GITHUB_ENV", f"OURA_ACCESS_TOKEN={access}")
    # Nuevo refresh token como output enmascarado del step
    emit("GITHUB_OUTPUT", f"refresh_token={new_rt}")
    print("::add-mask::" + new_rt)
    print("::add-mask::" + access)
    print("Token refrescado OK.")


if __name__ == "__main__":
    main()
