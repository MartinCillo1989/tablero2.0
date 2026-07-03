"""
Módulo para persistir notas de jornada en GitHub via API.
Las notas se guardan en notas_jornada.json en el repo.
"""
import json
import os
import base64
from datetime import datetime

import requests

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "MartinCillo1989/tablero2.0")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "master")
NOTAS_PATH    = "notas_jornada.json"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{NOTAS_PATH}"


def _get_file_info():
    """Obtiene el contenido actual y el SHA del archivo en GitHub."""
    r = requests.get(API_URL, headers=HEADERS, params={"ref": GITHUB_BRANCH})
    if r.status_code == 200:
        data = r.json()
        content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        return content, data["sha"]
    elif r.status_code == 404:
        return {}, None
    else:
        print(f"⚠️  Error leyendo notas: {r.status_code} {r.text}")
        return {}, None


def cargar_notas() -> dict:
    """Lee las notas desde GitHub. Fallback a archivo local si falla."""
    if not GITHUB_TOKEN:
        # Sin token, usar archivo local
        local = os.path.join(os.path.dirname(__file__), NOTAS_PATH)
        if os.path.exists(local):
            with open(local) as f:
                return json.load(f)
        return {}
    try:
        notas, _ = _get_file_info()
        return notas
    except Exception as e:
        print(f"⚠️  Error cargando notas: {e}")
        return {}


def guardar_nota(vendedor: str, fecha: str, nota: str) -> bool:
    """Guarda una nota para un vendedor/fecha en GitHub."""
    if not GITHUB_TOKEN:
        print("⚠️  Sin GITHUB_TOKEN — guardando solo localmente")
        local = os.path.join(os.path.dirname(__file__), NOTAS_PATH)
        try:
            notas = {}
            if os.path.exists(local):
                with open(local) as f:
                    notas = json.load(f)
            key = f"{vendedor}|{fecha}"
            if nota.strip():
                notas[key] = nota.strip()
            elif key in notas:
                del notas[key]
            with open(local, "w") as f:
                json.dump(notas, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️  Error guardando local: {e}")
            return False

    try:
        notas, sha = _get_file_info()
        key = f"{vendedor}|{fecha}"
        if nota.strip():
            notas[key] = nota.strip()
        elif key in notas:
            del notas[key]

        content_b64 = base64.b64encode(
            json.dumps(notas, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")

        payload = {
            "message": f"nota jornada {vendedor} {fecha}",
            "content": content_b64,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(API_URL, headers=HEADERS, json=payload)
        if r.status_code in (200, 201):
            print(f"✅ Nota guardada: {key}")
            return True
        else:
            print(f"⚠️  Error guardando nota: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"⚠️  Error guardando nota: {e}")
        return False