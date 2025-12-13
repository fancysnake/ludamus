"""External API integration for membership lookup."""

import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from ludamus.adapters.db.django.models import EnrollmentConfig, UserEnrollmentConfig

logger = logging.getLogger(__name__)


class MembershipApiClient:
    """Client for external membership API integration."""

    def __init__(self) -> None:
        self.base_url = settings.MEMBERSHIP_API_BASE_URL
        self.token = settings.MEMBERSHIP_API_TOKEN
        self.timeout = settings.MEMBERSHIP_API_TIMEOUT

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def fetch_membership_count(self, email: str) -> int | None:
        if not self.is_configured():
            logger.warning(
                "Membership API not configured - skipping fetch for %s", email
            )
            return None

        try:
            response = requests.get(
                self.base_url,
                params={"email": email},
                headers={"Authorization": f"Token {self.token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            membership_count: int = data.get("membership_count", 0)

            logger.info(
                "Fetched membership count %d for user %s", membership_count, email
            )
        except requests.RequestException:
            logger.exception("Failed to fetch membership for %s", email)
            return None
        except KeyError, ValueError:
            logger.exception("Invalid response format for %s", email)
            return None
        except Exception:
            logger.exception("Unexpected error fetching membership for %s", email)
            return None

        return membership_count


def get_or_create_user_enrollment_config(
    enrollment_config: EnrollmentConfig, user_email: str
) -> UserEnrollmentConfig | None:
    # First try to get existing config
    user_config = enrollment_config.user_configs.filter(user_email=user_email).first()

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
        if user_config.fetched_from_api and user_config.last_check:
            check_interval_minutes = getattr(
                settings, "MEMBERSHIP_API_CHECK_INTERVAL", 15
            )
            time_threshold = timezone.now() - timedelta(minutes=check_interval_minutes)

            if user_config.last_check < time_threshold:
                logger.info(
                    (
                        "Config for %s has 0 slots and is older than %d minutes, "
                        "refreshing from API"
                    ),
                    user_email,
                    check_interval_minutes,
                )
                # Update the existing config with fresh API data
                return _refresh_user_config_from_api(user_config)
            logger.debug(
                "Config for %s has 0 slots but was checked recently, using cached data",
                user_email,
            )

        # Config has 0 slots
        return None

    # No existing config - try to fetch from API
    api_client = MembershipApiClient()
    if not api_client.is_configured():
        return None

    return _create_user_config_from_api(enrollment_config, user_email, api_client)


def _refresh_user_config_from_api(
    user_config: UserEnrollmentConfig,
) -> UserEnrollmentConfig | None:
    api_client = MembershipApiClient()
    if not api_client.is_configured():
        logger.warning(
            "API not configured, cannot refresh config for %s", user_config.user_email
        )
        return user_config if user_config.allowed_slots > 0 else None

    membership_count = api_client.fetch_membership_count(user_config.user_email)
    current_time = timezone.now()

    if membership_count is None:
        # API call failed - update last_check but keep existing data
        user_config.last_check = current_time
        user_config.save(update_fields=["last_check"])
        logger.warning(
            "API call failed for %s, keeping existing config", user_config.user_email
        )
        return user_config if user_config.allowed_slots > 0 else None

    # Update config with fresh data
    if membership_count == 0:
        user_config.allowed_slots = 0
        user_config.last_check = current_time
        user_config.save(update_fields=["allowed_slots", "last_check"])
        logger.info(
            "Refreshed config for %s: now has 0 slots (membership expired)",
            user_config.user_email,
        )
        return None  # Return None since user has no slots
    allowed_slots = min(membership_count, 5)  # Cap at 5 slots maximum
    user_config.allowed_slots = allowed_slots
    user_config.last_check = current_time
    user_config.save(update_fields=["allowed_slots", "last_check"])
    logger.info(
        "Refreshed config for %s: now has %d slots",
        user_config.user_email,
        allowed_slots,
    )
    return user_config


def _create_user_config_from_api(
    enrollment_config: EnrollmentConfig,
    user_email: str,
    api_client: MembershipApiClient,
) -> UserEnrollmentConfig | None:
    membership_count = api_client.fetch_membership_count(user_email)
    current_time = timezone.now()

    if membership_count is None:
        # API call failed - create a placeholder to avoid retrying too soon
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,  # No slots if API failed
            fetched_from_api=True,
            last_check=current_time,
        )
        return None

    if membership_count == 0:
        # User has no membership - create config with 0 slots and mark as API-fetched
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=current_time,
        )
        logger.info("Created zero-slot config for non-member %s", user_email)
        return None  # Return None since user has no slots

    # User has membership - create config with slots based on membership count
    # You can customize this logic based on your business rules
    allowed_slots = min(membership_count, 5)  # Cap at 5 slots maximum

    user_config = UserEnrollmentConfig.objects.create(
        enrollment_config=enrollment_config,
        user_email=user_email,
        allowed_slots=allowed_slots,
        fetched_from_api=True,
        last_check=current_time,
    )

    logger.info("Created config with %d slots for member %s", allowed_slots, user_email)
    return user_config
