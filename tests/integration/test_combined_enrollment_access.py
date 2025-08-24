"""
Integration tests for combined enrollment access (individual + domain).
"""

from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.sites.models import Site

from ludamus.adapters.db.django.models import (
    DomainEnrollmentConfig,
    EnrollmentConfig,
    Event,
    Sphere,
    UserEnrollmentConfig,
)


@pytest.mark.django_db
class TestCombinedEnrollmentAccess:
    """Test combined individual and domain enrollment access."""

    def setup_method(self):
        """Set up test data."""
        # Create site and sphere
        self.site = Site.objects.create(name="Test Site", domain="test.com")
        self.sphere = Sphere.objects.create(name="Test Sphere", site=self.site)

        # Create event in the future
        now = datetime.now(UTC)
        self.event = Event.objects.create(
            sphere=self.sphere,
            name="Test Event",
            slug="test-event",
            start_time=now + timedelta(days=30),
            end_time=now + timedelta(days=30, hours=8),
        )

        # Create enrollment config that is currently active
        self.enrollment_config = EnrollmentConfig.objects.create(
            event=self.event,
            start_time=now - timedelta(days=1),  # Started yesterday
            end_time=now + timedelta(days=60),  # Ends in 2 months
            percentage_slots=100,
        )

    def test_individual_access_only(self):
        """Test user with only individual access."""
        # Create individual user config
        UserEnrollmentConfig.objects.create(
            enrollment_config=self.enrollment_config,
            user_email="user@example.com",
            allowed_slots=5,
        )

        config = self.event.get_user_enrollment_config("user@example.com")

        assert config is not None
        assert config.allowed_slots == 5
        assert config.has_individual_access() is True
        assert config.has_domain_access() is False
        assert config.is_combined_access() is False
        assert config.is_domain_based() is False

    def test_domain_access_only(self):
        """Test user with only domain access."""
        # Create domain config
        DomainEnrollmentConfig.objects.create(
            enrollment_config=self.enrollment_config,
            domain="company.com",
            allowed_slots_per_user=3,
        )

        config = self.event.get_user_enrollment_config("user@company.com")

        assert config is not None
        assert config.allowed_slots == 3
        assert config.has_individual_access() is False
        assert config.has_domain_access() is True
        assert config.is_combined_access() is False
        assert config.is_domain_based() is True
        assert config.get_source_domain() == "company.com"

    def test_combined_access(self):
        """Test user with both individual and domain access."""
        # Create individual user config
        UserEnrollmentConfig.objects.create(
            enrollment_config=self.enrollment_config,
            user_email="user@company.com",
            allowed_slots=5,
        )

        # Create domain config for same domain
        DomainEnrollmentConfig.objects.create(
            enrollment_config=self.enrollment_config,
            domain="company.com",
            allowed_slots_per_user=3,
        )

        config = self.event.get_user_enrollment_config("user@company.com")

        assert config is not None
        # Should sum individual (5) + domain (3) = 8 slots
        assert config.allowed_slots == 8
        assert config.has_individual_access() is True
        assert config.has_domain_access() is True
        assert config.is_combined_access() is True
        assert config.is_domain_based() is False
        assert config.get_source_domain() == "company.com"

    def test_multiple_individual_configs(self):
        """Test user with multiple individual configs across different enrollment configs."""
        # Create second enrollment config for same event
        now = datetime.now(UTC)
        enrollment_config2 = EnrollmentConfig.objects.create(
            event=self.event,
            start_time=now - timedelta(days=1),  # Also active
            end_time=now + timedelta(days=30),
            percentage_slots=50,
        )

        # Create individual configs in both enrollment configs
        UserEnrollmentConfig.objects.create(
            enrollment_config=self.enrollment_config,
            user_email="user@example.com",
            allowed_slots=5,
        )
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config2,
            user_email="user@example.com",
            allowed_slots=3,
        )

        config = self.event.get_user_enrollment_config("user@example.com")

        assert config is not None
        # Should sum both individual configs: 5 + 3 = 8
        assert config.allowed_slots == 8
        assert config.has_individual_access() is True
        assert config.has_domain_access() is False
        assert config.is_combined_access() is True

    def test_no_access(self):
        """Test user with no access."""
        config = self.event.get_user_enrollment_config("nouser@nowhere.com")
        assert config is None

    def test_domain_normalization(self):
        """Test that domain matching works with different email formats."""
        # Create domain config
        DomainEnrollmentConfig.objects.create(
            enrollment_config=self.enrollment_config,
            domain="company.com",
            allowed_slots_per_user=3,
        )

        # Test with different email formats
        config1 = self.event.get_user_enrollment_config("user@company.com")
        config2 = self.event.get_user_enrollment_config("user@COMPANY.COM")

        assert config1 is not None
        assert config2 is not None
        assert config1.allowed_slots == 3
        assert config2.allowed_slots == 3
