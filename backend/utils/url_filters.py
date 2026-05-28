from urllib.parse import urlparse


LOW_VALUE_HOSTS = {
    "apps.shopify.com",
    "shopify.dev",
    "hydrogen.shopify.dev",
    "shopifyacademy.com",
    "www.shopifyacademy.com",
}

LOW_VALUE_PATH_PREFIXES = (
    "/docs",
    "/editions",
)


def is_low_value_url(url: str) -> bool:
    """Return True for URLs that are likely noise for company research."""
    if not url:
        return False

    parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if host in LOW_VALUE_HOSTS:
        return True

    if host.endswith(".shopify.dev"):
        return True

    return path.startswith(LOW_VALUE_PATH_PREFIXES)