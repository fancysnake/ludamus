# Architecture

## Layers

| Layer | Location | Purpose |
| ----- | -------- | ------- |
| pacts | `pacts.py` | Protocols, DTOs (Pydantic) |
| mills | `mills.py` | Business logic |
| links | `links/db/django/` | Repositories, UoW |
| gates | `gates/web/django/` | Views, forms (panel) |
| adapters | `adapters/web/django/` | Views, forms (other) |
| norms | `config/` | Settings |
| binds | `binds.py` | DI middleware |

## Import Rules

Enforced by `importlinter`:

```text
mills  ✗ gates, links, norms
links  ✗ gates, mills, norms
gates  ✗ links, norms
```

Inner layers can't import outer.

## Repository Pattern

```python
# links/db/django/repositories.py
class ProposalRepository(ProposalRepositoryProtocol):
    def read(self, pk: int) -> ProposalDTO:
        try:
            proposal = Proposal.objects.select_related("category").get(id=pk)
        except Proposal.DoesNotExist as exception:
            raise NotFoundError from exception
        return ProposalDTO.model_validate(proposal)
```

## Unit of Work

```python
# links/db/django/uow.py
class UnitOfWork(UnitOfWorkProtocol):
    @cached_property
    def proposals(self) -> ProposalRepository:
        return ProposalRepository()
```

Injected by middleware in `binds.py`. Views use `request.di.uow.proposals.read(id)`.

## Views

Use `TemplateResponse`, type hint request as `RootRequestProtocol`:

```python
def get(self, request: RootRequestProtocol, slug: str) -> TemplateResponse:
    event = request.di.uow.events.read(slug)
    return TemplateResponse(request, "panel/event.html", {"event": event})
```

Mixins: `PanelAccessMixin` (permissions), `EventContextMixin` (loads `request.context.current_event`).

## Services (mills)

Services take UoW via constructor:

```python
class PanelService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow
```

---

## Subdomains and Bounded Contexts

The application has three subdomains. Each subdomain
contains one or more bounded contexts with distinct
responsibilities, URL namespaces, templates, and DTOs.

---

### Chronology

Manages events, proposals/sessions, scheduling,
venues, and enrollment.

#### Bounded Context: Public Event Pages

What visitors see: event details, session list,
session cards.

- **URLs:** `/chronology/event/<slug>/`
  (namespace `chronology`)
- **Views:** `adapters/web/django/views.py` —
  `EventPageView`
- **Templates:** `templates/chronology/event.html`,
  `_session_card.html`, `session_tags.html`
- **DTOs:** `EventDTO`, `SessionDTO`,
  `SessionListItemDTO`, `TrackDTO`

#### Bounded Context: CFP (Call for Proposals)

The multi-step wizard through which facilitators
submit session proposals.

- **URLs:** `/chronology/session/propose/`
  (namespace `session`)
- **Views:**
  `gates/web/django/chronology/views.py` —
  `ProposeSessionPageView` and component views
  for each wizard step (category, personal data,
  time slots, session details, review, submit)
- **Templates:** `templates/chronology/propose/`
- **Service:** `ProposeSessionService` — resolves
  field requirements per category, creates
  `Facilitator`, persists `Session` and field
  values, rate-limits by IP
- **DTOs:** `ProposalCategoryDTO`,
  `SessionFieldRequirementDTO`,
  `PersonalFieldRequirementDTO`,
  `TimeSlotRequirementDTO`, `FacilitatorDTO`,
  `SessionData`

#### Bounded Context: Enrollment

Session sign-ups for authenticated users and
anonymous attendees; proposal acceptance by
organizers.

- **URLs:**
  `/chronology/session/<id>/enrollment/`,
  `/chronology/session/<id>/accept/`,
  `/chronology/anonymous/`
- **Views:** `adapters/web/django/views.py` —
  `SessionEnrollPageView`,
  `SessionEnrollmentAnonymousPageView`,
  `ProposalAcceptPageView`,
  `EventAnonymousActivateActionView`,
  `AnonymousLoadActionView`,
  `AnonymousResetActionView`
- **Templates:**
  `templates/chronology/enroll_select.html`,
  `anonymous_enroll.html`,
  `anonymous_manage.html`,
  `accept_proposal.html`
- **Services:** `AcceptProposalService`
  (transitions session → ACCEPTED, creates
  `AgendaItem`), `AnonymousEnrollmentService`
  (code-based anonymous user lookup)
