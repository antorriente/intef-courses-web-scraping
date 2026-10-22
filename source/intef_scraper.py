import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from utils import verify_robots_txt, safety_pause


class IntefScraper:
    """
    Process of extracting INTEF training courses using a web scraper.
    """

    def __init__(self, headless: bool = False):
        self.base_url = "https://formacion.intef.es"
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36 (UOC-DataScienceTypology-WebScraper/1.0)"
        )
        self.driver = self._driver_config(headless)
        self.raw_data = []

    def _driver_config(self, headless: bool) -> webdriver.Chrome:
        """
        Launch Chrome and verify the User-Agent from the browser.
        """
        options = Options()
        if headless:
            options.add_argument("--headless=new")

        options.add_argument(f"user-agent={self.user_agent}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-background-networking")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        service = Service(ChromeDriverManager().install(), log_output=os.devnull)
        driver = webdriver.Chrome(service=service, options=options)

        ua_browser = driver.execute_script("return navigator.userAgent;")
        print(f"WebDriver started. User-Agent active.: {ua_browser}\n")
        return driver

    def _clean_noise_dom(self, soup_node) -> None:
        """
        Remove hidden system elements (<noscript>, <script>, and close buttons) before reading
        """
        for tag in soup_node.select("noscript, script, style, button.close, .sr-only, .accesshide"):
            tag.decompose()

    def _extract_patterns(self, text: str) -> dict:
        """
        Extract attributes using regular expressions.
        """
        dates = re.findall(
            r"\d{1,2}\s+(?:de\s+)?[a-zA-Záéíóú]{3,12}[\s,]+\d{4}|\d{2}/\d{2}/\d{4}"
            r"|(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{4}",
            text, re.IGNORECASE
        )
        hours = re.search(r"\d{1,3}\s*(?:horas|h\b)", text, re.IGNORECASE)
        edition = re.search(r"\d+\s*(?:ª|\.|a)?\s*edici[óo]n|\d+ª\s*Conv_\d{4}", text, re.IGNORECASE)
        format = re.search(r"\b(MOOC|NOOC|SPOOC|Curso)\b", text, re.IGNORECASE)
        skills = re.findall(r"(?:[ÁA]rea\s*\d|[1-6]\.[1-5]|\b[ABC][12]\b)", text)
        estate = re.search(r"\b(Finalizado|En curso|Abierto|Próximamente)\b", text, re.IGNORECASE)

        return {
            "modalidad": format.group(0) if format else None,
            "edicion": edition.group(0) if edition else None,
            "estado": estate.group(0) if estate else None,
            "fechas": " | ".join(dict.fromkeys(dates)) if dates else None,
            "duracion": hours.group(0) if hours else None,
            "competencias": ", ".join(dict.fromkeys(skills)) if skills else None
        }

    ### Block 1: Open Training (/abierta/)

    def extract_open_training(self) -> None:
        """
        Extract data from open training courses.
        """
        if not verify_robots_txt(self.base_url, "/abierta/", self.user_agent):
            return

        titles = set()

        # 1. Front Page
        url_front = f"{self.base_url}/abierta/"
        print(f"Exploring the Block 1 front page.: {url_front}")
        self.driver.get(url_front)
        safety_pause(2.0, 3.0)
        self._expand_tabs_scroll()

        soup_front = BeautifulSoup(self.driver.page_source, "html.parser")
        for modal in soup_front.select(".modal-content"):
            node_title = modal.select_one(".modal-title, h3, h4")
            if not node_title:
                continue
            title = node_title.get_text(" ", strip=True)
            if len(title) < 6 or title in titles:
                continue
            titles.add(title)

            self._clean_noise_dom(modal)
            text = modal.get_text(" ", strip=True)
            patterns = self._extract_patterns(f"{title} {text}")

            self.raw_data.append({
                "id": modal.get("id") or f"abierta-modal-{len(self.raw_data) + 1}",
                "titulo": title,
                "curso_padre": title,
                "bloque_web": "Formación Abierta",
                "categoria": "Catálogo Portada Formación Abierta",
                "modalidad": patterns["modalidad"],
                "edicion": patterns["edicion"],
                "estado": patterns["estado"] or "Publicado en Portada",
                "fechas": patterns["fechas"],
                "duracion": patterns["duracion"],
                "competencias": patterns["competencias"],
                "num_secciones": len(modal.select("h4, h5, strong")),
                "num_recursos": len(modal.select("p")),
                "num_elementos_lista": len(modal.select("li")),
                "num_enlaces": len(modal.select("a")),
                "num_imagenes": len(modal.select("img")),
                "longitud_texto": len(text),
                "extracto_texto": text[:400],
                "url_origen": url_front
            })
            print(f"Open Training Captured: {title[:55]}...")

        # 2. Category Tree
        url_index = f"{self.base_url}/abierta/course/index.php"
        print(f"Finding Categories: {url_index}")
        self.driver.get(url_index)
        safety_pause(2.0, 3.0)

        soup_index = BeautifulSoup(self.driver.page_source, "html.parser")
        urls_categories = [(f"{url_index}?perpage=100", "Índice General Abierta")]

        for category in soup_index.select("a[href*='categoryid=']"):
            href = category.get("href", "")
            name_category = category.get_text(" ", strip=True) or "Categoría Abierta"
            if href.startswith("/"):
                href = f"{self.base_url}{href}"
            if href and "formacion.intef.es" in href:
                sep = "&" if "?" in href else "?"
                url_cat_100 = f"{href}{sep}perpage=100"
                if url_cat_100 not in [c[0] for c in urls_categories]:
                    urls_categories.append((url_cat_100, name_category))

        for url_category, name_category in urls_categories:
            print(f"Exploring Open Category: {name_category}")
            self.driver.get(url_category)
            safety_pause(1.5, 2.5)

            # Expand collapsed subcategories and all information messages with AJAX
            self._expand_info_ajax_moodle()
            soup_category = BeautifulSoup(self.driver.page_source, "html.parser")

            # If expanding reveals new subcategories, add them to the queue
            for sub_category in soup_category.select("a[href*='categoryid=']"):
                sub_href = sub_category.get("href", "")
                if sub_href.startswith("/"):
                    sub_href = f"{self.base_url}{sub_href}"
                sep = "&" if "?" in sub_href else "?"
                sub_url_100 = f"{sub_href}{sep}perpage=100"
                if "formacion.intef.es" in sub_url_100 and sub_url_100 not in [c[0] for c in urls_categories]:
                    urls_categories.append((sub_url_100, sub_category.get_text(" ", strip=True) or name_category))

            for box in soup_category.select(".coursebox"):
                enlace = box.select_one(".coursename a")
                if not enlace:
                    continue
                title = enlace.get_text(" ", strip=True)
                if title in titles:
                    continue
                titles.add(title)

                self._clean_noise_dom(box)
                url_course = enlace.get("href", url_category)
                id_moodle = box.get("data-courseid") or "s/n"
                text_box = box.get_text(" ", strip=True)
                patterns = self._extract_patterns(f"{title} {text_box}")

                self.raw_data.append({
                    "id": f"abierta-{id_moodle}",
                    "titulo": title,
                    "curso_padre": title,
                    "bloque_web": "Formación Abierta",
                    "categoria": name_category,
                    "modalidad": patterns["modalidad"],
                    "edicion": patterns["edicion"],
                    "estado": patterns["estado"] or "Catálogo Histórico",
                    "fechas": patterns["fechas"],
                    "duracion": patterns["duracion"],
                    "competencias": patterns["competencias"],
                    "num_secciones": len(box.select(".content, .summary, p")),
                    "num_recursos_": len(box.select("p, div")),
                    "num_elementos_lista": len(box.select("li")),
                    "num_enlaces": len(box.select("a")),
                    "num_imagenes": len(box.select("img")),
                    "longitud_texto": len(text_box),
                    "extracto_texto": text_box[:400],
                    "url_origen": url_course
                })
                print(f"Open Training Captured: {title[:52]}...")

    def _expand_info_ajax_moodle(self) -> None:
        """
        Expand subcategories and click the information messages to retrieve the data.
        """
        try:
            buttons_exp = self.driver.find_elements(By.CSS_SELECTOR, ".collapseexpand, .category.notloaded a")
            for b in buttons_exp[:8]:
                try:
                    self.driver.execute_script("arguments[0].click();", b)
                except Exception:
                    pass
            safety_pause(1.0, 1.5)

            icons = self.driver.find_elements(By.CSS_SELECTOR, ".coursebox .moreinfo a")
            if icons:
                for icon in icons:
                    try:
                        self.driver.execute_script("arguments[0].click();", icon)
                    except Exception:
                        pass
                safety_pause(2.5, 4.0)
        except Exception:
            pass

    def _expand_tabs_scroll(self) -> None:
        """Click the front page filters and scroll through the entire page."""
        try:
            for b in self.driver.find_elements(By.CSS_SELECTOR, "button, .nav-link")[:10]:
                if any(w in (b.text or "").lower() for w in ["finalizado", "todos", "más"]):
                    self.driver.execute_script("arguments[0].click();", b)
                    safety_pause(0.5, 1.0)
        except Exception:
            pass
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        safety_pause(1.0, 1.5)

    # =========================================================================
    # BLOQUE 2: AULA EN ABIERTO (/aulaenabierto/)
    # =========================================================================

    def extraer_bloque_aula_en_abierto(self) -> None:
        """Recorre las categorías de Aula en Abierto y extrae Cursos, Secciones y Recursos Didácticos."""
        ruta_indice = "/aulaenabierto/course/index.php"
        if not verificar_robots_txt(self.base_url, ruta_indice, self.user_agent):
            return

        url_inicio = f"{self.base_url}{ruta_indice}"
        print(f"\n[*] Explorando Bloque 2 (Aula en Abierto): {url_inicio}")
        self.driver.get(url_inicio)
        pausa_responsable(2.0, 3.0)

        enlaces_cat = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='categoryid=']")
        categorias = []
        for elem in enlaces_cat:
            href = elem.get_attribute("href")
            nombre = elem.text.strip()
            if href and href not in [c[0] for c in categorias]:
                sep = "&" if "?" in href else "?"
                categorias.append((f"{href}{sep}perpage=100", nombre))

        cursos_visitados = set()

        for url_cat, nombre_cat in categorias:
            print(f"  -> Explorando categoría: {nombre_cat}")
            self.driver.get(url_cat)
            pausa_responsable(1.5, 2.5)

            soup_cat = BeautifulSoup(self.driver.page_source, "html.parser")
            for a in soup_cat.select("a[href*='course/view.php?id=']"):
                url_curso = a["href"].split("#")[0]
                titulo_crudo = a.get_text(" ", strip=True)

                if url_curso in cursos_visitados or not titulo_crudo:
                    continue
                cursos_visitados.add(url_curso)

                self._extraer_interior_aula_abierto(url_curso, titulo_crudo, nombre_cat)

    def _extraer_interior_aula_abierto(self, url_curso: str, titulo_curso: str, categoria_cruda: str) -> None:
        """Extrae el curso, lee su página de Guía/Introducción si existe, y extrae sus secciones y recursos."""
        print(f"    -> [Aula Abierto] Analizando curso y recursos: {titulo_curso[:50]}...")
        try:
            self.driver.get(url_curso)
            pausa_responsable(1.2, 2.0)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            main_node = soup.select_one("#region-main, .course-content") or soup
            self._limpiar_ruido_dom(main_node)

            texto_curso = main_node.get_text(" ", strip=True)
            id_match = re.search(r"id=(\d+)", url_curso)
            id_curso = f"aula-{id_match.group(1)}" if id_match else f"aula-{len(self.registros_crudos)}"

            secciones = main_node.select("li.section.main, .course-section")
            libros_paginas = main_node.select("a[href*='mod/book/'], a[href*='mod/page/']")
            actividades_todas = main_node.select("li.activity")

            # Si el curso tiene una página de 'Guía', 'Información básica' o 'Introducción', la leemos para enriquecer el texto
            texto_guia_extra = ""
            for enlace_guia in libros_paginas[:2]:
                nombre_enlace = enlace_guia.get_text(" ", strip=True).lower()
                if any(p in nombre_enlace for p in ["guía", "información", "introducción", "presentación", "créditos"]):
                    texto_guia_extra = self._leer_subpagina_guia(enlace_guia.get("href", ""))
                    if texto_guia_extra:
                        break

            texto_combinado = f"{titulo_curso} {texto_curso} {texto_guia_extra}".strip()
            patrones = self._extraer_patrones_crudos(texto_combinado)

            # 1. Registro del Curso Completo
            self.registros_crudos.append({
                "id_elemento": id_curso,
                "titulo_crudo": titulo_curso,
                "curso_padre_crudo": titulo_curso,
                "bloque_web": "Aula en Abierto",
                "nivel_granularidad": "Curso Completo",
                "categoria_cruda": categoria_cruda,
                "modalidad_cruda": patrones["modalidad_cruda"] or "Curso",
                "edicion_cruda": patrones["edicion_cruda"],
                "estado_crudo": "Abierto Permanente",
                "fechas_texto_crudo": patrones["fechas_crudo"],
                "duracion_texto_crudo": patrones["duracion_cruda"],
                "competencias_texto_crudo": patrones["competencias_crudo"],
                "num_secciones_o_temas": len(secciones),
                "num_recursos_libros_paginas": len(libros_paginas),
                "num_items_lista": len(actividades_todas) or len(main_node.select("li")),
                "num_enlaces": len(main_node.select("a")),
                "num_imagenes": len(main_node.select("img")),
                "longitud_texto_chars": len(texto_combinado),
                "extracto_texto_crudo": (texto_guia_extra or texto_curso)[:400],
                "url_origen": url_curso
            })

            # 2. Registros de cada Sección / Unidad Didáctica y sus Recursos principales
            for sec in secciones:
                titulo_sec_node = sec.select_one(".sectionname, h3, h4")
                titulo_sec = titulo_sec_node.get_text(" ", strip=True) if titulo_sec_node else None
                texto_sec = sec.get_text(" ", strip=True)

                if not titulo_sec or len(texto_sec) < 30:
                    continue

                patrones_sec = self._extraer_patrones_crudos(f"{titulo_sec} {texto_sec}")
                libros_sec = sec.select("a[href*='mod/book/'], a[href*='mod/page/']")

                self.registros_crudos.append({
                    "id_elemento": f"{id_curso}-{sec.get('id', 'sec')}",
                    "titulo_crudo": titulo_sec,
                    "curso_padre_crudo": titulo_curso,
                    "bloque_web": "Aula en Abierto",
                    "nivel_granularidad": "Módulo / Sección",
                    "categoria_cruda": categoria_cruda,
                    "modalidad_cruda": patrones["modalidad_cruda"] or "Curso",
                    "edicion_cruda": patrones["edicion_cruda"],
                    "estado_crudo": "Módulo Activo",
                    "fechas_texto_crudo": patrones_sec["fechas_crudo"] or patrones["fechas_crudo"],
                    "duracion_texto_crudo": patrones_sec["duracion_cruda"] or patrones["duracion_cruda"],
                    "competencias_texto_crudo": patrones_sec["competencias_crudo"] or patrones["competencias_crudo"],
                    "num_secciones_o_temas": 1,
                    "num_recursos_libros_paginas": len(libros_sec),
                    "num_items_lista": len(sec.select("li.activity, li")),
                    "num_enlaces": len(sec.select("a")),
                    "num_imagenes": len(sec.select("img")),
                    "longitud_texto_chars": len(texto_sec),
                    "extracto_texto_crudo": texto_sec[:400],
                    "url_origen": f"{url_curso}#{sec.get('id', '')}"
                })

        except Exception as error:
            print(f"    [!] Error en {url_curso}: {error}")

    def _leer_subpagina_guia(self, url_guia: str) -> str:
        """Entra en la página de Guía/Introducción del curso para capturar horas, fechas y competencias reales."""
        if not url_guia or "formacion.intef.es" not in url_guia:
            return ""
        try:
            self.driver.get(url_guia)
            pausa_responsable(0.8, 1.4)
            soup_guia = BeautifulSoup(self.driver.page_source, "html.parser")
            main_guia = soup_guia.select_one("#region-main, .book_content, main") or soup_guia
            self._limpiar_ruido_dom(main_guia)
            return main_guia.get_text(" ", strip=True)
        except Exception:
            return ""

    def guardar_csv(self, ruta_salida: str) -> None:
        """Guarda los datos crudos en un archivo CSV."""
        carpeta = os.path.dirname(ruta_salida)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)

        df = pd.DataFrame(self.registros_crudos)
        df.to_csv(ruta_salida, index=False, encoding="utf-8")

        print(f"\n[OK] Dataset en crudo guardado en: {ruta_salida}")
        print(f"[OK] Dimensiones: {df.shape[0]} filas x {df.shape[1]} columnas")

    def cerrar(self) -> None:
        """Cierra el navegador."""
        if self.driver:
            self.driver.quit()
            print("[*] Navegador cerrado.")