from collections.abc import Sequence
from datetime import timedelta

import environ
import requests
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone
from faker import Faker

from ludamus.adapters.db.django.models import (
    AgendaItem,
    EnrollmentConfig,
    Event,
    Session,
    Space,
    Sphere,
    Tag,
    TagCategory,
    User,
)

env = environ.Env()

IMAGES = {
    "sphere_fantasy": "https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=2094&auto=format&fit=crop",
    "sphere_scifi": "https://images.unsplash.com/photo-1555680202-c86f0e12f086?q=80&w=2070&auto=format&fit=crop",
    "event_tabletop": "https://images.unsplash.com/photo-1610484826967-09c5720778c7?q=80&w=2070&auto=format&fit=crop",
    "event_halloween": "https://images.unsplash.com/photo-1509248961158-e54f6934749c?q=80&w=2037&auto=format&fit=crop",
    "event_scifi": "https://images.unsplash.com/photo-1542751371-adc38448a05e?q=80&w=2070&auto=format&fit=crop",
    "session_fantasy_1": "https://images.unsplash.com/photo-1599058945522-28d584b6f0ff?q=80&w=2069&auto=format&fit=crop",
    "session_fantasy_2": "https://images.unsplash.com/photo-1519074069444-1ba4fff66d16?q=80&w=2574&auto=format&fit=crop",
    "session_horror": "https://images.unsplash.com/photo-1518331483807-f6adc0e1ad80?q=80&w=2069&auto=format&fit=crop",
    "session_scifi_1": "https://images.unsplash.com/photo-1535030456952-3791b811d806?q=80&w=2069&auto=format&fit=crop",
    "session_scifi_2": "https://images.unsplash.com/photo-1480796927426-f609979314bd?q=80&w=2070&auto=format&fit=crop",
}


