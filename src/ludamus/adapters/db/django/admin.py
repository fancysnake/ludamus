from django.contrib import admin

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Festival,
    Guild,
    Proposal,
    Room,
    Session,
    Sphere,
    Tag,
    TagCategory,
    TimeSlot,
    User,
    WaitList,
)

admin.site.register(AgendaItem)
admin.site.register(Festival)
admin.site.register(Guild)
admin.site.register(Proposal)
admin.site.register(Room)
admin.site.register(Session)
admin.site.register(Sphere)
admin.site.register(Tag)
admin.site.register(TagCategory)
admin.site.register(TimeSlot)
admin.site.register(User)
admin.site.register(WaitList)
