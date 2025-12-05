
  Code Review: Backoffice and Permissions System

  Overview

  This review covers the implementation of a permission system with Clean Architecture principles. The changes include permission models, services, repositories, and panel views for managing roles and
  events.

  ---
  🟢 Strengths

  1. Clean Architecture Adherence

  - ✅ Excellent separation of concerns with DTOs in pacts.py, business logic in gears.py, and repositories in links/
  - ✅ Protocol-based design enables testability and future framework swaps
  - ✅ Identity Map pattern (Storage) properly implemented
  - ✅ Unit of Work pattern correctly aggregates repositories

  2. Permission System Design

  - ✅ Registry pattern for permission checks is extensible and follows Open/Closed Principle
  - ✅ Wildcard support (Action.ALL, ResourceType.ALL) adds flexibility
  - ✅ Clear separation between Roles (templates) and UserPermissions (concrete grants)
  - ✅ Audit trail with granted_by, granted_from_role, granted_at

  3. Type Safety

  - ✅ Strong typing with Pydantic DTOs and TypedDict
  - ✅ StrEnum for Action and ResourceType prevents magic strings
  - ✅ Protocol definitions enable type-safe dependency injection

  ---
  🔴 Critical Issues

  ~~1. Violation of Repository Pattern (gears.py:112-133)~~ ✅ **FIXED**

  **Status:** Fixed by adding `get_sphere_id()` methods to repositories
  - Added protocols in `pacts.py` for EventRepository, ProposalRepository, SessionRepository
  - Implemented methods in `links/db/django/repositories.py`
  - Refactored `get_sphere_id_for_resource()` to delegate to repository methods
  - Updated unit tests
  - All tests passing ✅

  ---
  ~~2. Broken Permission Check Logic (gears.py:112-133)~~ ✅ **FIXED**

  **Status:** Fixed as part of Repository Pattern fix
  - Correct repositories now used (events.get_sphere_id instead of proposals.read_event)
  - Correct fields accessed (event.sphere_id instead of event.pk)
  - Permission checks now resolve sphere context correctly ✅

  ---
  ~~3. Missing Transaction Boundaries (repositories.py:419-443)~~ ✅ **FIXED**

  **Status:** Fixed by adding `@transaction.atomic` to multi-operation methods only

  **Analysis:**
  - Django has `ATOMIC_REQUESTS = True` (settings.py:269)
  - All view requests are already wrapped in transactions
  - Services use `UnitOfWork.atomic()` when orchestrating multiple operations

  **Solution:**
  Only methods with **multiple DB operations** need `@transaction.atomic`:
  - ✅ `SessionRepository.create()` - Creates session + sets M2M tags (2 operations)
  - ✅ `ConnectedUserRepository.update()` - Updates + reads back (2 operations)

  **Single-operation methods rely on `ATOMIC_REQUESTS`:**
  - All other create/update/delete methods
  - Already covered by request-level transaction
  - No unnecessary savepoint overhead

  This follows Django best practices and avoids redundant nested transactions ✅

  ---
  ~~4. Cache Invalidation Issues (repositories.py:386, 395, 403)~~ ✅ **FIXED**

  **Status:** Fixed by removing permission caching entirely

  **Analysis:**
  - `list_user_permissions()` was the only method using cache - **never called in codebase**
  - `has_permission()` and `has_any_permission_in_sphere()` already use direct `.exists()` queries ✅
  - Permission checks are fast (indexed queries) - caching unnecessary
  - Cache was request-scoped anyway (short-lived)

  **Solution:**
  Removed from `Storage`:
  - ❌ `roles: dict[int, Role]`
  - ❌ `role_permissions: dict[int, list[RolePermission]]`
  - ❌ `user_permissions: dict[tuple[int, int], list[UserPermission]]`

  **Benefits:**
  - ✅ No cache invalidation bugs
  - ✅ Simpler code (removed ~20 cache operations)
  - ✅ Always fresh data from DB
  - ✅ No performance impact (queries are already optimized)

  Permission data now always comes directly from the database ✅

  ---
  🟡 SOLID Violations

  1. Single Responsibility Principle (gears.py:209-280) ⚠️ **TODO**

  AuthorizationService has multiple responsibilities:
  - Permission checking (can(), require())
  - Sphere manager bypass logic
  - Derived permission registry lookups
  - Superuser/staff checks

  Recommendation: Extract sphere manager and superuser checks into separate strategies:

  class PermissionStrategy(Protocol):
      def check(self, user_id: int, action: Action, resource_type: ResourceType, resource_id: int) -> bool: ...

  class DirectPermissionStrategy:
      def check(self, ...) -> bool:
          return uow.user_permissions.has_permission(...)

  class SphereManagerStrategy:
      def check(self, ...) -> bool:
          return uow.spheres.is_manager(...)

  class AuthorizationService:
      def __init__(self, strategies: list[PermissionStrategy]):
          self._strategies = strategies

      def can(self, ...) -> bool:
          return any(s.check(...) for s in self._strategies)

  ---
  2. Open/Closed Principle Violation (repositories.py:452-465) ⚠️ **TODO**

  @staticmethod
  def has_permission(...) -> bool:
      return UserPermission.objects.filter(...).exists()

  Problem: Static method cannot be extended or mocked properly. Violates OCP and makes testing harder.

  Fix: Remove @staticmethod and make it instance method:
  def has_permission(self, ...) -> bool:
      return UserPermission.objects.filter(...).exists()

  ---
  3. Liskov Substitution Principle (gears.py:282-322) ⚠️ **TODO**

  RoleAssignmentService violates LSP by doing authorization internally:

  def assign_role(self, ...) -> list[UserPermissionDTO]:
      auth = AuthorizationService(self._context, self._uow)
      auth.require(Action.MANAGE_PERMISSIONS, ...)  # ❌ Mixing concerns
      # ... business logic

  Problem: The service does both authorization AND business logic. This makes it impossible to reuse the role assignment logic in contexts where authorization is already checked.

  Solution: Separate authorization from business logic:
  # In views:
  auth.require(Action.MANAGE_PERMISSIONS, ...)
  service.assign_role(user_id, role_id, ...)

  # In service:
  def assign_role(self, ...) -> list[UserPermissionDTO]:
      # Pure business logic only

  ---
  4. Dependency Inversion Principle (repositories.py:4-17) ℹ️ **KNOWN DEBT**

  from ludamus.adapters.db.django.models import (
      AgendaItem, Event, Proposal, Role, RolePermission, Session,
      Space, Sphere, TimeSlot, UserPermission,
  )

  Problem: Repositories (in links/) depend directly on Django ORM models (in adapters/). According to Clean Architecture, both should depend on abstractions in pacts/.

  Current dependency flow:
  links/ → adapters/db/django/models.py  ❌ Wrong

  Correct flow:
  links/ → pacts/  ✅
  adapters/ → pacts/  ✅

  Note: This is a known architectural debt being migrated. The Storage dataclass already violates this by importing Django models.

  ---
  🟠 Code Quality Issues

  1. Inconsistent Error Handling (repositories.py:361-372) ⚠️ **TODO**

  def update(self, role_id: int, role_data: RoleData) -> RoleDTO:
      role = Role.objects.get(id=role_id)  # ❌ Can raise DoesNotExist
      if role.is_system:
          raise ValueError("Cannot update system role")
      # ...

  Problem: Inconsistent with other repositories that wrap DoesNotExist in NotFoundError.

  Fix:
  def update(self, role_id: int, role_data: RoleData) -> RoleDTO:
      try:
          role = Role.objects.get(id=role_id)
      except Role.DoesNotExist as exception:
          raise NotFoundError from exception

      if role.is_system:
          raise ValueError("Cannot update system role")

  ---
  2. Code Duplication in Views (views.py:1961-1995) ⚠️ **TODO**

  All panel views have identical permission checks:

  def dispatch(self, request: AuthenticatedRootRequest, *args, **kwargs) -> HttpResponse:
      auth = AuthorizationService(request.context, request.uow)
      if not auth.has_any_permission_in_sphere():
          messages.error(request, _("You don't have permission..."))
          return redirect("web:index")
      return super().dispatch(request, *args, **kwargs)

  Solution: Create a mixin:
  class PanelPermissionMixin:
      def dispatch(self, request: AuthenticatedRootRequest, *args, **kwargs) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          if not auth.has_any_permission_in_sphere():
              messages.error(request, _("You don't have permission..."))
              return redirect("web:index")
          return super().dispatch(request, *args, **kwargs)

  class PanelIndexPageView(LoginRequiredMixin, PanelPermissionMixin, TemplateView):
      template_name = "panel/index.html"
      # dispatch() inherited from mixin

  ---
  3. Missing Input Validation (views.py:2033-2068) ⚠️ **TODO**

  def post(request: AuthenticatedRootRequest) -> HttpResponse:
      name = request.POST.get("name", "").strip()
      description = request.POST.get("description", "").strip()

      if not name:
          messages.error(request, _("Role name is required."))
          return redirect("web:panel:users")

  Missing validations:
  - Name length (max 100 chars per model)
  - Name uniqueness within sphere
  - XSS sanitization
  - SQL injection (handled by ORM but worth noting)

  Recommendation: Use Django Forms:
  class RoleForm(forms.Form):
      name = forms.CharField(max_length=100, required=True)
      description = forms.CharField(widget=forms.Textarea, required=False)

  def post(request):
      form = RoleForm(request.POST)
      if not form.is_valid():
          for error in form.errors.values():
              messages.error(request, error)
          return redirect("web:panel:users")
      # ...

  ---
  4. Incomplete Permission Check (gears.py:192-202) ⚠️ **TODO**

  @PermissionCheckRegistry.register(Action.APPROVE, ResourceType.PROPOSAL)
  @PermissionCheckRegistry.register(Action.REJECT, ResourceType.PROPOSAL)
  def can_manage_proposal_via_category(
      _uow: UnitOfWorkProtocol,
      _user_id: int,
      _resource_type: ResourceType,
      _resource_id: int,
  ) -> bool:
      # FIXME: Need proposal.category_id and proper sphere resolution
      return False  # Placeholder

  Problem: Registered check always returns False, breaking category-based proposal management.

  Impact: Users with category permissions cannot approve/reject proposals.

  Solution: Implement the actual logic:
  def can_manage_proposal_via_category(
      uow: UnitOfWorkProtocol,
      user_id: int,
      resource_type: ResourceType,
      resource_id: int,
  ) -> bool:
      proposal = uow.proposals.read(resource_id)
      # Assuming proposals have category_id (need to add to ProposalDTO)
      return uow.user_permissions.has_permission(
          user_id,
          get_sphere_id_for_resource(uow, ResourceType.PROPOSAL, resource_id),
          Action.MANAGE,
          ResourceType.CATEGORY,
          proposal.category_id,  # ❌ Not in ProposalDTO
      )

  ---
  🔵 Python Idiom Issues

  1. Unnecessary Underscore Prefix (repositories.py:269) ℹ️ **OPTIONAL**

  def _read_user(self, manager_slug: str, user_slug: str) -> User:

  Problem: Private method is only used internally, but the naming suggests it's "private" when Python doesn't have true private methods.

  Recommendation: Keep underscore for truly internal helpers, but this is borderline. Consider if it should be exposed in the protocol.

  ---
  2. Type Annotation Inconsistency (gears.py:26) ℹ️ **OPTIONAL**

  if TYPE_CHECKING:
      PermissionCheckFunc = Callable[[UnitOfWorkProtocol, int, ResourceType, int], bool]

  Problem: Type alias only exists under TYPE_CHECKING, but it's used in runtime code (ClassVar annotation). This works but is unconventional.

  Better:
  from typing import TypeAlias

  PermissionCheckFunc: TypeAlias = Callable[
      [UnitOfWorkProtocol, int, ResourceType, int], bool
  ]

  ---
  3. Mutable Default Argument (pacts.py:198)

  ACTION_APPLICABLE_TO: dict[Action, list[ResourceType]] = {
      Action.READ: [ResourceType.ALL],  # ✅ OK - module constant
      # ...
  }

  Analysis: This is safe because it's a module-level constant, not a function default. ✅

  ---
  4. Implicit Boolean Conversion (repositories.py:86-92)

  def is_manager(self, sphere_id: int, user_slug: str) -> bool:
      managers = self._storage.sphere_managers[sphere_id].values()
      if not managers:  # ✅ Pythonic
          for manager in self._storage.spheres[sphere_id].managers.all():
              self._storage.sphere_managers[sphere_id][manager.slug] = manager

      return user_slug in self._storage.sphere_managers[sphere_id]  # ✅ Clean

  Analysis: Excellent use of truthiness and in operator. ✅

  ---
  📊 Test Coverage

  Strengths:

  - ✅ Comprehensive unit tests for permission services
  - ✅ Registry pattern properly tested with cleanup
  - ✅ Mock usage follows best practices
  - ✅ Updated tests for get_sphere_id_for_resource refactoring

  Gaps: ⚠️ **TODO**

  - ❌ No tests for RoleRepository
  - ❌ No tests for UserPermissionRepository
  - ❌ No tests for EventRepository
  - ❌ No integration tests for permission checks with real database
  - ❌ No tests for cache invalidation scenarios

  ---
  🎯 Summary & Priority Fixes

  ## ✅ Completed

  1. ✅ **Fix get_sphere_id_for_resource() logic** - Repository Pattern violation fixed
  2. ✅ **Fix broken permission check logic** - Sphere resolution now correct
  3. ✅ **Add transaction boundaries** - Multi-operation methods use `@transaction.atomic`, single operations rely on `ATOMIC_REQUESTS`
  4. ✅ **Fix cache invalidation issues** - Removed permission caching entirely

  ## Critical (Fix Immediately):

  5. ⚠️ Implement placeholder permission check for proposal category management

  ## High Priority:

  6. ⚠️ Remove `@staticmethod` from repository methods
  7. ⚠️ Add consistent error handling (wrap `DoesNotExist`)
  8. ⚠️ Create DRY mixin for panel permission checks
  9. ⚠️ Add input validation via Django Forms

  ## Medium Priority:

  10. ⚠️ Refactor `AuthorizationService` with Strategy pattern
  11. ⚠️ Separate authorization from business logic in `RoleAssignmentService`
  12. ⚠️ Add missing test coverage for repositories

  ## Low Priority (Architecture Debt):

  13. ℹ️ Break dependency of repositories on Django models (migrate to pacts/) - **Known Debt**
  14. ℹ️ Consider TypeAlias for PermissionCheckFunc
  15. ℹ️ Review unnecessary underscore prefixes

  ---
  🏆 Overall Assessment

  **Score: 8.5/10** (Updated from 7/10 after fixes)

  The permission system follows Clean Architecture principles well and demonstrates good understanding of SOLID principles.

  **✅ Recently Fixed:**
  - Critical logic bugs in sphere resolution
  - Repository Pattern violation
  - Broken permission checks
  - Transaction boundaries (using `ATOMIC_REQUESTS` + selective `@transaction.atomic`)
  - Cache invalidation issues (removed permission caching entirely)

  **⚠️ Remaining Issues:**
  - Some SOLID violations (SRP, LSP, OCP)
  - Code duplication in views
  - Incomplete permission check implementation

  The codebase shows promise and the architecture is sound. The recent fixes improve reliability, simplicity, and data integrity significantly. The permission system is now cleaner with no caching complexity. With the remaining fixes above, this would be production-ready code. The use of protocols, DTOs, and the repository pattern is exemplary.

  ---
  🎨 New Features Review (Latest Commit)

  ## Backoffice Panel System

  **What Was Added:**
  - Complete admin panel UI at `/panel/` with navigation
  - Event management (create, update, delete)
  - Role management (create, update, delete)
  - Role permission assignment interface
  - User permission overview
  - Settings page for sphere configuration

  **Implementation Quality:**

  ### ✅ Strengths:
  1. **Consistent URL Structure** - Follows project conventions from `docs/CODE_LAYOUT.md`
     - Pages: `/panel/events/`, `/panel/users/`, `/panel/settings/`
     - Actions: `/panel/do/event-create`, `/panel/do/role-delete`
  2. **Clean Separation** - Views properly use UoW pattern via `request.uow`
  3. **Authorization Integration** - All panel views use `AuthorizationService`
  4. **User Feedback** - Good use of Django messages for success/error states
  5. **Template Organization** - Panel templates properly organized in `templates/panel/`

  ### 🔴 Critical Issues:

  #### 1. Permission Bypass in All Panel Views (views.py:1961-2395) 🚨 **SECURITY RISK**

  **Current Implementation:**
  ```python
  def dispatch(self, request: AuthenticatedRootRequest, *args, **kwargs) -> HttpResponse:
      auth = AuthorizationService(request.context, request.uow)
      if not auth.has_any_permission_in_sphere():
          messages.error(request, _("You don't have permission..."))
          return redirect("web:index")
      return super().dispatch(request, *args, **kwargs)
  ```

  **Problem:** ALL panel views only check `has_any_permission_in_sphere()` - this allows ANY user with ANY permission to access ALL panel features.

  **Example Attack Scenario:**
  1. User gets READ permission on a single proposal
  2. `has_any_permission_in_sphere()` returns `True`
  3. User can now CREATE/DELETE events, roles, and permissions! 🚨

  **Impact:** Complete authorization bypass - users can perform actions they have no permission for.

  **Fix Required:**
  - **Event views** should check: `auth.require(Action.MANAGE, ResourceType.EVENT, event_id)`
  - **Role views** should check: `auth.require(Action.MANAGE_PERMISSIONS, ResourceType.SPHERE, sphere_id)`
  - **Delete operations** should verify DELETE permission

  **Correct Implementation:**
  ```python
  class PanelEventUpdateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)

          # ✅ CORRECT: Check specific permission before action
          auth.require(Action.UPDATE, ResourceType.EVENT, event_id)

          # ... perform update
  ```

  #### 2. Missing CSRF Protection (views.py:2033-2395) 🚨 **SECURITY RISK**

  **Problem:** Action views use `View` instead of Django's CSRF-protected views.

  **Current:**
  ```python
  class PanelEventDeleteActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
          # ❌ No CSRF protection!
  ```

  **Fix:** Either add `@method_decorator(csrf_protect, name='dispatch')` or use forms with `{% csrf_token %}`

  #### 3. SQL Injection Risk via Unvalidated Input (views.py:2247-2300) ⚠️ **MEDIUM RISK**

  **Current:**
  ```python
  name = request.POST.get("name", "").strip()
  description = request.POST.get("description", "").strip()

  # Only checks if name exists
  if not name:
      messages.error(request, _("Event name is required."))
      return redirect("web:panel:events")

  # Directly creates event with unvalidated data
  request.uow.events.create(EventData(
      sphere_id=request.context.current_sphere_id,
      name=name,  # ❌ No length validation
      description=description,  # ❌ No XSS sanitization
      # ...
  ))
  ```

  **Problems:**
  - No max length validation (DB field has max_length=200)
  - No XSS sanitization
  - No uniqueness checks
  - Could cause database errors or malicious input storage

  **Fix:** Use Django Forms:
  ```python
  class EventForm(forms.Form):
      name = forms.CharField(max_length=200, required=True)
      description = forms.CharField(widget=forms.Textarea, required=False)
      # ... other fields

  def post(self, request):
      form = EventForm(request.POST)
      if not form.is_valid():
          for error in form.errors.values():
              messages.error(request, error)
          return redirect("web:panel:events")

      cleaned_data = form.cleaned_data
      # Now safe to use
  ```

  ### 🟡 Code Quality Issues:

  #### 4. Extreme Code Duplication (views.py:1955-2395)

  **Problem:** Identical `dispatch()` method copied 11 times across all panel views.

  **Lines of duplicated code:** ~150 lines

  **Fix:** Create a reusable mixin (already documented in existing CR.md TODO)

  #### 5. Inconsistent Error Handling (views.py:2247-2395)

  **Example 1 - No error handling:**
  ```python
  def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
      event = request.uow.events.read(event_id)  # ❌ Can raise NotFoundError
      # ... no try/except
  ```

  **Example 2 - Partial validation:**
  ```python
  if not name:
      messages.error(request, _("Event name is required."))
      return redirect("web:panel:events")
  # ❌ But doesn't validate other required fields like start_time, end_time
  ```

  **Fix:** Add consistent error handling and validation for all inputs.

  #### 6. Transaction Boundary Confusion (views.py:2354-2375)

  ```python
  def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
      with request.uow.atomic():  # ✅ Good
          event = request.uow.events.read(event_id)
          request.uow.events.delete(event_id)
  ```

  **Analysis:**
  - ✅ Uses `uow.atomic()` correctly
  - ⚠️ But `ATOMIC_REQUESTS = True` means view is already in transaction
  - ℹ️ Creates nested transaction (savepoint) - unnecessary but not harmful
  - 🤔 Consider: Is the `read()` needed before `delete()`? Could just delete directly.

  ### 🔵 Architecture & Design:

  #### 7. Breaking Clean Architecture Layering (views.py:1955+)

  **Problem:** Views (gates layer) contain business logic that should be in gears layer.

  **Example - Event Creation Logic in View:**
  ```python
  def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
      # ❌ View parsing dates, building slugs, validating business rules
      start_time_str = request.POST.get("start_time", "").strip()
      end_time_str = request.POST.get("end_time", "").strip()

      start_time = timezone.datetime.fromisoformat(start_time_str)
      end_time = timezone.datetime.fromisoformat(end_time_str)

      slug = slugify(unidecode(name))

      # ❌ Business validation in view
      if start_time >= end_time:
          messages.error(request, _("Start time must be before end time."))
          return redirect("web:panel:events")
  ```

  **Correct Architecture:**
  ```python
  # In gears.py - Business logic layer
  class EventManagementService:
      def create_event(self, context, name, start_time, end_time, ...) -> EventDTO:
          # Validation
          if start_time >= end_time:
              raise ValueError("Start time must be before end time")

          # Business logic
          slug = self._generate_slug(name)

          # Data creation
          return self._uow.events.create(EventData(...))

  # In views.py - Presentation layer
  def post(self, request):
      try:
          service = EventManagementService(request.context, request.uow)
          event = service.create_event(...)
          messages.success(request, _("Event created successfully."))
      except ValueError as e:
          messages.error(request, str(e))
  ```

  **Benefits:**
  - ✅ Business logic reusable (API, CLI, tests)
  - ✅ Views stay thin (just HTTP handling)
  - ✅ Easier to test business logic
  - ✅ Follows Single Responsibility Principle

  #### 8. Backoffice Templates Not Listed in Review

  **Files:**
  - `backoffice/categories.html`
  - `backoffice/door-cards.html`
  - `backoffice/proposals.html`
  - `backoffice/venues.html`
  - `backoffice/index.html`
  - `backoffice/organizers.html`
  - `backoffice/sphere-settings.html`
  - `backoffice/timetable.html`
  - `backoffice/settings.html`
  - `backoffice/hosts.html`
  - `backoffice/changelog.html`

  **Question:** Are these templates connected to any views? No URLs reference them in the diff.

  **Recommendation:** Either:
  1. Implement the views for these templates
  2. Remove unused templates to avoid confusion
  3. Document if they're work-in-progress for future features

  ## Database Schema Review

  ### ✅ Excellent Design:

  **Migration 0026:**
  - Clean foreign key relationships
  - Proper unique constraints on `Role` (sphere + name)
  - Proper unique constraints on `RolePermission` (role + action + resource_type)
  - Good indexing on `UserPermission` lookup fields
  - Audit trail fields (`granted_by`, `granted_from_role`, `granted_at`)
  - System role protection via `is_system` flag

  **No issues found in database schema** ✅

  ## Documentation Quality

  ### ✅ Excellent:

  **CLAUDE.md updates:**
  - Comprehensive permission system documentation
  - Clear examples of permission checking
  - Explanation of role assignment workflow
  - Permission hierarchy explained
  - Management command documented
  - Design principles articulated

  **This is exemplary documentation** ✅

  ## Summary of New Issues

  ### 🚨 Critical (Fix Before Merge):
  1. **Authorization bypass in all panel views** - Users can perform actions without proper permissions
  2. **Missing CSRF protection** - Vulnerable to CSRF attacks
  3. **Unvalidated user input** - Risk of XSS and database errors

  ### ⚠️ High Priority:
  4. **Extreme code duplication** - 11 identical `dispatch()` methods
  5. **Inconsistent error handling** - Some views handle errors, others don't
  6. **Business logic in views** - Violates Clean Architecture separation

  ### ℹ️ Medium Priority:
  7. **Unnecessary nested transactions** - Minor performance impact
  8. **Orphaned template files** - 11 backoffice HTML files with no views

  ## Updated Overall Score

  **Score: 6.5/10** (Decreased from 8.5/10)

  **Reason for decrease:** While the core permission system architecture is excellent (8.5/10), the panel views introduce critical security vulnerabilities that must be addressed before this can go to production.

  **Path to 9/10:**
  1. Fix critical security issues (authorization bypass, CSRF, input validation)
  2. Extract business logic from views to services
  3. Eliminate code duplication with mixins
  4. Add comprehensive integration tests for panel views
  5. Clean up orphaned templates

  **Current State:** Permission system foundation is solid, but panel implementation needs security hardening and architectural cleanup.

  ---
  📋 Complete TODO List - All Fixes Needed

  ## 🚨 CRITICAL - Fix Before Merge (Security Issues)

  ### 1. Fix Authorization Bypass in Panel Views
  **Location:** `src/ludamus/adapters/web/django/views.py:1961-2395`
  **Issue:** All panel views only check `has_any_permission_in_sphere()` instead of specific permissions
  **Impact:** Users with ANY permission can perform ALL actions
  **Fix:**
  ```python
  # Event views
  class PanelEventCreateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          auth.require(Action.CREATE, ResourceType.EVENT, request.context.current_sphere_id)
          # ... rest of implementation

  class PanelEventUpdateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          auth.require(Action.UPDATE, ResourceType.EVENT, event_id)
          # ... rest of implementation

  class PanelEventDeleteActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          auth.require(Action.DELETE, ResourceType.EVENT, event_id)
          # ... rest of implementation

  # Role/Permission views
  class PanelRoleCreateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          auth.require(Action.MANAGE_PERMISSIONS, ResourceType.SPHERE, request.context.current_sphere_id)
          # ... rest of implementation

  # Similar fixes for:
  # - PanelRoleUpdateActionView
  # - PanelRoleDeleteActionView
  # - PanelRolePermissionAddActionView
  # - PanelRolePermissionRemoveActionView
  ```

  ### 2. Add CSRF Protection to All Action Views
  **Location:** `src/ludamus/adapters/web/django/views.py:2033-2395`
  **Issue:** POST endpoints lack CSRF validation
  **Impact:** Vulnerable to CSRF attacks
  **Fix Option 1 - Decorator:**
  ```python
  from django.views.decorators.csrf import csrf_protect
  from django.utils.decorators import method_decorator

  @method_decorator(csrf_protect, name='dispatch')
  class PanelEventCreateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
          # ... implementation
  ```
  **Fix Option 2 - Django Forms (Recommended):**
  ```python
  # Use Django Forms which include CSRF tokens automatically
  # See Fix #3 below
  ```

  ### 3. Add Input Validation with Django Forms
  **Location:** `src/ludamus/adapters/web/django/views.py:2247-2395`
  **Issue:** Unvalidated user input passed to database
  **Impact:** XSS risk, database errors, no length validation
  **Fix:**
  ```python
  # Create forms.py in adapters/web/django/
  from django import forms

  class EventForm(forms.Form):
      name = forms.CharField(max_length=200, required=True)
      description = forms.CharField(widget=forms.Textarea, required=False)
      slug = forms.SlugField(max_length=200, required=True)
      start_time = forms.DateTimeField(required=True)
      end_time = forms.DateTimeField(required=True)
      publication_time = forms.DateTimeField(required=False)
      proposal_start_time = forms.DateTimeField(required=False)
      proposal_end_time = forms.DateTimeField(required=False)

      def clean(self):
          cleaned_data = super().clean()
          start = cleaned_data.get('start_time')
          end = cleaned_data.get('end_time')

          if start and end and start >= end:
              raise forms.ValidationError("Start time must be before end time")

          return cleaned_data

  class RoleForm(forms.Form):
      name = forms.CharField(max_length=100, required=True)
      description = forms.CharField(widget=forms.Textarea, required=False)

  # Use in views:
  class PanelEventCreateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
          form = EventForm(request.POST)
          if not form.is_valid():
              for field, errors in form.errors.items():
                  for error in errors:
                      messages.error(request, f"{field}: {error}")
              return redirect("web:panel:events")

          cleaned_data = form.cleaned_data
          # Now safe to use cleaned_data
  ```

  ## ⚠️ HIGH PRIORITY - Fix Soon

  ### 4. Implement Placeholder Permission Check
  **Location:** `src/ludamus/gears.py:190-200`
  **Issue:** `can_manage_proposal_via_category()` always returns False
  **Impact:** Users with category permissions cannot approve/reject proposals
  **Prerequisites:** Need to add `category_id` to `ProposalDTO`
  **Fix:**
  ```python
  # Step 1: Add category_id to ProposalDTO in pacts.py
  class ProposalDTO(BaseModel):
      model_config = ConfigDict(from_attributes=True)

      creation_time: datetime
      description: str
      host_id: int
      min_age: int
      needs: str
      participants_limit: int
      pk: int
      requirements: str
      session_id: int | None
      title: str
      category_id: int  # ← Add this field

  # Step 2: Implement the check in gears.py
  @PermissionCheckRegistry.register(Action.APPROVE, ResourceType.PROPOSAL)
  @PermissionCheckRegistry.register(Action.REJECT, ResourceType.PROPOSAL)
  def can_manage_proposal_via_category(
      uow: UnitOfWorkProtocol,
      user_id: int,
      resource_type: ResourceType,
      resource_id: int,
  ) -> bool:
      """User can approve/reject proposal if they can manage its category"""
      proposal = uow.proposals.read(resource_id)
      sphere_id = get_sphere_id_for_resource(uow, ResourceType.PROPOSAL, resource_id)

      return uow.user_permissions.has_permission(
          user_id,
          sphere_id,
          Action.MANAGE,
          ResourceType.CATEGORY,
          proposal.category_id,
      )
  ```

  ### 5. Remove @staticmethod from Repository Methods
  **Location:** `src/ludamus/links/db/django/repositories.py:447-473`
  **Issue:** Static methods violate OCP and make testing harder
  **Impact:** Cannot be extended or properly mocked
  **Fix:**
  ```python
  # Change from:
  @staticmethod
  def has_permission(
      user_id: int,
      sphere_id: int,
      action: Action,
      resource_type: ResourceType,
      resource_id: int,
  ) -> bool:
      return UserPermission.objects.filter(...).exists()

  # To:
  def has_permission(
      self,
      user_id: int,
      sphere_id: int,
      action: Action,
      resource_type: ResourceType,
      resource_id: int,
  ) -> bool:
      return UserPermission.objects.filter(...).exists()

  # Same for has_any_permission_in_sphere()
  def has_any_permission_in_sphere(self, user_id: int, sphere_id: int) -> bool:
      return UserPermission.objects.filter(
          user_id=user_id, sphere_id=sphere_id
      ).exists()
  ```

  ### 6. Add Consistent Error Handling to Repository Updates
  **Location:** `src/ludamus/links/db/django/repositories.py:372-395`
  **Issue:** Inconsistent error handling - some wrap DoesNotExist, others don't
  **Fix:**
  ```python
  def update(self, role_id: int, role_data: RoleData) -> RoleDTO:
      try:
          role = Role.objects.get(id=role_id)
      except Role.DoesNotExist as exception:
          raise NotFoundError from exception

      if role.is_system:
          raise ValueError("Cannot update system role")

      # ... rest of implementation

  def delete(self, role_id: int) -> None:
      try:
          role = Role.objects.get(id=role_id)
      except Role.DoesNotExist as exception:
          raise NotFoundError from exception

      if role.is_system:
          raise ValueError("Cannot delete system role")

      role.delete()
  ```

  ### 7. Create PanelPermissionMixin to Eliminate Code Duplication
  **Location:** `src/ludamus/adapters/web/django/views.py:1955-2395`
  **Issue:** Identical `dispatch()` method copied 11 times (~150 lines)
  **Fix:**
  ```python
  # Add mixin at top of views.py
  class PanelPermissionMixin:
      """Mixin for panel views requiring any permission in sphere"""

      def dispatch(self, request: AuthenticatedRootRequest, *args, **kwargs) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          if not auth.has_any_permission_in_sphere():
              messages.error(
                  request,
                  _("You don't have permission to access the panel for this sphere.")
              )
              return redirect("web:index")
          return super().dispatch(request, *args, **kwargs)

  # Then use in all page views (not action views, they need specific checks):
  class PanelIndexPageView(LoginRequiredMixin, PanelPermissionMixin, TemplateView):
      template_name = "panel/index.html"
      # dispatch() inherited from mixin

  class PanelSettingsPageView(LoginRequiredMixin, PanelPermissionMixin, TemplateView):
      template_name = "panel/settings.html"
      # dispatch() inherited from mixin

  # Remove dispatch() from all 11 views that only show pages (not actions)
  ```

  ### 8. Add Error Handling to All Action Views
  **Location:** `src/ludamus/adapters/web/django/views.py:2247-2395`
  **Issue:** Missing try/except for NotFoundError and other exceptions
  **Fix:**
  ```python
  from ludamus.pacts import NotFoundError

  class PanelEventUpdateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest, event_id: int) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)

          try:
              auth.require(Action.UPDATE, ResourceType.EVENT, event_id)
              event = request.uow.events.read(event_id)

              # ... validation and update logic

              messages.success(request, _("Event updated successfully."))
              return redirect("web:panel:events")

          except NotFoundError:
              messages.error(request, _("Event not found."))
              return redirect("web:panel:events")
          except PermissionDenied:
              messages.error(request, _("You don't have permission to update this event."))
              return redirect("web:panel:events")
          except ValueError as e:
              messages.error(request, str(e))
              return redirect("web:panel:events")
  ```

  ### 9. Extract Business Logic from Views to Services
  **Location:** `src/ludamus/adapters/web/django/views.py:2247-2395`
  **Issue:** Views contain business logic (date parsing, slug generation, validation)
  **Impact:** Violates Clean Architecture, logic not reusable
  **Fix:**
  ```python
  # Add to gears.py
  class EventManagementService:
      def __init__(self, context: AuthenticatedRequestContext, uow: UnitOfWorkProtocol):
          self._context = context
          self._uow = uow

      def create_event(
          self,
          name: str,
          description: str,
          start_time: datetime,
          end_time: datetime,
          publication_time: datetime | None = None,
          proposal_start_time: datetime | None = None,
          proposal_end_time: datetime | None = None,
      ) -> EventDTO:
          # Validation
          if start_time >= end_time:
              raise ValueError("Start time must be before end time")

          # Business logic
          slug = slugify(unidecode(name))

          # Create event
          return self._uow.events.create(
              EventData(
                  sphere_id=self._context.current_sphere_id,
                  name=name,
                  slug=slug,
                  description=description,
                  start_time=start_time,
                  end_time=end_time,
                  publication_time=publication_time,
                  proposal_start_time=proposal_start_time,
                  proposal_end_time=proposal_end_time,
              )
          )

      def update_event(self, event_id: int, **kwargs) -> EventDTO:
          # Similar pattern for updates
          pass

  # Simplify view to just HTTP handling:
  class PanelEventCreateActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
          form = EventForm(request.POST)
          if not form.is_valid():
              for field, errors in form.errors.items():
                  for error in errors:
                      messages.error(request, f"{field}: {error}")
              return redirect("web:panel:events")

          try:
              auth = AuthorizationService(request.context, request.uow)
              auth.require(Action.CREATE, ResourceType.EVENT, request.context.current_sphere_id)

              service = EventManagementService(request.context, request.uow)
              event = service.create_event(**form.cleaned_data)

              messages.success(request, _("Event created successfully."))
              return redirect("web:panel:events")

          except PermissionDenied:
              messages.error(request, _("You don't have permission to create events."))
              return redirect("web:panel:events")
          except ValueError as e:
              messages.error(request, str(e))
              return redirect("web:panel:events")
  ```

  ## ⚙️ MEDIUM PRIORITY - Architectural Improvements

  ### 10. Refactor AuthorizationService with Strategy Pattern
  **Location:** `src/ludamus/gears.py:207-278`
  **Issue:** AuthorizationService has too many responsibilities (violates SRP)
  **Fix:**
  ```python
  # Add to pacts.py
  class PermissionStrategy(Protocol):
      def check(
          self,
          user_id: int,
          sphere_id: int,
          action: Action,
          resource_type: ResourceType,
          resource_id: int
      ) -> bool: ...

  # Add to gears.py
  class DirectPermissionStrategy:
      def __init__(self, uow: UnitOfWorkProtocol):
          self._uow = uow

      def check(self, user_id: int, sphere_id: int, action: Action,
                resource_type: ResourceType, resource_id: int) -> bool:
          return self._uow.user_permissions.has_permission(
              user_id, sphere_id, action, resource_type, resource_id
          )

  class SphereManagerStrategy:
      def __init__(self, uow: UnitOfWorkProtocol, user_slug: str):
          self._uow = uow
          self._user_slug = user_slug

      def check(self, user_id: int, sphere_id: int, action: Action,
                resource_type: ResourceType, resource_id: int) -> bool:
          return self._uow.spheres.is_manager(sphere_id, self._user_slug)

  class DerivedPermissionStrategy:
      def __init__(self, uow: UnitOfWorkProtocol):
          self._uow = uow

      def check(self, user_id: int, sphere_id: int, action: Action,
                resource_type: ResourceType, resource_id: int) -> bool:
          checks = PermissionCheckRegistry.get_checks(action, resource_type)
          return any(
              check_func(self._uow, user_id, resource_type, resource_id)
              for check_func in checks
          )

  class AuthorizationService:
      def __init__(self, context: AuthenticatedRequestContext, uow: UnitOfWorkProtocol):
          self._context = context
          self._strategies: list[PermissionStrategy] = [
              DirectPermissionStrategy(uow),
              SphereManagerStrategy(uow, context.current_user_slug),
              DerivedPermissionStrategy(uow),
          ]

      def can(self, action: Action, resource_type: ResourceType, resource_id: int) -> bool:
          # Validate action applies to resource type
          if action != Action.ALL and resource_type != ResourceType.ALL:
              applicable = ACTION_APPLICABLE_TO.get(action, [])
              if ResourceType.ALL not in applicable and resource_type not in applicable:
                  raise ValueError(f"Action {action} not applicable to {resource_type}")

          return any(
              strategy.check(
                  self._context.current_user_id,
                  self._context.current_sphere_id,
                  action,
                  resource_type,
                  resource_id
              )
              for strategy in self._strategies
          )
  ```

  ### 11. Separate Authorization from Business Logic in RoleAssignmentService
  **Location:** `src/ludamus/gears.py:280-320`
  **Issue:** Service does both authorization AND business logic (violates LSP)
  **Fix:**
  ```python
  # Remove authorization from service:
  class RoleAssignmentService:
      def __init__(self, context: AuthenticatedRequestContext, uow: UnitOfWorkProtocol):
          self._context = context
          self._uow = uow

      def assign_role(
          self, user_id: int, role_id: int, resource_type: ResourceType, resource_id: int
      ) -> list[UserPermissionDTO]:
          # ❌ REMOVE THIS:
          # auth = AuthorizationService(self._context, self._uow)
          # auth.require(Action.MANAGE_PERMISSIONS, ResourceType.SPHERE, ...)

          # Pure business logic only:
          role_perms = self._uow.roles.get_permissions(role_id)

          created_perms = []
          for role_perm in role_perms:
              perm = self._uow.user_permissions.grant(
                  UserPermissionData(
                      user_id=user_id,
                      sphere_id=self._context.current_sphere_id,
                      action=role_perm.action,
                      resource_type=resource_type,
                      resource_id=resource_id,
                      granted_from_role_id=role_id,
                      granted_by_id=self._context.current_user_id,
                  )
              )
              created_perms.append(perm)

          return created_perms

  # Move authorization to views:
  class PanelRoleAssignActionView(LoginRequiredMixin, View):
      def post(self, request: AuthenticatedRootRequest) -> HttpResponse:
          auth = AuthorizationService(request.context, request.uow)
          auth.require(Action.MANAGE_PERMISSIONS, ResourceType.SPHERE, request.context.current_sphere_id)

          service = RoleAssignmentService(request.context, request.uow)
          service.assign_role(user_id, role_id, resource_type, resource_id)
  ```

  ### 12. Add Missing Repository Test Coverage
  **Location:** `tests/unit/` (new files needed)
  **Issue:** No unit tests for RoleRepository, UserPermissionRepository, EventRepository
  **Fix:** Create test files:
  ```python
  # tests/unit/test_role_repository.py
  # tests/unit/test_user_permission_repository.py
  # tests/unit/test_event_repository.py
  ```

  ### 13. Add Integration Tests for Panel Views
  **Location:** `tests/integration/views/` (new files needed)
  **Issue:** No integration tests for new panel functionality
  **Fix:** Create test files following project conventions:
  ```python
  # tests/integration/views/panel/test_panel_index.py
  # tests/integration/views/panel/test_panel_events.py
  # tests/integration/views/panel/test_panel_users.py
  # tests/integration/views/panel/test_panel_role_create.py
  # etc.
  ```

  ## ℹ️ LOW PRIORITY - Nice to Have

  ### 14. Clean Up Orphaned Template Files
  **Location:** `backoffice/*.html` (11 files)
  **Issue:** Template files with no corresponding views
  **Decision Needed:** Are these work-in-progress or should they be removed?
  **Options:**
  1. Implement views for these templates
  2. Remove unused templates
  3. Move to a separate directory (e.g., `backoffice/planned/`)

  ### 15. Remove Unnecessary Transaction Wrappers
  **Location:** `src/ludamus/adapters/web/django/views.py:2354-2375`
  **Issue:** Nested transactions when `ATOMIC_REQUESTS = True`
  **Impact:** Minor performance overhead (creates savepoints)
  **Fix:** Remove `with request.uow.atomic():` from views since requests are already atomic

  ### 16. Use TypeAlias for PermissionCheckFunc
  **Location:** `src/ludamus/gears.py:26`
  **Issue:** Type alias only exists under TYPE_CHECKING (unconventional)
  **Fix:**
  ```python
  from typing import TypeAlias

  PermissionCheckFunc: TypeAlias = Callable[
      [UnitOfWorkProtocol, int, ResourceType, int], bool
  ]
  ```

  ### 17. Review Underscore Prefixes for Internal Methods
  **Location:** `src/ludamus/links/db/django/repositories.py:280`
  **Issue:** `_read_user()` has underscore but could be public
  **Decision:** Evaluate if method should be in protocol or truly internal

  ## 🏗️ LONG-TERM - Architectural Debt

  ### 18. Break Dependency of Repositories on Django Models
  **Location:** `src/ludamus/links/db/django/repositories.py:4-17`
  **Issue:** Repositories depend on adapters (should both depend on pacts)
  **Status:** Known architectural debt being migrated
  **Note:** This is part of larger migration to Clean Architecture, defer until other layers migrated

  ---
  ## Quick Reference: Priority Ordering

  **Must Fix Before Merge (Blocking):**
  1. Authorization bypass in panel views
  2. CSRF protection
  3. Input validation

  **Should Fix This Sprint:**
  4. Placeholder permission check
  5. Remove @staticmethod
  6. Consistent error handling
  7. DRY mixin for permissions
  8. Error handling in views
  9. Extract business logic to services

  **Next Sprint:**
  10. Strategy pattern refactor
  11. Separate authorization from services
  12-13. Test coverage

  **Backlog:**
  14-18. Low priority improvements