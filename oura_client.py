"""
Cliente OAuth2 + API para Oura Ring (API v2).
Maneja el token de acceso y lo renueva solo usando el refresh_token.
"""
import json
import os
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
TOKENS_PATH = BASE_DIR / "tokens.json"

AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
API_BASE = "https://api.ouraring.com/v2"

# Todos los scopes registrados en el portal
SCOPES = (
    "email personal daily heartrate tag workout session "
    "spo2 ring_configuration stress heart_health"
)


def load_env():
    """Carga variables desde .env (parser simple, sin dependencias).

    En la nube (GitHub Actions) no hay .env: las credenciales vienen por
    variables de entorno, asi que devolvemos un dict vacio sin fallar.
    """
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


ENV = load_env()


def _cfg(key, default=None):
    """Prioriza variable de entorno (nube), luego .env (local)."""
    return os.environ.get(key) or ENV.get(key) or default


CLIENT_ID = _cfg("OURA_CLIENT_ID")
CLIENT_SECRET = _cfg("OURA_CLIENT_SECRET")
REDIRECT_URI = _cfg("OURA_REDIRECT_URI", "http://localhost:8000/callback")


def save_tokens(tokens: dict):
    """Guarda tokens y calcula el momento de expiración."""
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600) - 60
    TOKENS_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")


def load_tokens() -> dict | None:
    if not TOKENS_PATH.exists():
        return None
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def exchange_code(code: str) -> dict:
    """Cambia el código de autorización por tokens."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    save_tokens(tokens)
    return tokens


def refresh_access(refresh_token: str) -> dict:
    """Refresca el token SIN guardar en disco (útil en la nube).

    Oura ROTA el refresh_token en cada uso (single-use): la respuesta trae
    uno nuevo que hay que persistir para la próxima corrida.
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens.setdefault("refresh_token", refresh_token)  # por si no rotara
    return tokens


def refresh_tokens(refresh_token: str) -> dict:
    """Refresca y guarda en tokens.json (modo local)."""
    tokens = refresh_access(refresh_token)
    save_tokens(tokens)
    return tokens


def get_access_token() -> str:
    """Devuelve un access_token válido.

    - Nube: si existe OURA_ACCESS_TOKEN en el entorno, lo usa directo.
    - Local: lee tokens.json y lo renueva si expiró.
    """
    env_token = os.environ.get("OURA_ACCESS_TOKEN")
    if env_token:
        return env_token

    tokens = load_tokens()
    if not tokens:
        raise RuntimeError(
            "No hay tokens guardados. Ejecutá primero: python 1_authorize.py"
        )
    if time.time() >= tokens.get("expires_at", 0):
        print("Token expirado, renovando...")
        tokens = refresh_tokens(tokens["refresh_token"])
    return tokens["access_token"]


def api_get(path: str, params: dict | None = None) -> dict:
    """GET a la API v2 con paginación automática (next_token)."""
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = dict(params or {})
    all_data = []
    while True:
        resp = requests.get(
            f"{API_BASE}{path}", headers=headers, params=params, timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        all_data.extend(payload.get("data", []))
        next_token = payload.get("next_token")
        if not next_token:
            break
        params["next_token"] = next_token
    return {"data": all_data}