- **DTOs:** `SessionParticipationDTO`,
  `EnrollmentConfigDTO`,
  `UserEnrollmentConfigDTO`,
  `VirtualEnrollmentConfig`, `AgendaItemDTO`

#### Bounded Context: Panel

The backoffice for event organisers. Covers every
aspect of event configuration and session management.

- **URLs:** `/panel/event/<slug>/…`
  (namespace `panel`)
- **Views:** `gates/web/django/panel.py`
  (~3 500 lines, 50+ view classes)
- **Templates:** `templates/panel/`
- **Service:** `PanelService` — event stats
  aggregation, cascade-safe entity deletion,
  time slot overlap validation

Internal areas within the panel (all under the
same bounded context):

<!-- markdownlint-disable MD013 -->

| Area | Views | Templates |
| ---- | ----- | --------- |
| Event settings | `EventSettingsPageView` | `settings.html` |
| Proposal categories | `CFPPageView` | `cfp-*.html` |
| Proposals / sessions | `ProposalsPageView` | `proposal-*.html` |
| Personal data fields | `PersonalDataFieldsPageView` | `personal-data-field-*.html` |
| Session fields | `SessionFieldsPageView` | `session-field-*.html` |
| Time slots | `TimeSlotsPageView` | `time-slot*.html` |
| Tracks | `TracksPageView` | `track-*.html` |
| Venues / Areas / Spaces | `VenuesPageView` | `venue-*.html` |
| Facilitators | `FacilitatorsPageView` | `facilitator-*.html` |

<!-- markdownlint-enable MD013 -->

---

### Notice Board

Informal social gathering system, decoupled from
the formal event/session lifecycle.

#### Bounded Context: Encounters

Users create one-off encounters (game sessions,
meetups) and others RSVP to join them. Includes
the public share page, RSVP actions, and calendar
exports.

- **URLs:** `/encounters/` (authenticated),
  `/e/<share_code>/` (public,
  namespace `notice-board`)
- **Views:**
  `gates/web/django/notice_board/views.py` —
  `EncountersIndexPageView`,
  `EncounterCreatePageView`,
  `EncounterEditPageView`,
  `EncounterDeleteActionView`,
  `EncounterDetailPageView`,
  `EncounterRSVPActionView`,
  `EncounterCancelRSVPActionView`,
  `EncounterQrView`, `EncounterIcsView`
- **Templates:** `templates/notice_board/`
- **Service:** `EncounterService` —
  `build_detail()` (encounter + RSVPs +
  computed availability), `build_index()`
  (upcoming/past split, own vs RSVP'd)
- **DTOs:** `EncounterDTO`,
  `EncounterRSVPDTO`,
  `EncounterDetailResult`,
  `EncounterIndexItem`,
  `EncounterIndexResult`, `EncounterData`
- **Repositories:** `EncounterRepository`,
  `EncounterRSVPRepository`
- **External integrations:** Google Calendar
  and Outlook deep links, iCalendar `.ics`
  export, QR code generation

---

### Crowd

Authentication, user profiles, and delegate
accounts.

#### Bounded Context: Auth

Auth0 OAuth login/logout. State token management
and JWT validation; user upsert on callback.

- **URLs:** `/crowd/auth0/`
  (namespace `auth0`)
- **Views:** `adapters/web/django/views.py` —
  `Auth0LoginActionView`,
  `Auth0LoginCallbackActionView`,
  `Auth0LogoutActionView`,
  `Auth0LogoutRedirectActionView`,
  `LoginRequiredPageView`
- **Templates:**
  `templates/crowd/login_required.html`
- **External integration:** Auth0 PKCE/state
  OAuth flow

#### Bounded Context: Profile

User profile management and delegate (connected)
accounts.

- **URLs:** `/crowd/profile/` and
  `/crowd/profile/connected-users/`
- **Views:** `adapters/web/django/views.py` —
  `ProfilePageView`,
  `ProfileAvatarPageView`,
  `ProfileConnectedUsersPageView`,
  `ProfileConnectedUserUpdateActionView`,
  `ProfileConnectedUserDeleteActionView`
- **Templates:**
  `templates/crowd/user/edit.html`,
  `avatar.html`, `connected.html`
- **DTOs:** `UserDTO`, `UserData`, `UserType`
  (`ACTIVE` / `CONNECTED` / `ANONYMOUS`)
- **Repositories:** `UserRepository`,
  `ConnectedUserRepository`
- **External integration:**
  `MembershipApiClient` (`links/ticket_api.py`)
  — fetches enrollment quotas; Gravatar
  (`links/gravatar.py`) — email-hash avatar
