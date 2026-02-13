from django import template

register = template.Library()


@register.filter
def avatar_bg_class(name_value: str) -> str:
    if not name_value:
        name_value = ""
    name_len = len(name_value)

    if name_len % 4 == 0:
        return "bg-coral-400"
    if name_len % 3 == 0:
        return "bg-teal-400"
    if name_len % 2 == 0:
        return "bg-teal-500"
    return "bg-warm-400"
