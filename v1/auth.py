# v1/auth.py
import json
import ast
import requests

try:
    import settings
except ImportError:
    settings = None


def _parse_cookie_header_to_dict(s: str) -> dict:
    d = {}
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip().strip()
    return d


def _parse_any_cookies_value(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, str):
        r = raw.strip()
        if not r:
            return {}
        # Try JSON object
        if r.startswith("{") and r.endswith("}"):
            try:
                obj = json.loads(r)
                if isinstance(obj, dict):
                    return {str(k): str(v) for k, v in obj.items()}
            except Exception:
                pass
            try:
                obj = ast.literal_eval(r)
                if isinstance(obj, dict):
                    return {str(k): str(v) for k, v in obj.items()}
            except Exception:
                pass
        # Try Python dict literal
        try:
            obj = ast.literal_eval(r)
            if isinstance(obj, dict):
                return {str(k): str(v) for k, v in obj.items()}
        except Exception:
            pass
        # Fallback: assume Cookie header string "k=v; k2=v2"
        return _parse_cookie_header_to_dict(r)
    return {}


def load_credentials() -> dict:
    cookies_source = getattr(settings, "COOKIES", {}) if settings else {}
    creds = _parse_any_cookies_value(cookies_source)
    return creds


def build_cookie_header(creds: dict) -> str:
    parts = []
    for k, v in creds.items():
        if v is None:
            continue
        parts.append(f"{k}={v}")
    return "; ".join(parts)


def build_headers() -> dict:
    creds = load_credentials()
    cookie = build_cookie_header(creds) if creds else ""
    headers = {
        "authority": "www.instagram.com",
        "accept": "*/*",
        "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "x-fb-friendly-name": "PolarisProfilePostsQuery",
    }
    if cookie:
        headers["cookie"] = cookie
    if "csrftoken" in creds:
        headers["x-csrftoken"] = creds["csrftoken"]

    # Merge optional extras from settings.HEADERS
    extras = getattr(settings, "HEADERS", {}) if settings else {}
    if isinstance(extras, dict):
        for k, v in extras.items():
            headers[str(k)] = str(v)
    return headers


def build_session_and_headers(username: str) -> tuple[requests.Session, dict]:
    creds = load_credentials()
    s = requests.Session()
    for k, v in creds.items():
        if v is not None:
            s.cookies.set(k, v)

    headers = build_headers()
    # Ensure a sensible referer if not provided in settings.HEADERS
    headers.setdefault("referer", f"https://www.instagram.com/{username}/")
    return s, headers