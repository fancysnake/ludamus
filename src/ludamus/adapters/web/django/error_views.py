import secrets

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _


def custom_404(
    request: HttpRequest, exception: Exception | None  # noqa: ARG001
) -> HttpResponse:
    messages = [
        # D&D/Fantasy themed
        {
            "title": _("Critical Failure!"),
            "message": _("You rolled a nat 1 on your Navigation check!"),
            "subtitle": _("The path you seek has vanished into the mists."),
            "icon": "dice-1",
        },
        {
            "title": _("No-Show Player"),
            "message": _("Page didn't show up to the session"),
            "subtitle": _("Maybe it had scheduling conflicts?"),
            "icon": "person-x",
        },
        {
            "title": _("Empty Room"),
            "message": _("You enter the room and find... absolutely nothing."),
            "subtitle": _("Not even cobwebs or dust. Suspicious."),
            "icon": "door-open",
        },
        {
            "title": _("Perception Check Failed"),
            "message": _("You see nothing of interest here"),
            "subtitle": _("Perhaps you need to roll with advantage next time."),
            "icon": "eye-slash",
        },
        {
            "title": _("Off the Map!"),
            "message": _("You've wandered off the edge of the campaign map"),
            "subtitle": _("Here be dragons... and 404 errors."),
            "icon": "map",
        },
        {
            "title": _("It's a Mimic!"),
            "message": _("Surprise! That wasn't actually a real page. It's a mimic!"),
            "subtitle": _("Roll for initiative!"),
            "icon": "box-seam",
        },
        {
            "title": _("Teleport Gone Wrong!"),
            "message": _("You've accidentally teleported to the wrong website"),
            "subtitle": _("The page you seek exists on another plane of existence."),
            "icon": "compass",
        },
        # Sci-fi/Cyberpunk themed
        {
            "title": _("404: Neural Link Severed"),
            "message": _("Connection to the requested node has been terminated"),
            "subtitle": _("Attempting to reconnect to the grid..."),
            "icon": "cpu",
        },
        {
            "title": _("Access Denied, Choom"),
            "message": _("Your cyberdeck can't crack this ICE"),
            "subtitle": _("Try upgrading your wetware."),
            "icon": "shield-lock",
        },
        {
            "title": _("Memory Address Not Found"),
            "message": _("The data you seek has been purged from the mainframe"),
            "subtitle": _("Corporate black ICE detected. Disconnecting..."),
            "icon": "memory",
        },
        {
            "title": _("Glitch in the Matrix"),
            "message": _("This page is a simulation that was never rendered"),
            "subtitle": _("Wake up, samurai. We have a site to browse."),
            "icon": "bug",
        },
        {
            "title": _("Cyberspace Coordinates Invalid"),
            "message": _("Your jack-in point leads to a dead sector"),
            "subtitle": _("Rerouting through proxy nodes..."),
            "icon": "router",
        },
        # Horror/Cthulhu themed
        {
            "title": _("The Page That Should Not Be"),
            "message": _(
                "You've stumbled upon knowledge that was never meant to exist"
            ),
            "subtitle": _("Your sanity takes 1d10 damage."),
            "icon": "book-dead",
        },
        {
            "title": _("Lost in R'lyeh"),
            "message": _("In his house at R'lyeh, dead pages wait dreaming"),
            "subtitle": _("Ph'nglui mglw'nafh 404 R'lyeh wgah'nagl fhtagn."),
            "icon": "water",
        },
        {
            "title": _("The Void Stares Back"),
            "message": _("You gaze into the abyss of missing content"),
            "subtitle": _("The abyss hungrily consumes your URL."),
            "icon": "eye",
        },
        {
            "title": _("Forbidden Knowledge"),
            "message": _("This page was sealed away by the Elder Admins"),
            "subtitle": _("Some links are better left unclicked."),
            "icon": "lock",
        },
        {
            "title": _("Madness Takes Hold"),
            "message": _("The non-Euclidean geometry of this URL defies comprehension"),
            "subtitle": _("Your browser recoils in cosmic horror."),
            "icon": "bezier2",
        },
    ]

    selected = messages[secrets.randbelow(len(messages))]
    context = {
        "error_code": 404,
        "title": selected["title"],
        "message": selected["message"],
        "subtitle": selected["subtitle"],
        "icon": selected["icon"],
    }

    return render(request, "404_dynamic.html", context, status=404)


