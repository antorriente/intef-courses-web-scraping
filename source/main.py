import argparse
import time
from intef_scraper import IntefScraper


def args_config():
    parser = argparse.ArgumentParser(
        description="Scraper de Cursos Formativos del INTEF"
    )
    parser.add_argument(
        "--headless",
        action="store_true"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="dataset/formacion_intef.csv"
    )
    return parser.parse_args()


def main():
    args = args_config()
    inicio = time.time()

    print("-" * 70)
    print(" WEB SCRAPER: CURSOS FORMATIVOS INTEF")
    print("-" * 70)

    scraper = IntefScraper(headless=args.headless)
    try:
        # Bloque 1: Formación Abierta (MOOC, NOOC, SPOOC)
        scraper.extraer_bloque_abierta()

        # Bloque 2: Aula en Abierto (Cursos Tutorizados en Abierto)
        scraper.extraer_bloque_aula_en_abierto()

        # Exportar del dataset
        scraper.guardar_csv(ruta_salida=args.output)

    except KeyboardInterrupt:
        print("\n Process stopped by the user.")
    finally:
        scraper.cerrar()

    tiempo_total = round(time.time() - inicio, 2)
    print("-" * 70)
    print(f" EXTRACCIÓN COMPLETADA EN {tiempo_total} SEGUNDOS")
    print("-" * 70)


if __name__ == "__main__":
    main()