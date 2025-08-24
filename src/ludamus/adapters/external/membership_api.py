"""External API integration for membership lookup."""

import logging

import requests
from django.conf import settings

from ludamus.adapters.db.django.models import EnrollmentConfig, UserEnrollmentConfig

logger = logging.getLogger(__name__)


class MembershipApiClient:
    """Client for external membership API integration."""

    def __init__(self):
        self.base_url = getattr(settings, "MEMBERSHIP_API_URL", None)
        self.token = getattr(settings, "MEMBERSHIP_API_TOKEN", None)
        self.timeout = getattr(settings, "MEMBERSHIP_API_TIMEOUT", 10)

    def is_configured(self) -> bool:
        """Check if API is properly configured."""
        return bool(self.base_url and self.token)

    def fetch_membership_count(self, email: str) -> int | None:
        """Fetch membership count for user from external API."""
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
            membership_count = data.get("membership_count", 0)

            logger.info(
                "Fetched membership count %d for user %s", membership_count, email
            )
            return membership_count

        except requests.RequestException as e:
            logger.error("Failed to fetch membership for %s: %s", email, str(e))
            return None
        except (KeyError, ValueError) as e:
            logger.error("Invalid response format for %s: %s", email, str(e))
            return None
        except Exception as e:
            logger.error(
                "Unexpected error fetching membership for %s: %s", email, str(e)
            )
            return None


def get_or_create_user_enrollment_config(
    enrollment_config: EnrollmentConfig, user_email: str
) -> UserEnrollmentConfig | None:
    """
    Get or create UserEnrollmentConfig, fetching from API if needed.

    Returns None if user is not eligible for enrollment.
    """
    # First try to get existing config
    user_config = enrollment_config.user_configs.filter(user_email=user_email).first()
    if user_config:
        # If config was fetched from API and has 0 slots, return None (user has no access)
        if user_config.fetched_from_api and user_config.allowed_slots == 0:
            return None
        return user_config

    # Check if we should fetch from API (only if we haven't tried before)
    # Look for any config for this user email that was fetched from API
    existing_api_config = UserEnrollmentConfig.objects.filter(
        user_email=user_email, fetched_from_api=True
    ).first()

    if existing_api_config:
        # We already tried the API for this user, don't try again
        logger.debug("Already fetched from API for %s, not trying again", user_email)
        return None

    # Try to fetch from API
    api_client = MembershipApiClient()
    if not api_client.is_configured():
        return None

    membership_count = api_client.fetch_membership_count(user_email)
    if membership_count is None:
        # API call failed - create a placeholder to avoid retrying
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,  # No slots if API failed
            fetched_from_api=True,
        )
        return None

    if membership_count == 0:
        # User has no membership - create config with 0 slots and mark as API-fetched
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,
            fetched_from_api=True,
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
    )

    logger.info("Created config with %d slots for member %s", allowed_slots, user_email)
    return user_config
