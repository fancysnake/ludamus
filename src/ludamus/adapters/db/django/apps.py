from django.apps import AppConfig


class DBMainConfig(AppConfig):
    name = "ludamus.adapters.db.django"
    label = "db_main"

    def ready(self) -> None:
        # Signals are intentionally disabled; sphere creation is handled explicitly.
        return
