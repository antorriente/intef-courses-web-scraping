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
        state = re.search(r"\b(Finalizado|En curso|Abierto|Próximamente)\b", text, re.IGNORECASE)

        return {
            "modalidad": format.group(0) if format else None,
            "edicion": edition.group(0) if edition else None,
            "estado": state.group(0) if state else None,
            "fechas": " | ".join(dict.fromkeys(dates)) if dates else None,
            "duracion": hours.group(0) if hours else None,
            "competencias": ", ".join(dict.fromkeys(skills)) if skills else None
        }

    ##########################################
    ### Block 1: Open Training (/abierta/) ###
    ##########################################

    def extract_open_training(self) -> None:
        """
        Extract data from Open Training courses.
        """
        if not verify_robots_txt(self.base_url, "/abierta/", self.user_agent):
            return

        titles = set()

        # 1. Front Page
        url_front = f"{self.base_url}/abierta/"
        print(f"Exploring Block 1 Front Page.: {url_front}")
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
                "texto": text[:100000],
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
                    "bloque_web": "Formación Abierta",
                    "categoria": name_category,
                    "modalidad": patterns["modalidad"],
                    "edicion": patterns["edicion"],
                    "estado": patterns["estado"] or "Catálogo Histórico",
                    "fechas": patterns["fechas"],
                    "duracion": patterns["duracion"],
                    "competencias": patterns["competencias"],
                    "num_secciones": len(box.select(".content, .summary, p")),
                    "num_recursos": len(box.select("p, div")),
                    "num_elementos_lista": len(box.select("li")),
                    "num_enlaces": len(box.select("a")),
                    "num_imagenes": len(box.select("img")),
                    "longitud_texto": len(text_box),
                    "texto": text_box[:100000],
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

    ###########################################
    ### Block 2: Open Classroom (/abierta/) ###
    ###########################################

    def extract_open_classroom(self) -> None:
        """
        Extract courses, sections and teaching resources from Open Classroom categories.
        """
        path_index = "/aulaenabierto/course/index.php"
        if not verify_robots_txt(self.base_url, path_index, self.user_agent):
            return

        url_start = f"{self.base_url}{path_index}"
        print(f"Exploring Block 2 Open Classroom: {url_start}")
        self.driver.get(url_start)
        safety_pause(2.0, 3.0)

        links_category = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='categoryid=']")
        categories = []
        for elem in links_category:
            href = elem.get_attribute("href")
            name = elem.text.strip()
            if href and href not in [c[0] for c in categories]:
                sep = "&" if "?" in href else "?"
                categories.append((f"{href}{sep}perpage=100", name))

        courses = set()

        for url_category, name_category in categories:
            print(f"Exploring Category: {name_category}")
            self.driver.get(url_category)
            safety_pause(1.5, 2.5)

            soup_category = BeautifulSoup(self.driver.page_source, "html.parser")
            for a in soup_category.select("a[href*='course/view.php?id=']"):
                url_course = a["href"].split("#")[0]
                title = a.get_text(" ", strip=True)

                if url_course in courses or not title:
                    continue
                courses.add(url_course)

                self._extract_inside_open_classroom(url_course, title, name_category)

    def _extract_inside_open_classroom(self, url_course: str, title_course: str, category: str) -> None:
        """
        Extract courses, sections and resources.
        """
        print(f"Analizing Courses and Resources: {title_course[:50]}...")
        try:
            self.driver.get(url_course)
            safety_pause(1.2, 2.0)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            main_node = soup.select_one("#region-main, .course-content") or soup
            self._clean_noise_dom(main_node)

            text_course = main_node.get_text(" ", strip=True)
            id_match = re.search(r"id=(\d+)", url_course)
            id_course = f"aula-{id_match.group(1)}" if id_match else f"aula-{len(self.raw_data)}"

            sections = main_node.select("li.section.main, .course-section")
            books_pages = main_node.select("a[href*='mod/book/'], a[href*='mod/page/']")
            activities = main_node.select("li.activity")

            # Read course pages to add the information to the dataset.
            extra_text = ""
            for link_guide in books_pages[:2]:
                name_link = link_guide.get_text(" ", strip=True).lower()
                if any(p in name_link for p in ["guía", "información", "introducción", "presentación", "créditos"]):
                    extra_text = self._read_subpage_guide(link_guide.get("href", ""))
                    if extra_text:
                        break

            combined_text = f"{title_course} {text_course} {extra_text}".strip()
            patterns = self._extract_patterns(combined_text)

            # 1. Full Course Register
            self.raw_data.append({
                "id": id_course,
                "titulo": title_course,
                "bloque_web": "Aula en Abierto",
                "categoria": category,
                "modalidad": patterns["modalidad"] or "Curso",
                "edicion": patterns["edicion"],
                "estado": "Abierto Permanente",
                "fechas": patterns["fechas"],
                "duracion": patterns["duracion"],
                "competencias": patterns["competencias"],
                "num_secciones": len(sections),
                "num_recursos": len(books_pages),
                "num_elementos_lista": len(activities) or len(main_node.select("li")),
                "num_enlaces": len(main_node.select("a")),
                "num_imagenes": len(main_node.select("img")),
                "longitud_texto": len(combined_text),
                "texto": (extra_text or text_course)[:100000],
                "url_origen": url_course
            })

            # 2. Registers for each section and their main resources.
            for sec in sections:
                title_sec_node = sec.select_one(".sectionname, h3, h4")
                title_sec = title_sec_node.get_text(" ", strip=True) if title_sec_node else None
                text_sec = sec.get_text(" ", strip=True)

                if not title_sec_node or len(text_sec) < 30:
                    continue

                patterns_sec = self._extract_patterns(f"{title_sec} {text_sec}")
                books_sec = sec.select("a[href*='mod/book/'], a[href*='mod/page/']")

                self.raw_data.append({
                    "id": f"{id_course}-{sec.get('id', 'sec')}",
                    "titulo": title_sec,
                    "bloque_web": "Aula en Abierto",
                    "categoria": category,
                    "modalidad": patterns["modalidad"] or "Curso",
                    "edicion": patterns["edicion"],
                    "estado": "Módulo Activo",
                    "fechas": patterns_sec["fechas"] or patterns["fechas"],
                    "duracion": patterns_sec["duracion"] or patterns["duracion"],
                    "competencias": patterns_sec["competencias"] or patterns["competencias"],
                    "num_secciones": 1,
                    "num_recursos": len(books_sec),
                    "num_elementos_lista": len(sec.select("li.activity, li")),
                    "num_enlaces": len(sec.select("a")),
                    "num_imagenes": len(sec.select("img")),
                    "longitud_texto": len(text_sec),
                    "texto": text_sec[:100000],
                    "url_origen": f"{url_course}#{sec.get('id', '')}"
                })

        except Exception as error:
            print(f"Error in {url_course}: {error}")

    def _read_subpage_guide(self, url_guide: str) -> str:
        """
        Extract actual hours, dates and skills from the Guide/Introduction page of each course.
        """
        if not url_guide or "formacion.intef.es" not in url_guide:
            return ""
        try:
            self.driver.get(url_guide)
            safety_pause(0.8, 1.4)
            soup_guide = BeautifulSoup(self.driver.page_source, "html.parser")
            main_guide = soup_guide.select_one("#region-main, .book_content, main") or soup_guide
            self._clean_noise_dom(main_guide)
            return main_guide.get_text(" ", strip=True)
        except Exception:
            return ""

    def save_dataset(self, output_path: str) -> None:
        """
        Save the final dataset as a CSV file.
        """
        folder = os.path.dirname(output_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        df = pd.DataFrame(self.raw_data)
        df.to_csv(output_path, index=False, encoding="utf-8")

        print(f"Dataset Saved: {output_path}")
        print(f"Dimensions: {df.shape[0]} rows x {df.shape[1]} columns")

    def close(self) -> None:
        """
        Close browser.
        """
        if self.driver:
            self.driver.quit()
            print("Browser Closed")