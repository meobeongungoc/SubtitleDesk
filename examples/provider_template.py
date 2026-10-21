"""Copy into subtitledesk/sources only AFTER the user supplies a site.
This file is deliberately NOT registered or imported by the application.
"""
from subtitledesk.providers import Capabilities, Page


class WebsiteProvider:
    capabilities = Capabilities(
        id="replace_with_site_id", name="Tên website do người dùng cung cấp",
        languages=("vi", "en"), pagination=True,
        credentials=("api_key",), min_interval=1.0, timeout=15.0,
        domains=(),  # Exact HTTPS API/download domains confirmed from official docs.
    )

    def __init__(self, secret_store):
        self.secrets = secret_store

    def search(self, query, cursor, context):
        context.check()
        # Obtain key via self.secrets.get(self.capabilities.id, "api_key").
        # fetch_bytes(...) enforces allowlisted HTTPS domains, size and timeout.
        # Normalize metadata into Result; return Page(results, next_cursor).
        # Never log credentials, cookies or complete authenticated URLs.
        raise NotImplementedError("Chờ website người dùng cung cấp.")

    def download(self, result, context):
        context.check()
        # Return (filename, bytes). GUI validates archive and subtitle before saving.
        raise NotImplementedError("Chờ website người dùng cung cấp.")
