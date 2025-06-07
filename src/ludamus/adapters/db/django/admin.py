from django.contrib import admin

from ludamus.adapters.db.django.models import Auth0User, User

admin.site.register(User)
admin.site.register(Auth0User)
