import ssl
import time
import random
import urllib.robotparser
import urllib.request
from urllib.error import URLError, HTTPError


def verify_robots_txt(base_url: str, path: str, user_agent: str) -> bool:
    """
    Verify whether the robots.txt file allows the specified path to be crawled.
    """
    robots_url = f"{base_url.rstrip('/')}/robots.txt"
    target_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    parser = urllib.robotparser.RobotFileParser()

    print(f"Verifying robots.txt from: {robots_url}")

    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        request = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=10, context=ssl_context) as answer:
            content_type = answer.headers.get("Content-Type", "").lower()
            text = answer.read().decode("utf-8", errors="ignore")

            if "text/html" in content_type or "<html" in text.lower():
                print("The robots.txt file does not exist (returns HTML instead). Crawling is allowed.")
                return True

            parser.parse(text.splitlines())
            allowed = parser.can_fetch(user_agent, target_url)
            print(f"Access according to robots.txt for '{path}': {allowed}")
            return allowed

    except HTTPError as error:
        if error.code in (301, 302, 303, 404):
            print(f"No restrictions in robots.txt (HTTP {error.code}). Crawling is allowed.")
            return True
        print(f"HTTP Error {error.code} verifying robots.txt.")
        return False

    except URLError as error:
        print(f"Network warning ({error}). Proceeding with caution..")
        return True


def safety_pause(min_sec: float = 1.5, max_sec: float = 3.0) -> None:
    """
    Safety pause to avoid overloading the server.
    """
    time.sleep(random.uniform(min_sec, max_sec))