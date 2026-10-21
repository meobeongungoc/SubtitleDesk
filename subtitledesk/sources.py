"""Adapters for the two sites chosen by the user. No built-in credentials."""
import json
from pathlib import PurePosixPath
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

from .providers import Capabilities, Page, Result, SafeRedirect, validate_url, fetch_bytes
from .languages import LANGUAGES, normalize_language, subdl_code


class SourceError(Exception):
    """Contains only application-owned messages, never raw server errors."""


def error_text(exc):
    return str(exc) if isinstance(exc, SourceError) else type(exc).__name__


class Source:
    def __init__(self, secrets):
        self.secrets = secrets
        self.last_request = 0

    def key(self, field="api_key", required=True):
        value = self.secrets.get(self.capabilities.id, field).strip()
        if required and not value:
            raise SourceError(f"Missing {field}; enter it in Settings.")
        return value

    def request(self, url, context, headers, body=None):
        context.wait(max(0, self.last_request + 0.4 - time.monotonic()))
        self.last_request = time.monotonic()
        validate_url(url, self.api_domains)
        data = json.dumps(body).encode() if body is not None else None
        headers = {**headers, "Accept": "application/json", "User-Agent": "SubtitleDesk v0.2"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        # API redirects must stay on the same host; no credential-bearing cross-host requests.
        opener = urllib.request.build_opener(SafeRedirect((urlparse(url).hostname,)))
        try:
            with opener.open(urllib.request.Request(url, data=data, headers=headers),
                             timeout=max(.1, min(8, context.deadline - time.monotonic()))) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            context.check()
            if len(raw) > 4 * 1024 * 1024:
                raise SourceError("Provider response is too large.")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise SourceError("Invalid response format from provider.")
            return value
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            messages = {401: "Invalid API key or login.", 403: "Access denied; check the API key and account permissions.",
                        429: "Provider rate limit reached. Try again later.", 406: "Provider download quota exhausted.",
                        402: "Provider requires a different account permission or plan."}
            raise SourceError(messages.get(code, f"Source trả lỗi HTTP {code}.")) from None


class SubDL(Source):
    capabilities = Capabilities("subdl", "SubDL", languages=tuple(code for _, code in LANGUAGES if "," not in code), credentials=("api_key",), timeout=30,
                                domains=("api.subdl.com", "dl.subdl.com"))
    api_domains = ("api.subdl.com",)

    def search(self, query, cursor, context):
        movie = query.movie
        params = {"api_key": self.key(), "film_name": movie.title,
                  "languages": ",".join(subdl_code(v) for v in query.languages), "subs_per_page": 30,
                  "releases": 1, "hi": 1, "unpack": 1, "client": "custom_integration"}
        for key, value in (("year", movie.year), ("season_number", movie.season),
                           ("episode_number", movie.episode)):
            if value:
                params[key] = value
        if movie.season or movie.episode:
            params["type"] = "tv"
        data = self.request("https://api.subdl.com/api/v1/subtitles?" + urlencode(params), context, {})
        if data.get("status") is False:
            raise SourceError("SubDL rejected the request; check the API key or quota.")
        films = data.get("results") or []
        title = films[0].get("name", movie.title) if films else movie.title
        results = []
        for sub in data.get("subtitles") or []:
            for child in sub.get("unpack_files") or []:
                language = normalize_language(child.get("language"))
                if language not in query.languages:
                    continue
                child_url = urljoin("https://dl.subdl.com", child.get("url") or "")
                validate_url(child_url, ("dl.subdl.com",))
                child_url = urlunparse(urlparse(child_url)._replace(query="", fragment=""))
                child_name = PurePosixPath(str(child.get("name") or "").replace("\\", "/")).name
                if not child_name.lower().endswith((".srt", ".ass", ".ssa", ".vtt")):
                    continue
                results.append(Result("subdl", urlparse(child_url).path, str(title), language,
                    str(child.get("release_name") or child_name), str(sub.get("author") or ""),
                    "HI" if child.get("hi") else "", download_ref=child_url,
                    season=str(child["season"]) if child.get("season") is not None else "",
                    episode=str(child["episode"]) if child.get("episode") is not None else "", filename=child_name))
            url = urljoin("https://dl.subdl.com", sub.get("url") or "")
            validate_url(url, ("dl.subdl.com",))
            # SubDL can append the API key to response links. Keep it out of
            # result metadata, logs and reports; send it only as a header.
            url = urlunparse(urlparse(url)._replace(query="", fragment=""))
            if not urlparse(url).path.lower().endswith(".zip"):
                continue
            language = normalize_language(sub.get("lang") or sub.get("language"))
            if language not in query.languages:
                continue
            releases = sub.get("releases") or []
            release = sub.get("release_name") or (releases[0] if releases else "") or sub.get("name") or title
            pack = bool(sub.get("full_season")) or bool(sub.get("episode_end") and sub.get("episode_from")
                        and sub["episode_end"] != sub["episode_from"])
            results.append(Result("subdl", urlparse(url).path, str(title), language, str(release),
                                  str(sub.get("author") or ""), "HI" if sub.get("hi") else "",
                                  download_ref=url, season=str(sub["season"]) if sub.get("season") is not None else "",
                                  episode=str(sub["episode"]) if sub.get("episode") is not None else "", season_pack=pack))
        # v1 documents a maximum of 30 subtitles, but no cursor parameter.
        return Page(results)

    def download(self, result, context):
        validate_url(result.download_ref, ("dl.subdl.com",))
        data = fetch_bytes(result.download_ref, ("dl.subdl.com",), context,
                           headers={"x-api-key": self.key()})
        return result.filename or "subdl.zip", data


class OpenSubtitles(Source):
    capabilities = Capabilities("opensubtitles", "OpenSubtitles", languages=tuple(code for _, code in LANGUAGES if "," not in code), pagination=True,
                                credentials=("api_key", "username", "password"), timeout=30)
    api_domains = ("api.opensubtitles.com", "vip-api.opensubtitles.com")

    def search(self, query, cursor, context):
        movie = query.movie
        params = {"query": movie.title.lower(), "languages": ",".join(query.languages)}
        for key, value in (("year", movie.year), ("season_number", movie.season),
                           ("episode_number", movie.episode), ("page", cursor)):
            if value:
                params[key] = value
        data = self.request("https://api.opensubtitles.com/api/v1/subtitles?" + urlencode(sorted(params.items())),
                            context, {"Api-Key": self.key()})
        results = []
        for entry in data.get("data") or []:
            attrs = entry.get("attributes") or {}
            feature = attrs.get("feature_details") or {}
            language = str(attrs.get("language", "")).lower()
            if language not in query.languages:
                continue
            for file in attrs.get("files") or []:
                identifier = str(file.get("file_id", ""))
                if not identifier.isdecimal():
                    continue
                results.append(Result("opensubtitles", identifier,
                                      str(feature.get("parent_title") or feature.get("title") or movie.title),
                                      language, str(attrs.get("release") or file.get("file_name") or ""),
                                      str((attrs.get("uploader") or {}).get("name") or ""),
                                      "HI" if attrs.get("hearing_impaired") else "",
                                      season=str(feature.get("season_number") if feature.get("season_number") is not None else ""),
                                      episode=str(feature.get("episode_number") if feature.get("episode_number") is not None else ""),
                                      filename=PurePosixPath(str(file.get("file_name") or "").replace("\\", "/")).name))
        current = int(data.get("page") or cursor or 1)
        return Page(results, str(current + 1) if current < int(data.get("total_pages") or 1) else None)

    def download(self, result, context):
        headers = {"Api-Key": self.key()}
        username, password = self.key("username", False), self.key("password", False)
        if bool(username) != bool(password):
            raise SourceError("Enter both username and password, or leave both empty for anonymous downloads.")
        base = "https://api.opensubtitles.com/api/v1"
        if username:
            login = self.request(base + "/login", context, headers,
                                 {"username": username, "password": password})
            token = login.get("token")
            if not isinstance(token, str) or not token:
                raise SourceError("OpenSubtitles login failed.")
            headers["Authorization"] = "Bearer " + token
            host = login.get("base_url") or "api.opensubtitles.com"
            host = urlparse(host if "://" in host else "https://" + host).hostname
            if host not in self.api_domains:
                raise SourceError("The account API address is not supported.")
            base = f"https://{host}/api/v1"
        data = self.request(base + "/download", context, headers,
                            {"file_id": int(result.id), "sub_format": "srt"})
        self.download_remaining = data.get("remaining")
        self.download_reset = data.get("reset_time_utc")
        url = data.get("link", "")
        host = urlparse(url).hostname or ""
        if not any(host == domain or host.endswith("." + domain)
                   for domain in ("opensubtitles.com", "opensubtitles.org")):
            raise SourceError("Provider returned a download URL outside OpenSubtitles domains.")
        # Credentials never accompany the temporary download link.
        content = fetch_bytes(url, (host,), context)
        name = PurePosixPath(str(data.get("file_name") or "subtitle.srt").replace("\\", "/")).name
        if not name.lower().endswith((".srt", ".ass", ".ssa", ".vtt")):
            name = "subtitle.srt"
        return name, content
