class RedirectError(Exception):
    def __init__(
        self, url: str, *, error: str | None = None, warning: str | None = None
    ) -> None:
        self.url = url
        self.error = error
        self.warning = warning
