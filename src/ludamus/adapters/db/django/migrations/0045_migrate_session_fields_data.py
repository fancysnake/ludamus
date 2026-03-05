"""Migrate hardcoded Session fields to SessionField/SessionFieldValue system.

For each event with sessions:
- Creates SessionField definitions for requirements, needs, min_age, and tag categories
- Creates SessionFieldOption entries for select fields
- Creates SessionFieldRequirement entries for each ProposalCategory
- Creates SessionFieldValue entries from existing session data
"""

from django.db import migrations
from django.utils.text import slugify


def _unique_slug(session_field_model, event_id, base_slug):
    slug = base_slug or "field"
    for i in range(10):
        candidate = slug if i == 0 else f"{slug}-{i}"
        if not session_field_model.objects.filter(
            event_id=event_id, slug=candidate
        ).exists():
            return candidate
    return f"{slug}-{event_id}"


def forward(apps, schema_editor):
    Session = apps.get_model("db_main", "Session")
    SessionField = apps.get_model("db_main", "SessionField")
    SessionFieldOption = apps.get_model("db_main", "SessionFieldOption")
    SessionFieldRequirement = apps.get_model("db_main", "SessionFieldRequirement")
    SessionFieldValue = apps.get_model("db_main", "SessionFieldValue")
    ProposalCategory = apps.get_model("db_main", "ProposalCategory")
    TagCategory = apps.get_model("db_main", "TagCategory")
    Tag = apps.get_model("db_main", "Tag")

    # Find all event IDs that have sessions with a category
    event_ids = (
        Session.objects.filter(category__isnull=False)
        .values_list("category__event_id", flat=True)
        .distinct()
    )

    for event_id in event_ids:
        categories = ProposalCategory.objects.filter(event_id=event_id)
        sessions = Session.objects.filter(
            category__event_id=event_id, category__isnull=False
        )

        # 2a. Requirements field (text)
        req_field = SessionField.objects.create(
            event_id=event_id,
            name="Requirements",
            slug=_unique_slug(SessionField, event_id, "requirements"),
            field_type="text",
            is_multiple=False,
            allow_custom=False,
            order=100,
        )
        for cat in categories:
            SessionFieldRequirement.objects.create(
                category=cat, field=req_field, is_required=False, order=0
            )
        req_values = [
            SessionFieldValue(
                session=session, field=req_field, value=session.requirements
            )
            for session in sessions.exclude(requirements="")
        ]
        if req_values:
            SessionFieldValue.objects.bulk_create(req_values)

        # 2b. Needs field (text)
        needs_field = SessionField.objects.create(
            event_id=event_id,
            name="Needs",
            slug=_unique_slug(SessionField, event_id, "needs"),
            field_type="text",
            is_multiple=False,
            allow_custom=False,
            order=101,
        )
        for cat in categories:
            SessionFieldRequirement.objects.create(
                category=cat, field=needs_field, is_required=False, order=0
            )
        needs_values = [
            SessionFieldValue(session=session, field=needs_field, value=session.needs)
            for session in sessions.exclude(needs="")
        ]
        if needs_values:
            SessionFieldValue.objects.bulk_create(needs_values)

        # 2c. Minimum Age field (select)
        min_age_field = SessionField.objects.create(
            event_id=event_id,
            name="Minimum Age",
            slug=_unique_slug(SessionField, event_id, "min-age"),
            field_type="select",
            is_multiple=False,
            allow_custom=False,
            order=102,
        )
        for cat in categories:
            SessionFieldRequirement.objects.create(
                category=cat, field=min_age_field, is_required=False, order=0
            )
        pegi_values = ["3", "7", "12", "16", "18"]
        for order, pegi in enumerate(pegi_values):
            SessionFieldOption.objects.create(
                field=min_age_field, label=pegi, value=pegi, order=order
            )
        age_values = [
            SessionFieldValue(
                session=session, field=min_age_field, value=str(session.min_age)
            )
            for session in sessions.filter(min_age__gt=0)
        ]
        if age_values:
            SessionFieldValue.objects.bulk_create(age_values)

        # 2d. Tag-based fields (select, multiple)
        # Find all TagCategory IDs used by this event's proposal categories
        tag_category_ids = set()
        for cat in categories:
            cat_tag_ids = cat.tag_categories.values_list("id", flat=True)
            tag_category_ids.update(cat_tag_ids)

        for tag_idx, tc_id in enumerate(sorted(tag_category_ids)):
            tc = TagCategory.objects.get(pk=tc_id)

            tag_field = SessionField.objects.create(
                event_id=event_id,
                name=tc.name,
                slug=_unique_slug(SessionField, event_id, slugify(tc.name)),
                field_type="select",
                is_multiple=True,
                allow_custom=tc.input_type == "type",
                order=200 + tag_idx,
            )

            # Create options from confirmed tags
            confirmed_tags = Tag.objects.filter(
                category_id=tc_id, confirmed=True
            ).order_by("name")
            for opt_order, tag in enumerate(confirmed_tags):
                SessionFieldOption.objects.create(
                    field=tag_field, label=tag.name, value=tag.name, order=opt_order
                )

            # Link to categories that use this tag category
            for cat in categories:
                if cat.tag_categories.filter(pk=tc_id).exists():
                    SessionFieldRequirement.objects.create(
                        category=cat, field=tag_field, is_required=False, order=0
                    )

            # Create values from session tags
            tag_values = []
            all_tags_in_category = Tag.objects.filter(category_id=tc_id)
            tag_ids = set(all_tags_in_category.values_list("id", flat=True))

            for session in sessions:
                session_tag_ids = set(session.tags.values_list("id", flat=True))
                matching = session_tag_ids & tag_ids
                for tag_id in matching:
                    tag = Tag.objects.get(pk=tag_id)
                    tag_values.append(
                        SessionFieldValue(
                            session=session, field=tag_field, value=tag.name
                        )
                    )
            if tag_values:
                SessionFieldValue.objects.bulk_create(tag_values)


def reverse(apps, schema_editor):
    SessionField = apps.get_model("db_main", "SessionField")
    # Delete all fields created by this migration (cascade deletes values, options, reqs)
    # Known slugs: requirements, needs, min-age, plus tag-based fields at order >= 200
    SessionField.objects.filter(slug__in=["requirements", "needs", "min-age"]).delete()
    SessionField.objects.filter(order__gte=200).delete()


class Migration(migrations.Migration):

    dependencies = [("db_main", "0044_sessionfieldvalue")]

    operations = [migrations.RunPython(forward, reverse)]
