from django.contrib import admin

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Event,
    Guild,
    Proposal,
    ProposalCategory,
    Session,
    Space,
    Sphere,
    Tag,
    TagCategory,
    TimeSlot,
    User,
)

admin.site.register(AgendaItem)
admin.site.register(Event)
admin.site.register(Guild)
admin.site.register(Proposal)
admin.site.register(Space)
admin.site.register(Session)
admin.site.register(Sphere)
admin.site.register(Tag)
admin.site.register(TagCategory)
admin.site.register(TimeSlot)
admin.site.register(User)
admin.site.register(ProposalCategory)
