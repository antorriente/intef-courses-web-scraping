import ssl
import time
import random
import urllib.robotparser
import urllib.request
from urllib.error import URLError, HTTPError


def verificar_robots_txt(url_base: str, ruta: str, user_agent: str) -> bool:
    """Verifica si el archivo robots.txt permite rastrear la ruta indicada."""
    robots_url = f"{url_base.rstrip('/')}/robots.txt"
    url_objetivo = f"{url_base.rstrip('/')}/{ruta.lstrip('/')}"
    parser = urllib.robotparser.RobotFileParser()

    print(f"[*] Verificando robots.txt en: {robots_url}")

    try:
        contexto_ssl = ssl.create_default_context()
        contexto_ssl.check_hostname = False
        contexto_ssl.verify_mode = ssl.CERT_NONE

        peticion = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(peticion, timeout=10, context=contexto_ssl) as respuesta:
            tipo_contenido = respuesta.headers.get("Content-Type", "").lower()
            texto = respuesta.read().decode("utf-8", errors="ignore")

            if "text/html" in tipo_contenido or "<html" in texto.lower():
                print("[+] No existe fichero robots.txt (devuelve HTML). Rastreo permitido.")
                return True

            parser.parse(texto.splitlines())
            permitido = parser.can_fetch(user_agent, url_objetivo)
            print(f"[+] Permiso según robots.txt para '{ruta}': {permitido}")
            return permitido

    except HTTPError as error:
        if error.code in (301, 302, 303, 404):
            print(f"[+] Sin restricciones en robots.txt (HTTP {error.code}). Rastreo permitido.")
            return True
        print(f"[!] Error HTTP {error.code} al revisar robots.txt.")
        return False

    except URLError as error:
        print(f"[!] Aviso de red ({error}). Continuando con precaución.")
        return True


def pausa_responsable(min_segundos: float = 1.5, max_segundos: float = 3.0) -> None:
    """Detiene la ejecución unos segundos al azar para no saturar el servidor."""
    time.sleep(random.uniform(min_segundos, max_segundos))