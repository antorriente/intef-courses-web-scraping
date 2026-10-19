import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from utils import verificar_robots_txt, pausa_responsable


class IntefScraper:
    """Extrae en crudo (raw data) el catálogo completo de Formación Abierta y Aula en Abierto."""

    def __init__(self, headless: bool = False):
        self.url_base = "https://formacion.intef.es"
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36 (UOC-DataScience-Scraper/1.0)"
        )
        self.driver = self._configurar_driver(headless)
        self.registros_crudos = []

    def _configurar_driver(self, headless: bool) -> webdriver.Chrome:
        """Arranca Chrome y verifica el User-Agent desde el navegador."""
        opciones = Options()
        if headless:
            opciones.add_argument("--headless=new")

        opciones.add_argument(f"user-agent={self.user_agent}")
        opciones.add_argument("--window-size=1920,1080")
        opciones.add_argument("--disable-gpu")
        opciones.add_argument("--no-sandbox")
        opciones.add_argument("--log-level=3")
        opciones.add_argument("--disable-background-networking")
        opciones.add_experimental_option("excludeSwitches", ["enable-logging"])

        servicio = Service(ChromeDriverManager().install(), log_output=os.devnull)
        driver = webdriver.Chrome(service=servicio, options=opciones)

        ua_navegador = driver.execute_script("return navigator.userAgent;")
        print(f"[*] WebDriver iniciado. User-Agent activo: {ua_navegador}\n")
        return driver

    def _limpiar_ruido_dom(self, soup_node) -> None:
        """Elimina etiquetas invisibles de sistema (<noscript>, <script>, botones de cerrar) antes de leer."""
        for tag in soup_node.select("noscript, script, style, button.close, .sr-only, .accesshide"):
            tag.decompose()

    def _extraer_patrones_crudos(self, texto: str) -> dict:
        """Extrae menciones en bruto de fechas, horas, ediciones y competencias presentes en el texto."""
        fechas = re.findall(
            r"\d{1,2}\s+(?:de\s+)?[a-zA-Záéíóú]{3,12}[\s,]+\d{4}|\d{2}/\d{2}/\d{4}"
            r"|(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{4}",
            texto, re.IGNORECASE
        )
        horas = re.search(r"\d{1,3}\s*(?:horas|h\b)", texto, re.IGNORECASE)
        edicion = re.search(r"\d+\s*(?:ª|\.|a)?\s*edici[óo]n|\d+ª\s*Conv_\d{4}", texto, re.IGNORECASE)
        modalidad = re.search(r"\b(MOOC|NOOC|SPOOC|Curso)\b", texto, re.IGNORECASE)
        competencias = re.findall(r"(?:[ÁA]rea\s*\d|[1-6]\.[1-5]|\b[ABC][12]\b)", texto)
        estado = re.search(r"\b(Finalizado|En curso|Abierto|Próximamente)\b", texto, re.IGNORECASE)

        return {
            "modalidad_cruda": modalidad.group(0) if modalidad else None,
            "edicion_cruda": edicion.group(0) if edicion else None,
            "estado_crudo": estado.group(0) if estado else None,
            "fechas_crudo": " | ".join(dict.fromkeys(fechas)) if fechas else None,
            "duracion_cruda": horas.group(0) if horas else None,
            "competencias_crudo": ", ".join(dict.fromkeys(competencias)) if competencias else None
        }

    # =========================================================================
    # BLOQUE 1: FORMACIÓN ABIERTA (/abierta/)
    # =========================================================================

    def extraer_bloque_abierta(self) -> None:
        """Extrae las fichas modales de portada y todas las categorías de /abierta/course/index.php."""
        if not verificar_robots_txt(self.url_base, "/abierta/", self.user_agent):
            return

        titulos_vistos = set()

        # 1. Portada de Formación Abierta (Modales completos)
        url_portada = f"{self.url_base}/abierta/"
        print(f"[*] Explorando portada de Bloque 1: {url_portada}")
        self.driver.get(url_portada)
        pausa_responsable(2.0, 3.0)
        self._desplegar_pestanas_y_scroll()

        soup_portada = BeautifulSoup(self.driver.page_source, "html.parser")
        for modal in soup_portada.select(".modal-content"):
            titulo_nodo = modal.select_one(".modal-title, h3, h4")
            if not titulo_nodo:
                continue
            titulo = titulo_nodo.get_text(" ", strip=True)
            if len(titulo) < 6 or titulo in titulos_vistos:
                continue
            titulos_vistos.add(titulo)

            self._limpiar_ruido_dom(modal)
            texto = modal.get_text(" ", strip=True)
            patrones = self._extraer_patrones_crudos(f"{titulo} {texto}")

            self.registros_crudos.append({
                "id_elemento": modal.get("id") or f"abierta-modal-{len(self.registros_crudos) + 1}",
                "titulo_crudo": titulo,
                "curso_padre_crudo": titulo,
                "bloque_web": "Formación Abierta",
                "nivel_granularidad": "Curso Completo (Modal)",
                "categoria_cruda": "Catálogo Portada Abierta",
                "modalidad_cruda": patrones["modalidad_cruda"],
                "edicion_cruda": patrones["edicion_cruda"],
                "estado_crudo": patrones["estado_crudo"] or "Publicado en Portada",
                "fechas_texto_crudo": patrones["fechas_crudo"],
                "duracion_texto_crudo": patrones["duracion_cruda"],
                "competencias_texto_crudo": patrones["competencias_crudo"],
                "num_secciones_o_temas": len(modal.select("h4, h5, strong")),
                "num_recursos_libros_paginas": len(modal.select("p")),
                "num_items_lista": len(modal.select("li")),
                "num_enlaces": len(modal.select("a")),
                "num_imagenes": len(modal.select("img")),
                "longitud_texto_chars": len(texto),
                "extracto_texto_crudo": texto[:400],
                "url_origen": url_portada
            })
            print(f"    -> [Abierta Modal] Capturado: {titulo[:55]}...")

        # 2. Árbol de categorías de /abierta/course/index.php (MOOC, NOOC, SPOOC, Ediciones anteriores)
        url_indice = f"{self.url_base}/abierta/course/index.php"
        print(f"[*] Descubriendo categorías en: {url_indice}")
        self.driver.get(url_indice)
        pausa_responsable(2.0, 3.0)

        soup_indice = BeautifulSoup(self.driver.page_source, "html.parser")
        urls_categorias = [(f"{url_indice}?perpage=100", "Índice General Abierta")]

        for a_cat in soup_indice.select("a[href*='categoryid=']"):
            href = a_cat.get("href", "")
            nombre_cat = a_cat.get_text(" ", strip=True) or "Categoría Abierta"
            if href.startswith("/"):
                href = f"{self.url_base}{href}"
            if href and "formacion.intef.es" in href:
                sep = "&" if "?" in href else "?"
                url_cat_100 = f"{href}{sep}perpage=100"
                if url_cat_100 not in [c[0] for c in urls_categorias]:
                    urls_categorias.append((url_cat_100, nombre_cat))

        for url_cat, nombre_cat in urls_categorias:
            print(f"  -> Explorando categoría Abierta: {nombre_cat}")
            self.driver.get(url_cat)
            pausa_responsable(1.5, 2.5)

            # Desplegamos subcategorías colapsadas y todos los iconos 'i' (.moreinfo a) con AJAX
            self._desplegar_info_ajax_moodle()
            soup_cat = BeautifulSoup(self.driver.page_source, "html.parser")

            # Si al expandir aparecen nuevas subcategorías, las añadimos a la cola
            for sub_a in soup_cat.select("a[href*='categoryid=']"):
                sub_href = sub_a.get("href", "")
                if sub_href.startswith("/"):
                    sub_href = f"{self.url_base}{sub_href}"
                sep = "&" if "?" in sub_href else "?"
                sub_url_100 = f"{sub_href}{sep}perpage=100"
                if "formacion.intef.es" in sub_url_100 and sub_url_100 not in [c[0] for c in urls_categorias]:
                    urls_categorias.append((sub_url_100, sub_a.get_text(" ", strip=True) or nombre_cat))

            for box in soup_cat.select(".coursebox"):
                enlace = box.select_one(".coursename a")
                if not enlace:
                    continue
                titulo = enlace.get_text(" ", strip=True)
                if titulo in titulos_vistos:
                    continue
                titulos_vistos.add(titulo)

                self._limpiar_ruido_dom(box)
                url_curso = enlace.get("href", url_cat)
                id_moodle = box.get("data-courseid") or "s/n"
                texto_box = box.get_text(" ", strip=True)
                patrones = self._extraer_patrones_crudos(f"{titulo} {texto_box}")

                self.registros_crudos.append({
                    "id_elemento": f"abierta-{id_moodle}",
                    "titulo_crudo": titulo,
                    "curso_padre_crudo": titulo,
                    "bloque_web": "Formación Abierta",
                    "nivel_granularidad": "Curso Completo (Catálogo)",
                    "categoria_cruda": nombre_cat,
                    "modalidad_cruda": patrones["modalidad_cruda"],
                    "edicion_cruda": patrones["edicion_cruda"],
                    "estado_crudo": patrones["estado_crudo"] or "Catálogo Histórico",
                    "fechas_texto_crudo": patrones["fechas_crudo"],
                    "duracion_texto_crudo": patrones["duracion_cruda"],
                    "competencias_texto_crudo": patrones["competencias_crudo"],
                    "num_secciones_o_temas": len(box.select(".content, .summary, p")),
                    "num_recursos_libros_paginas": len(box.select("p, div")),
                    "num_items_lista": len(box.select("li")),
                    "num_enlaces": len(box.select("a")),
                    "num_imagenes": len(box.select("img")),
                    "longitud_texto_chars": len(texto_box),
                    "extracto_texto_crudo": texto_box[:400],
                    "url_origen": url_curso
                })
                print(f"    -> [Abierta Catálogo] Capturado: {titulo[:52]} ({len(texto_box)} chars)")

    def _desplegar_info_ajax_moodle(self) -> None:
        """Expande subcategorías y clica en los iconos .moreinfo para que Moodle inyecte las descripciones."""
        try:
            botones_exp = self.driver.find_elements(By.CSS_SELECTOR, ".collapseexpand, .category.notloaded a")
            for b in botones_exp[:8]:
                try:
                    self.driver.execute_script("arguments[0].click();", b)
                except Exception:
                    pass
            pausa_responsable(1.0, 1.5)

            iconos = self.driver.find_elements(By.CSS_SELECTOR, ".coursebox .moreinfo a")
            if iconos:
                for icono in iconos:
                    try:
                        self.driver.execute_script("arguments[0].click();", icono)
                    except Exception:
                        pass
                pausa_responsable(2.5, 4.0)
        except Exception:
            pass

    def _desplegar_pestanas_y_scroll(self) -> None:
        """Clica en filtros de portada y hace scroll completo."""
        try:
            for b in self.driver.find_elements(By.CSS_SELECTOR, "button, .nav-link")[:10]:
                if any(w in (b.text or "").lower() for w in ["finalizado", "todos", "más"]):
                    self.driver.execute_script("arguments[0].click();", b)
                    pausa_responsable(0.5, 1.0)
        except Exception:
            pass
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        pausa_responsable(1.0, 1.5)

    # =========================================================================
    # BLOQUE 2: AULA EN ABIERTO (/aulaenabierto/)
    # =========================================================================

    def extraer_bloque_aula_en_abierto(self) -> None:
        """Recorre las categorías de Aula en Abierto y extrae Cursos, Secciones y Recursos Didácticos."""
        ruta_indice = "/aulaenabierto/course/index.php"
        if not verificar_robots_txt(self.url_base, ruta_indice, self.user_agent):
            return

        url_inicio = f"{self.url_base}{ruta_indice}"
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