from django.core.cache import cache


class DjangoCache:
    @staticmethod
    def get(key: str) -> object:
        result: object = cache.get(key)
        return result

    @staticmethod
    def set(key: str, value: object, timeout: int | None = None) -> None:
        cache.set(key, value, timeout)
