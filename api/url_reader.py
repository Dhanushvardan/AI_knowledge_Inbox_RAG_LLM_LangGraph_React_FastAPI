
import httpx
import re
import ipaddress
import socket

from urllib.parse import urlparse
from bs4 import BeautifulSoup


def validate_url(url: str):

    url = url.strip().rstrip(".,;!?)\"]}")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    if not parsed.hostname:
        raise ValueError("Invalid URL")

    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80)
        )

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])

            if not ip.is_global:
                raise ValueError("Private or restricted URL")

    except socket.gaierror:
        raise ValueError("Website domain could not be resolved")

    return url


async def extract_url_content(url: str):

    try:

        url = validate_url(url)

        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml"
            }
        ) as client:

            response = await client.get(url)

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type", ""
            )

            if "text/html" not in content_type.lower():
                raise ValueError("URL does not contain an HTML webpage")

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            # Remove unnecessary elements
            for tag in soup([
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "noscript",
                "iframe",
                "svg"
            ]):
                tag.decompose()

            # Extract page title
            title = (
                soup.title.get_text(strip=True)
                if soup.title else "No title found"
            )

            # Extract webpage content
            content = soup.get_text(
                separator=" ",
                strip=True
            )

            # Clean extra spaces
            content = re.sub(
                r"\s+",
                " ",
                content
            )

            if not content:
                raise ValueError("No readable webpage content found")

            return {
                "url": str(response.url),
                "title": title,
                "content": content[:15000],
                "success": True
            }

    except Exception as e:

        print("URL extraction error:", str(e))

        return {
            "url": url,
            "title": "",
            "content": "",
            "success": False,
            "error": str(e)
        }
