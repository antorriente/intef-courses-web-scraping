import os
import re
from typing import List, Dict

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from utils import verificar_robots_txt, pausa_responsable, extraer_modalidad_y_edicion


class IntefScraper:
    """
    Clase principal encargada de la navegación autónoma, descubrimiento de enlaces
    y extracción de datos de los dos portales Moodle del INTEF (/abierta/ y /aulaenabierto/).
    """

    def __init__(self, headless: bool = False):
        self.url_base = "https://formacion.intef.es"
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36 (UOC-DataScience-Scraper/1.0)"
        )
        self.driver = self._iniciar_driver(headless)
        self.datos_cursos: List[Dict] = []

    def _iniciar_driver(self, headless: bool) -> webdriver.Chrome:
        """Inicializa el WebDriver de Chrome y verifica activamente el User-Agent."""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument(f"user-agent={self.user_agent}")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Comprobación obligatoria del User-Agent directamente desde el motor JS del navegador
        ua_verificado = driver.execute_script("return navigator.userAgent;")
        print("[*] WebDriver iniciado correctamente.")
        print(f"[*] User-Agent comprobado en el navegador: {ua_verificado}\n")
        return driver

    def extraer_bloque_abierta(self) -> None:
        """
        BLOQUE 1: Extrae los cursos de Formación Abierta (https://formacion.intef.es/abierta/).
        Incluye interacción con filtros laterales y botones dinámicos con JavaScript.
        """
        ruta = "/abierta/"

        # 1. Comprobación ética de robots.txt antes de entrar al Bloque 1
        if not verificar_robots_txt(self.url_base, ruta, self.user_agent):
            print("[!] Rastreo cancelado en Bloque 1 por directiva robots.txt.")
            return

        url_semilla = f"{self.url_base}{ruta}"
        print(f"[*] Iniciando extracción en Bloque 1 (Formación Abierta): {url_semilla}")
        self.driver.get(url_semilla)
        pausa_responsable(2.0, 4.0)

        # Descubrimiento de enlaces de categorías temáticas
        categorias_elems = self.driver.find_elements(
            By.CSS_SELECTOR, "a[href*='categoryid='], .category-filter a, .list-group-item"
        )
        urls_categorias = []
        for elem in categorias_elems:
            href = elem.get_attribute("href")
            nombre = elem.text.strip()
            if href and "formacion.intef.es" in href and href not in [u[0] for u in urls_categorias]:
                urls_categorias.append((href, nombre or "General"))

        if not urls_categorias:
            urls_categorias = [(url_semilla, "Catálogo Formación Abierta")]

        for url_cat, nombre_cat in urls_categorias:
            print(f"  -> Explorando categoría: {nombre_cat}")
            self.driver.get(url_cat)
            pausa_responsable(1.5, 3.0)

            # Gestión de JavaScript: clic en botones de 'Mostrar más' o 'Finalizados' si existen
            try:
                botones = self.driver.find_elements(
                    By.XPATH, "//button[contains(text(), 'más') or contains(text(), 'Finalizado')]"
                )
                for btn in botones:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        pausa_responsable(1.0, 2.0)
            except Exception:
                pass

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            tarjetas = soup.select(".coursebox, .card, .course-card, article")

            for tarjeta in tarjetas:
                titulo_elem = tarjeta.select_one("h3, h4, .coursename, .card-title, a")
                if not titulo_elem:
                    continue
                titulo = titulo_elem.get_text(strip=True)
                if len(titulo) < 5:
                    continue

                enlace_elem = tarjeta.select_one("a[href]")
                url_curso = enlace_elem["href"] if enlace_elem else url_cat
                id_match = re.search(r"id=(\d+)", url_curso)
                id_curso = f"ABI-{id_match.group(1)}" if id_match else f"ABI-{len(self.datos_cursos) + 1}"

                modalidad, edicion = extraer_modalidad_y_edicion(titulo)
                texto_tarjeta = tarjeta.get_text(" ", strip=True)

                fechas = re.findall(
                    r"\d{1,2}\s+[a-zA-Z]{3,10}[\s,]+\d{4}|\d{2}/\d{2}/\d{4}", texto_tarjeta
                )
                fecha_inicio = fechas[0] if len(fechas) > 0 else None
                fecha_fin = fechas[1] if len(fechas) > 1 else None

                estado = "Finalizado" if "finalizado" in texto_tarjeta.lower() else "En curso / Abierto"

                horas_match = re.search(r"(\d+)\s*(?:horas|h\b)", texto_tarjeta, re.IGNORECASE)
                horas = int(horas_match.group(1)) if horas_match else (3 if modalidad == "NOOC" else 30)

                areas_encontradas = sorted(list(set(re.findall(r"[ÁA]rea\s*\d", texto_tarjeta, re.IGNORECASE))))

                self.datos_cursos.append({
                    "id_curso": id_curso,
                    "titulo": titulo,
                    "bloque_origen": "Formación Abierta",
                    "modalidad": modalidad,
                    "edicion": edicion,
                    "categoria_tematica": nombre_cat,
                    "estado": estado,
                    "fecha_inicio_cruda": fecha_inicio,
                    "fecha_fin_cruda": fecha_fin,
                    "horas_esfuerzo": horas,
                    "areas_cdd": ", ".join(areas_encontradas) if areas_encontradas else "No especificada",
                    "num_areas_cdd": len(areas_encontradas),
                    "num_items_estructura": len(tarjeta.select("li")),
                    "longitud_descripcion_chars": len(texto_tarjeta),
                    "url_ficha": url_curso
                })

    def extraer_bloque_aula_en_abierto(self) -> None:
        """
        BLOQUE 2: Recorre el catálogo de Aula en Abierto (/aulaenabierto/course/index.php)
        realizando descubrimiento de enlaces en 2 niveles (Categoría -> Ficha interna del curso).
        """
        ruta = "/aulaenabierto/course/index.php"

        # 1. Comprobación ética de robots.txt antes de entrar al Bloque 2
        if not verificar_robots_txt(self.url_base, ruta, self.user_agent):
            print("[!] Rastreo cancelado en Bloque 2 por directiva robots.txt.")
            return

        url_semilla = f"{self.url_base}{ruta}"
        print(f"\n[*] Iniciando extracción en Bloque 2 (Aula en Abierto): {url_semilla}")
        self.driver.get(url_semilla)
        pausa_responsable(2.0, 4.0)

        enlaces_cat = self.driver.find_elements(By.CSS_SELECTOR, ".categoryname a, a[href*='categoryid=']")
        categorias = [(e.get_attribute("href"), e.text.strip()) for e in enlaces_cat if e.get_attribute("href")]
        categorias_unicas = list(dict(categorias).items())

        urls_cursos_vistos = set()

        for url_cat, nombre_cat in categorias_unicas:
            print(f"  -> Explorando categoría Moodle: {nombre_cat}")
            self.driver.get(url_cat)
            pausa_responsable(1.5, 3.0)

            soup_cat = BeautifulSoup(self.driver.page_source, "html.parser")
            enlaces_cursos = soup_cat.select("a[href*='course/view.php?id=']")

            for a in enlaces_cursos:
                url_curso = a["href"]
                titulo = a.get_text(strip=True)
                if url_curso in urls_cursos_vistos or not titulo:
                    continue
                urls_cursos_vistos.add(url_curso)

                print(f"    -> Extrayendo ficha de curso: {titulo[:45]}...")
                try:
                    self.driver.get(url_curso)
                    pausa_responsable(1.5, 2.5)
                    soup_curso = BeautifulSoup(self.driver.page_source, "html.parser")

                    id_match = re.search(r"id=(\d+)", url_curso)
                    id_curso = f"AULA-{id_match.group(1)}" if id_match else f"AULA-{len(self.datos_cursos) + 1}"

                    modalidad, edicion = extraer_modalidad_y_edicion(titulo)
                    if modalidad == "Tutorizado / Otro":
                        modalidad = "Tutorizado en Abierto"

                    texto_completo = soup_curso.get_text(" ", strip=True)
                    num_actividades = len(soup_curso.select(".activity, .section li, .course-section"))

                    horas_match = re.search(r"(\d{2,3})\s*(?:horas|h\b)", texto_completo, re.IGNORECASE)
                    horas = int(horas_match.group(1)) if horas_match else None

                    areas_encontradas = sorted(list(set(re.findall(r"[ÁA]rea\s*\d", texto_completo, re.IGNORECASE))))

                    self.datos_cursos.append({
                        "id_curso": id_curso,
                        "titulo": titulo,
                        "bloque_origen": "Aula en Abierto",
                        "modalidad": modalidad,
                        "edicion": edicion,
                        "categoria_tematica": nombre_cat or "Formación Tutorizada",
                        "estado": "Abierto Permanente",
                        "fecha_inicio_cruda": None,
                        "fecha_fin_cruda": None,
                        "horas_esfuerzo": horas,
                        "areas_cdd": ", ".join(areas_encontradas) if areas_encontradas else "No especificada",
                        "num_areas_cdd": len(areas_encontradas),
                        "num_items_estructura": num_actividades,
                        "longitud_descripcion_chars": len(texto_completo),
                        "url_ficha": url_curso
                    })
                except Exception as e:
                    print(f"    [!] Error al procesar {url_curso}: {e}")

    def guardar_csv(self, ruta_salida: str) -> None:
        """Guarda los registros recolectados en formato CSV dentro de /dataset."""
        directorio = os.path.dirname(ruta_salida)
        if directorio:
            os.makedirs(directorio, exist_ok=True)
        df = pd.DataFrame(self.datos_cursos)
        df.to_csv(ruta_salida, index=False, encoding="utf-8")
        print(f"\n[OK] Dataset exportado correctamente en: {ruta_salida}")
        print(f"[OK] Dimensiones del dataset: {df.shape[0]} filas x {df.shape[1]} columnas")

    def cerrar(self) -> None:
        """Cierra la sesión del navegador WebDriver."""
        if self.driver:
            self.driver.quit()
            print("[*] Sesión de Selenium WebDriver finalizada.")