class Command(BaseCommand):
    help = "Seed the database with initial data for development and testing."

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help="Do not flush the database before seeding.",
        )

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        if not options["no_flush"]:
            self.stdout.write("Flushing database...")
            call_command("flush", verbosity=0, interactive=False)

        self.stdout.write("Seeding data...")
        fake = Faker()

        # Create Sites & Spheres
        root_domain = env("ROOT_DOMAIN", default="localhost:8000")
        root_site, _ = Site.objects.get_or_create(
            domain=root_domain, defaults={"name": "Root Domain"}
        )

        # Ensure root sphere exists
        Sphere.objects.get_or_create(name="Root Sphere", site=root_site)

        # Create localhost sites for local development
        localhost_spheres = []
        for localhost_domain in ["localhost:8000", "127.0.0.1:8000"]:
            if localhost_domain != root_domain:
                localhost_site, _ = Site.objects.get_or_create(
                    domain=localhost_domain, defaults={"name": "Local Dev"}
                )
                localhost_sphere, _ = Sphere.objects.get_or_create(
                    site=localhost_site,
                    defaults={
                        "name": "Local Dev Sphere",
                        "description": (
                            "A local development sphere for testing and "
                            "development purposes."
                        ),
                        "visibility": Sphere.Visibility.PUBLIC,
                    },
                )
                self._set_image(localhost_sphere, IMAGES["sphere_fantasy"])
                localhost_spheres.append(localhost_sphere)

        # Create a dev/test sphere
        sphere_domain = "ludamus.local:8000"
        site, _ = Site.objects.get_or_create(
            domain=sphere_domain, defaults={"name": "Dev Sphere"}
        )
        sphere, _ = Sphere.objects.get_or_create(
            name="Ludamus Dev",
            site=site,
            defaults={
                "description": "A development sphere for testing features.",
                "visibility": Sphere.Visibility.PUBLIC,
            },
        )
        self._set_image(sphere, IMAGES["sphere_scifi"])

        # Create Users
        users = []
        for i in range(5):
            username = f"testuser{i + 1}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"testuser{i + 1}@example.com",
                    "name": fake.name(),
                    "slug": username,
                },
            )
            if created:
                user.set_password("password")
                user.save()
            users.append(user)

        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "name": "Admin User",
                "slug": "admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin")
            admin_user.save()

        # Create Tags
        category, _ = TagCategory.objects.get_or_create(
            name="Genre", defaults={"input_type": TagCategory.InputType.SELECT}
        )
        tags = []
        for genre in ["RPG", "Board Game", "LARP", "Workshop"]:
            tag, _ = Tag.objects.get_or_create(
                name=genre, category=category, confirmed=True
            )
            tags.append(tag)

        # Create Events for Ludamus Dev sphere
        self._create_upcoming_event(sphere, tags)
        self._create_past_event(sphere)
        self._create_live_event(sphere, tags)

        # Create Events for localhost spheres
        for localhost_sphere in localhost_spheres:
            self._create_upcoming_event(localhost_sphere, tags)
            self._create_past_event(localhost_sphere)

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))

    def _set_image(self, instance: models.Model, url: str) -> None:
        if instance.image:
            return
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                filename = url.split("/")[-1].split("?")[0] + ".jpg"
                instance.image.save(filename, ContentFile(response.content), save=True)
                self.stdout.write(f"Set image for {instance}")
        except Exception as e:
            self.stderr.write(f"Failed to fetch image {url}: {e}")

    def _create_upcoming_event(
        self, sphere: Sphere, tags: Sequence[Tag]
    ) -> None:
        now = timezone.now()
        event, created = Event.objects.get_or_create(
            sphere=sphere,
            slug="autumn-open",
            defaults={
                "name": "Autumn Open Playtest",
                "description": (
                    "A cozy meetup packed with prototypes, mentors, "
                    "and hands-on demos.\n"
                    "Bring dice, meeples, and curiosity!"
                ),
                "start_time": now + timedelta(days=1),
                "end_time": now + timedelta(days=1, hours=4),
                "publication_time": now - timedelta(days=2),
                "location_label": "Kawalerka",
                "location_url": (
                    "https://www.google.com/maps/place/Kawalerka/"
                    "@51.1201309,17.0493087,14z/data=!4m6!3m5!1s0x470fe9d453002611:"
                    "0x8b4f765f05fba3f6!8m2!3d51.1114596!4d17.0549689!16s%2Fg%2F"
                    "12hk5jf6g?entry=ttu&g_ep=EgoyMDI1MTExNy4wIKXMDSoASAFQAw%3D%3D"
                ),
            },
        )
        self._set_image(event, IMAGES["event_tabletop"])

        if created:
            EnrollmentConfig.objects.get_or_create(
                event=event,
                defaults={
                    "start_time": now - timedelta(days=1),
                    "end_time": now + timedelta(days=7),
                    "percentage_slots": 100,
                    "banner_text": (
                        "Enrollment is open—grab a slot before we fill up!"
                    ),
                    "allow_anonymous_enrollment": True,
                },
            )

        self._create_session(
            sphere,
            event,
            title="Mega Strategy Lab",
            slug="mega-strategy",
            presenter="Alex Morgan",
            description="Deep dive into asymmetric mechanics and pacing tricks.",
            location="Main Hall East Wing",
            start_offset=timedelta(hours=1),
            duration=timedelta(hours=2),
            tags=[tags[1]],
            image_url=IMAGES["session_scifi_1"],
        )

        self._create_session(
            sphere,
            event,
            title="Cozy Storytellers Circle",
            slug="story-circle",
            presenter="Priya Chen",
            description="Collaborative narrative building with lightweight prompts.",
            location="Fireside Alcove",
            start_offset=timedelta(hours=2),
            duration=timedelta(hours=1),
            tags=[tags[0]],
            image_url=IMAGES["session_fantasy_1"],
        )

    def _create_past_event(self, sphere: Sphere) -> None:
        now = timezone.now()
        start = now - timedelta(days=7)
        event, _ = Event.objects.get_or_create(
            sphere=sphere,
            slug="retro-mini-jam",
            defaults={
                "name": "Retro Mini Jam",
                "description": (
                    "Weekend jam focused on 8-bit vibes and tactile puzzlers."
                ),
                "start_time": start,
                "end_time": start + timedelta(hours=6),
                "publication_time": now - timedelta(days=14),
            },
        )
        self._set_image(event, IMAGES["event_halloween"])

    def _create_live_event(
        self, sphere: Sphere, tags: Sequence[Tag]
    ) -> None:
        now = timezone.now()
        event, created = Event.objects.get_or_create(
            sphere=sphere,
            slug="live-gaming",
            defaults={
                "name": "Live Gaming Night",
                "description": (
                    "Happening right now! Join us for some late night gaming."
                ),
                "start_time": now - timedelta(hours=1),
                "end_time": now + timedelta(hours=3),
                "publication_time": now - timedelta(days=5),
                "location_label": "Virtual Space",
            },
        )
        self._set_image(event, IMAGES["event_scifi"])

        if created:
            EnrollmentConfig.objects.get_or_create(
                event=event,
                defaults={
                    "start_time": now - timedelta(days=2),
                    "end_time": now + timedelta(days=1),
                    "percentage_slots": 100,
                    "allow_anonymous_enrollment": True,
                },
            )

        self._create_session(
            sphere,
            event,
            title="Late Night Among Us",
            slug="late-night-among-us",
            presenter="Red",
            description="Who is the impostor?",
            location="Spaceship",
            start_offset=timedelta(minutes=30),
            duration=timedelta(hours=1),
            tags=[tags[2]],
            image_url=IMAGES["session_scifi_2"],
        )

    def _create_session(  # noqa: PLR0913
        self,
        sphere: Sphere,
        event: Event,
        title: str,
        slug: str,
        presenter: str,
        description: str,
        location: str,
        start_offset: timedelta,
        duration: timedelta,
        tags: Sequence[Tag] | None = None,
        image_url: str | None = None,
    ) -> None:
        space, _ = Space.objects.get_or_create(
            event=event,
            name=location,
            defaults={"slug": f"{event.slug}-{slug}-space"},
        )
        session, session_created = Session.objects.get_or_create(
            sphere=sphere,
            slug=slug,
            defaults={
                "presenter_name": presenter,
                "title": title,
                "description": description,
                "participants_limit": 24,
                "min_age": 10,
            },
        )
        if tags and session_created:
            session.tags.set(tags)

        if image_url:
             self._set_image(session, image_url)

        if session_created:
            AgendaItem.objects.get_or_create(
                session=session,
                defaults={
                    "space": space,
                    "session_confirmed": True,
                    "start_time": event.start_time + start_offset,
                    "end_time": event.start_time + start_offset + duration,
                },
            )
