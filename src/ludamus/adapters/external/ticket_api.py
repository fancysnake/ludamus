"""External API integration for ticket lookup."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, cast

import requests
from django.utils import timezone

from ludamus.adapters.external.ticket_api_registry import (
    BaseTicketAPIClient,
    register_ticket_api,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import EnrollmentConfig, UserEnrollmentConfig
    from ludamus.adapters.external.ticket_api_registry import TicketAPIClientFactory
    from ludamus.pacts import EnrollmentConfigProtocol, TicketAPIClientProtocol

logger = logging.getLogger(__name__)


class TicketAPIError(Exception):
    pass


@register_ticket_api("kapitularz")
class KapitularzTicketAPIClient(BaseTicketAPIClient):
    """Ticket API client for sklep.kapitularz.pl."""

    display_name = "Kapitularz Shop"

    def fetch_ticket_count(self, email: str) -> int:
        try:
            response = requests.get(
                self.base_url,
                params={"email": email},
                headers={"Authorization": f"Token {self.secret}"},
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            ticket_count: int = data.get("membership_count", 0)

            logger.info("Fetched ticket count %d for user %s", ticket_count, email)
        except requests.RequestException as exception:
            logger.exception("Failed to fetch ticket count for %s", email)
            raise TicketAPIError from exception
        except Exception as exception:
            logger.exception("Unexpected error fetching ticket count for %s", email)
            raise TicketAPIError from exception

        return ticket_count


def get_or_create_user_enrollment_config(
    enrollment_config: EnrollmentConfig,
    user_email: str,
    get_api_client: TicketAPIClientFactory,
) -> UserEnrollmentConfig | None:
    """Get or create a user enrollment config, optionally fetching from ticket API.

    Args:
        enrollment_config: The enrollment config to get/create user config for.
        user_email: The user's email address.
        get_api_client: Factory function that returns API client for enrollment config.

    Returns:
        The user enrollment config if user has slots, None otherwise.
    """
    from django.conf import settings  # noqa: PLC0415

    # First try to get existing config
    user_config = enrollment_config.user_configs.filter(
        user_email=user_email, fetched_from_api=True
    ).first()

    if user_config:
        # If config has slots > 0, it's final - no need to refresh
        if user_config.allowed_slots > 0:
            logger.debug(
                "Config for %s has %d slots, using final cached data",
                user_email,
                user_config.allowed_slots,
            )
            return user_config

        # Only refresh configs with 0 slots, and only if enough time has passed
        check_interval_minutes = getattr(settings, "TICKET_API_CHECK_INTERVAL", 15)
        time_threshold = timezone.now() - timedelta(minutes=check_interval_minutes)

        if not user_config.last_check or user_config.last_check < time_threshold:
            logger.info(
                (
                    "Config for %s has 0 slots and is older than %d minutes, "
                    "refreshing from API"
                ),
                user_email,
                check_interval_minutes,
            )
            # Update the existing config with fresh API data
            api_client = get_api_client(
                cast("EnrollmentConfigProtocol", enrollment_config)
            )
            return _refresh_user_config_from_api(user_config, api_client)
        logger.debug(
            "Config for %s has 0 slots but was checked recently, using cached data",
            user_email,
        )

        # Config has 0 slots
        return None

    # No existing config - try to fetch from API if client is available
    api_client = get_api_client(cast("EnrollmentConfigProtocol", enrollment_config))
    if api_client is None:
        return None

    return _create_user_config_from_api(enrollment_config, user_email, api_client)


def _refresh_user_config_from_api(
    user_config: UserEnrollmentConfig, api_client: TicketAPIClientProtocol | None = None
) -> UserEnrollmentConfig | None:
    if api_client is None:
        return user_config

    try:
        ticket_count = api_client.fetch_ticket_count(user_config.user_email)
    except TicketAPIError:
        return user_config

    current_time = timezone.now()

    # Update config with fresh data
    if ticket_count == 0:
        user_config.allowed_slots = 0
        user_config.last_check = current_time
        user_config.save(update_fields=["allowed_slots", "last_check"])
        logger.info(
            "Refreshed config for %s: now has 0 slots (ticket expired)",
            user_config.user_email,
        )
        return None  # Return None since user has no slots

    user_config.allowed_slots = ticket_count
    user_config.last_check = current_time
    user_config.save(update_fields=["allowed_slots", "last_check"])
    logger.info(
        "Refreshed config for %s: now has %d slots",
        user_config.user_email,
        ticket_count,
    )
    return user_config


def _create_user_config_from_api(
    enrollment_config: EnrollmentConfig,
    user_email: str,
    api_client: TicketAPIClientProtocol,
) -> UserEnrollmentConfig | None:
    from ludamus.adapters.db.django.models import (  # noqa: PLC0415
        UserEnrollmentConfig as UserEnrollmentConfigModel,
    )

    try:
        ticket_count = api_client.fetch_ticket_count(user_email)
    except TicketAPIError:
        return None

    current_time = timezone.now()

    if ticket_count == 0:
        # User has no ticket - create config with 0 slots and mark as API-fetched
        UserEnrollmentConfigModel.objects.create(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=current_time,
        )
        logger.info("Created zero-slot config for non-ticket-holder %s", user_email)
        return None  # Return None since user has no slots

    # User has ticket - create config with slots based on ticket count
    user_config = UserEnrollmentConfigModel.objects.create(
        enrollment_config=enrollment_config,
        user_email=user_email,
        allowed_slots=ticket_count,
        fetched_from_api=True,
        last_check=current_time,
    )

    logger.info(
        "Created config with %d slots for ticket holder %s", ticket_count, user_email
    )
    return user_config
