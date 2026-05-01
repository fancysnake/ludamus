# Architecture

## Layers

| Layer | Location | Purpose |
| ----- | -------- | ------- |
| pacts | `pacts.py` | Protocols, DTOs (Pydantic), errors, enums, TypedDicts |
| specs | `specs/{subdomain}.py` | Business invariants — pure constants, no IO |
| mills | `mills.py` | Business logic, Django-free |
| links | `links/` | Repositories, UoW, external clients |
| gates | `gates/` | Views, forms, URLs, templatetags |
| inits | `inits.py` | DI container, middleware wiring |
| edges | `edges/` | settings, wsgi/asgi — outside GLIMPSE |
| adapters | `adapters/` | Legacy — new code goes into GLIMPSE layers |

## Import Rules

Enforced by `importlinter`:

```text
General flow (Y can import X):
pacts -> mills -> links -> gates -> inits

specs sits at the bottom alongside pacts, consumed only by mills:
pacts -> specs -> mills

Forbidden:
mills   ✗ gates, links, inits, edges, django
links   ✗ gates, mills, inits, specs, edges
gates   ✗ links, inits, specs, edges
inits   ✗ edges
specs   ✗ gates, links, inits, mills, edges, django
pacts   ✗ gates, links, inits, mills, specs, edges, django
```

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

## Repository Registry

Repositories are wired into a flat registry, internal to `inits/`, never
imported from gates:

```python
# inits/repositories.py
class Repositories:
    @cached_property
    def personal_data_fields(self) -> PersonalDataFieldRepository:
        return PersonalDataFieldRepository()

    @cached_property
    def proposal_categories(self) -> ProposalCategoryRepository:
        return ProposalCategoryRepository()
```

Buckets appear when the leaf count grows past ~12. Until then, stay flat.

## Services (mills)

Services take a `TransactionProtocol` plus the specific repo protocols they
actually touch — never the full UoW, never imports of concrete repos:

```python
# mills/chronology.py
class CFPPersonalDataFieldService:
    def __init__(
        self,
        transaction: TransactionProtocol,
        fields: PersonalDataFieldRepositoryProtocol,
        categories: ProposalCategoryRepositoryProtocol,
    ) -> None:
        self._transaction = transaction
        self._fields = fields
        self._categories = categories

    def create(self, event_pk: int, data, requirements) -> PersonalDataFieldDTO:
        with self._transaction.atomic():
            field = self._fields.create(event_pk, data)
            if requirements:
                self._categories.add_field_to_categories(field.pk, requirements)
        return field
```

Services own transactions (`transaction.atomic()`); views never start them.
Services return DTOs; views render them.

## Services Tree

Services are exposed to gates through a flat namespace at
`request.services.<service_name>`:

```python
# inits/services.py
class Services:
    @cached_property
    def personal_data_fields(self) -> CFPPersonalDataFieldService:
        return CFPPersonalDataFieldService(
            self._transaction,
            self._repos.personal_data_fields,
            self._repos.proposal_categories,
        )
```

The `ServicesProtocol` in `pacts/services.py` describes the navigation
shape. `ServiceInjectionMiddleware` attaches `request.services` per request.

## Views

Views are glue: parse forms, call services, render DTOs. They never reach
into repos or build services themselves. Type-hint request as
`RootRequestProtocol` (or a subdomain-specific request like `PanelRequest`):

```python
def get(self, request: PanelRequest, slug: str) -> TemplateResponse:
    service = request.services.personal_data_fields
    fields = service.list_summaries(event_pk)
    return TemplateResponse(
        request, "panel/personal-data-fields.html", {"fields": fields}
    )
```

## Strangler-fig migration

Two middleware run in parallel: the legacy `RepositoryInjectionMiddleware`
(attaches `request.di.uow`) and the new `ServiceInjectionMiddleware`
(attaches `request.services`). New code uses `request.services`. A single
view file picks one shape; never both in the same view.

Migration is per view file. The recipe lives in
[services-migration.md](services-migration.md). Once the last view migrates,
`RepositoryInjectionMiddleware` and `request.di.uow` are removed.

New code must use `request.services`. Do not extend the `request.di.uow`
surface — write a new mills service instead.

## Specs

Business invariants consumed only by mills. No IO, no Django.
Sliced by subdomain, mirroring pacts and mills:

```python
# specs/event.py
MAX_SESSIONS_PER_USER = 5
```

Pacts can define the structure; specs provide the values:

```python
# pacts/event.py
class SessionLimits(TypedDict):
    max_per_user: int

# specs/event.py
SESSION_LIMITS: SessionLimits = {"max_per_user": 5}
```

---

## Subdomains and Bounded Contexts

The application has four subdomains. Each subdomain
contains one or more bounded contexts with distinct
responsibilities, URL namespaces, templates, and DTOs.

<!-- markdownlint-disable MD013 -->

| Subdomain | Scope | Bounded contexts |
| --------- | ----- | ---------------- |
| Multiverse | Sphere and concepts depending only on Sphere | Panel |
| Chronology | Events, proposals/sessions, scheduling, venues, enrollment | Public Event Pages, CFP, Enrollment, Panel |
| Notice Board | Informal social gatherings decoupled from the formal event/session lifecycle | Encounters |
| Crowd | Authentication, profiles, delegate accounts | Auth, Profile |

<!-- markdownlint-enable MD013 -->

---

### Multiverse

Sphere-scoped configuration shared across the events
that live under a sphere. Holds `Sphere` itself plus
anything that depends only on Sphere (no Event coupling).

#### Bounded Context: Panel (Multiverse)

Sphere-scoped backoffice for sphere managers. Parallel
to `chronology/panel` (which is event-scoped) and uses
its own access mixin keyed off `current_sphere_id`
without an `EventContextMixin`.

- **URLs:** `/multiverse/sphere/<slug>/…`
  (namespace `multiverse:panel`)
- **Views:** `gates/web/django/multiverse/panel/views/…`
- **Templates:** `templates/multiverse/panel/`
- **Pacts/Mills/Specs:** `pacts/multiverse.py`,
  `mills/multiverse.py`, `specs/multiverse.py`
  (split into `multiverse/{context}.py` when big)
- **Access:** `SphereAccessMixin` (sphere-manager check
  via `request.di.uow.spheres.is_manager`)
- **First feature:** sphere-scoped import-connections CRUD
  ("Połączenia importu" subpage)

`Sphere` ORM models and repositories continue to live in
`links/db/django/models.py` and
`links/db/django/repositories.py` per the split-when-big
rule; they are not moved into a multiverse-named file.

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

#### Bounded Context: Panel (Chronology)

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
