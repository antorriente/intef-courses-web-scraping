import re
import time
import random
import urllib.robotparser
import urllib.request
from urllib.error import URLError, HTTPError
from typing import Tuple


def verificar_robots_txt(url_base: str, ruta: str, user_agent: str) -> bool:
    """
    Comprueba programáticamente el archivo robots.txt del servidor antes de hacer scraping.
    Cumple con los principios éticos y legales exigidos en la práctica.
    """
    robots_url = f"{url_base.rstrip('/')}/robots.txt"
    url_objetivo = f"{url_base.rstrip('/')}/{ruta.lstrip('/')}"
    rp = urllib.robotparser.RobotFileParser()

    print(f"[*] Analizando directivas éticas en: {robots_url}")
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=10) as response:
            contenido = response.read().decode("utf-8", errors="ignore")
            rp.parse(contenido.splitlines())

            # Verificamos si nuestro User-Agent tiene permiso para la ruta objetivo
            permitido = rp.can_fetch(user_agent, url_objetivo)
            print(f"[+] Resultado robots.txt para '{url_objetivo}': Permitido = {permitido}")
            return permitido

    except HTTPError as e:
        if e.code == 404:
            # Estándar RFC 9309: Si el servidor devuelve 404 para robots.txt, no hay restricciones
            print(f"[+] {robots_url} devuelve HTTP 404 (no existen restricciones). Rastreo permitido.")
            return True
        print(f"[!] Error HTTP {e.code} al consultar {robots_url}. Abortando por precaución.")
        return False

    except URLError as e:
        print(f"[!] Aviso de red al verificar {robots_url} ({e}). Continuando con precaución.")
        return True


def pausa_responsable(min_seg: float = 1.5, max_seg: float = 3.5) -> None:
    """
    Implementa Rate Limiting mediante una pausa aleatoria uniforme para evitar
    saturar el servidor del Ministerio de Educación.
    """
    tiempo_espera = random.uniform(min_seg, max_seg)
    time.sleep(tiempo_espera)


def extraer_modalidad_y_edicion(titulo: str) -> Tuple[str, int]:
    """
    Extrae mediante expresiones regulares la modalidad del curso (MOOC, NOOC, SPOOC...)
    y el número de edición a partir del título en bruto.
    """
    modalidad = "Tutorizado / Otro"
    for mod in ["MOOC", "NOOC", "SPOOC", "EduPills"]:
        if mod.lower() in titulo.lower():
            modalidad = mod
            break

    match_edicion = re.search(r"(\d+)\s*(?:ª|\.|a)?\s*edici[óo]n", titulo, re.IGNORECASE)
    edicion = int(match_edicion.group(1)) if match_edicion else 1
    return modalidad, edicion