from typing import TYPE_CHECKING

from django import template
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import Session

register = template.Library()


@register.simple_tag
def enrollment_status_text(session: Session) -> str:
    context = session.enrollment_status_context

    if context["status_type"] == "not_full":
        return _("%(enrolled)s of %(limit)s enrolled") % {
            "enrolled": context["enrolled"],
            "limit": context["limit"],
        }
    if context["status_type"] == "enrollment_limited":
        return _("Enrollment capacity reached (%(enrolled)s/%(limit)s)") % {
            "enrolled": context["enrolled"],
            "limit": context["limit"],
        }
    # session_full
    return _("Session full (%(enrolled)s/%(limit)s)") % {
        "enrolled": context["enrolled"],
        "limit": context["limit"],
    }
