import argparse
import time
from intef_scraper import IntefScraper


def configurar_argumentos():
    """Define los parámetros configurables por consola."""
    parser = argparse.ArgumentParser(
        description="Scraper de cursos formativos del INTEF - Práctica 1 UOC (M2.851)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecuta el navegador en modo oculto (sin interfaz gráfica)."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="dataset/cursos_intef_raw.csv",
        help="Ruta donde se guardará el fichero CSV resultante."
    )
    return parser.parse_args()


def main():
    args = configurar_argumentos()
    inicio = time.time()

    print("=" * 70)
    print(" WEB SCRAPER: CATÁLOGO DE FORMACIÓN DOCENTE INTEF (UOC M2.851)")
    print("=" * 70)

    scraper = IntefScraper(headless=args.headless)
    try:
        # 1. Bloque 1: Formación Abierta (MOOC, NOOC, SPOOC)
        scraper.extraer_bloque_abierta()

        # 2. Bloque 2: Aula en Abierto (Cursos Tutorizados en Abierto)
        scraper.extraer_bloque_aula_en_abierto()

        # 3. Exportación del dataset resultante en /dataset
        scraper.guardar_csv(ruta_salida=args.output)

    except KeyboardInterrupt:
        print("\n[!] Proceso detenido manualmente por el usuario.")
    finally:
        scraper.cerrar()

    tiempo_total = round(time.time() - inicio, 2)
    print("=" * 70)
    print(f" EXTRACCIÓN COMPLETADA EN {tiempo_total} SEGUNDOS")
    print("=" * 70)


if __name__ == "__main__":
    main()