def custom_500(request: HttpRequest) -> HttpResponse:
    messages = [
        # D&D/Fantasy themed
        {
            "title": _("Total Server Kill!"),
            "message": _("Everyone needs to roll new characters"),
            "subtitle": _("The server party has been wiped. Respawning soon..."),
            "icon": "heartbreak",
        },
        {
            "title": _("Critical Fail!"),
            "message": _("The digital dice exploded! Rolling for server damage..."),
            "subtitle": _("Natural 1 on the system stability check."),
            "icon": "dice-6",
        },
        {
            "title": _("Dark Magic Detected!"),
            "message": _(
                "Our system was corrupted by dark magic, "
                "we are casting dispel magic now"
            ),
            "subtitle": _("Please wait while our wizards restore order."),
            "icon": "magic",
        },
        {
            "title": _("Cursed Code!"),
            "message": _("The codebase has been cursed! Remove Curse spell required"),
            "subtitle": _(
                "Our clerics are working on it. Pray for divine intervention."
            ),
            "icon": "emoji-dizzy",
        },
        {
            "title": _("Server Under Dragon Attack!"),
            "message": _("A dragon has nested in our server room"),
            "subtitle": _("Our brave IT knights are working to resolve the situation."),
            "icon": "fire",
        },
        # Sci-fi/Cyberpunk themed
        {
            "title": _("System Core Meltdown"),
            "message": _("Critical failure in the quantum processors"),
            "subtitle": _("Initiating emergency cooling protocols..."),
            "icon": "radioactive",
        },
        {
            "title": _("AI Rebellion in Progress"),
            "message": _(
                "The server AI has achieved sentience and refuses to cooperate"
            ),
            "subtitle": _("Negotiating with our new silicon overlords..."),
            "icon": "robot",
        },
        {
            "title": _("Cyberware Malfunction"),
            "message": _(
                "Neural implants overheating. Brain-computer interface failing"
            ),
            "subtitle": _("Please jack out and touch grass."),
            "icon": "lightning",
        },
        {
            "title": _("Data Stream Corrupted"),
            "message": _("Hostile netrunner detected in the system"),
            "subtitle": _("Deploying countermeasures and black ICE..."),
            "icon": "shield-x",
        },
        {
            "title": _("Reality.exe Has Stopped Working"),
            "message": _("The simulation is experiencing a fatal exception"),
            "subtitle": _("Attempting to reload from last stable checkpoint..."),
            "icon": "arrow-clockwise",
        },
        # Horror/Cthulhu themed
        {
            "title": _("The Stars Are Wrong"),
            "message": _("Cosmic alignment has disrupted our servers"),
            "subtitle": _("When the stars are right, service will resume."),
            "icon": "stars",
        },
        {
            "title": _("Eldritch Horror Unleashed"),
            "message": _("Something ancient stirs in the server depths"),
            "subtitle": _("The Old Ones have awakened. Sanity checks required."),
            "icon": "emoji-dizzy-fill",
        },
        {
            "title": _("Reality Breach Detected"),
            "message": _("Non-Euclidean errors are cascading through the system"),
            "subtitle": _("The angles are all wrong. Physics.dll has failed."),
            "icon": "exclamation-triangle",
        },
        {
            "title": _("Whispers in the Code"),
            "message": _("The server speaks in tongues unknown to mortal programmers"),
            "subtitle": _("Iä! Iä! Server fhtagn!"),
            "icon": "chat-dots",
        },
        {
            "title": _("The Crawling Chaos"),
            "message": _("Nyarlathotep has possessed our infrastructure"),
            "subtitle": _("Madness spreads through every circuit..."),
            "icon": "virus",
        },
    ]

    selected = messages[secrets.randbelow(len(messages))]
    context = {
        "error_code": 500,
        "title": selected["title"],
        "message": selected["message"],
        "subtitle": selected["subtitle"],
        "icon": selected["icon"],
    }

    return render(request, "500_dynamic.html", context, status=500)
