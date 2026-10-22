import argparse
import time
from intef_scraper import IntefScraper


def args_config():
    parser = argparse.ArgumentParser(
        description="Scraper of INTEF Courses"
    )
    parser.add_argument(
        "--headless",
        action="store_true"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="csv/intef_courses.csv"
    )
    return parser.parse_args()


def main():
    args = args_config()

    start = time.time()
    print("-" * 70)
    print(" WEB SCRAPER: INTEF TRAINING COURSES ")
    print("-" * 70)

    scraper = IntefScraper(headless=args.headless)

    scraper.extract_open_training()
    scraper.extract_open_classroom()
    scraper.save_dataset(output_path=args.output)
    scraper.close()

    total_time = round(time.time() - start, 2)
    print("-" * 70)
    print(f" PROCESS COMPLETED IN {total_time} SECONDS ")
    print("-" * 70)


if __name__ == "__main__":
    main()