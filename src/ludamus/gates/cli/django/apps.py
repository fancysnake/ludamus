"""Django app configuration for CLI gates."""

from django.apps import AppConfig


class CliGatesConfig(AppConfig):
    """Configuration for CLI management commands."""

    name = "ludamus.gates.cli.django"
    label = "cli_gates"
