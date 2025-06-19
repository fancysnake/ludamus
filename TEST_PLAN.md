# Comprehensive Test Plan - Ludamus Event Management System

## Overview
This test plan covers all user stories for the Ludamus event management system, organized by the Django fixture files required to test them. Load fixtures incrementally as you progress through test sections.

## Test Data Setup - Django Fixtures

### Fixture Loading Commands

```bash
# Load fixtures incrementally based on what you're testing
poe dj loaddata fixtures/01_base_setup.json
poe dj loaddata fixtures/02_events_without_sessions.json
poe dj loaddata fixtures/03_events_with_sessions.json
poe dj loaddata fixtures/04_sessions_with_time_slots.json
poe dj loaddata fixtures/05_limited_capacity_sessions.json
poe dj loaddata fixtures/06_proposal_periods.json
poe dj loaddata fixtures/07_tags_and_categories.json
poe dj loaddata fixtures/08_connected_users.json
```

---

## Tests Requiring No Fixtures (Public Access Without Data)

### Authentication Redirects & Error Handling
These tests verify system behavior when no data exists.

#### Test Cases
- **US-005**: As a user on wrong domain, I get redirected to correct domain before login
- **US-006**: As a user with Auth0 failures, I see appropriate error messages
- **US-007**: As a user with incomplete Auth0 profile, system handles missing data gracefully
- **US-008**: User repeatedly tries to access restricted pages before login → Always redirected to login
- **US-009**: User tries to manipulate login URLs → Security validation prevents unauthorized access
- **US-010**: User bookmarks login callback URL → Graceful handling of invalid callback attempts
- **US-044**: As a visitor when no events exist, I see appropriate empty state
- **US-047**: User tries to access events that don't exist → 404 handling
- **US-186**: As an unauthenticated user, I get redirected to login for protected actions
- **US-189**: User tries to access URLs directly without proper authentication → Proper redirection

---

## Tests Requiring Fixture: 01_base_setup.json

**Fixture provides**: Sites, spheres, and test users (event_host, session_host, admin_user)

### User Authentication & Login
#### Test Cases
- **US-001**: As a new user, I can log in via Auth0 and get automatically registered
- **US-002**: As a returning user, I can log in and see "Welcome back!" message
- **US-003**: As a new user, I'm redirected to profile completion after first login
- **US-004**: As a user, I can log out and get redirected back to Auth0 logout

### Profile Management
#### Test Cases
- **US-011**: As a new user, I can complete my profile with name, birth date, and email
- **US-012**: As an existing user, I can update my profile information
- **US-013**: As a user, I see validation errors clearly when submitting invalid data
- **US-014**: As a user over 16, my profile gets accepted and I can access full features
- **US-015**: As a user under 16, I cannot create a profile (age validation fails)
- **US-016**: As a user with duplicate email, I see appropriate error message
- **US-017**: As a user with invalid birth date (future date), I get validation error
- **US-018**: As a user without completing profile, I'm blocked from enrollments/proposals
- **US-019**: User tries to enter obviously fake birth date (like 1900) → Accepted if over 16 rule
- **US-020**: User leaves required fields empty and keeps submitting → Clear validation messages persist
- **US-021**: User tries to set birth date to make them exactly 16 → Edge case validation testing
- **US-022**: User enters extremely long names/emails → Field length validation

### Basic Connected Users Management (No Enrollments)
#### Test Cases
- **US-023**: As a user, I can add family members/friends as connected users
- **US-024**: As a user, I can set connected user's name and birth date
- **US-025**: As a user, I can see all my connected users in a list
- **US-026**: As a user, I can edit connected user information
- **US-027**: As a user, I cannot add connected user with duplicate name
- **US-028**: As a user adding infant connected user, system accepts any age
- **US-029**: As a user with no connected users, I see helpful empty state message
- **US-033**: As a user, I can edit connected user's information
- **US-034**: As a user, I can delete connected users I no longer manage
- **US-035**: As a user, I can see connected user ages calculated automatically
- **US-037**: As a user, I cannot edit connected users to have invalid data
- **US-038**: User rapidly creates and deletes same connected user → System handles gracefully
- **US-039**: User tries to edit connected user to have birth date in future → Validation prevents

### Basic Permission Tests
#### Test Cases
- **US-188**: As a regular user, I cannot access superuser features
- **US-190**: User tries to manipulate URLs to access others' data → Access denied appropriately

---

## Tests Requiring Fixture: 02_events_without_sessions.json

**Fixture provides**: Various event states (past, live, future, with/without enrollment periods)

### Public Event Discovery
#### Test Cases
- **US-040**: As a visitor, I can see all upcoming events
- **US-041**: As a visitor, I can see event names, descriptions, and dates
- **US-042**: As a visitor, I can distinguish between UPCOMING, LIVE, and PAST events
- **US-043**: As a visitor, I can click on events to see details
- **US-045**: As a visitor, events from other domains/spheres are not visible
- **US-046**: User bookmarks event URLs from other domains → Properly handled access control
- **US-048**: As a visitor, I can see complete event information
- **US-052**: As a visitor viewing event with no sessions, I see appropriate message
- **US-055**: User constantly refreshes event page → Consistent data display

### Authenticated Event Access
#### Test Cases
- **US-147**: As a user, I can easily navigate between events, sessions, and profile sections
- **US-192**: As a user, I can only see data relevant to my sphere/domain
- **US-193**: As a user, I can see appropriate enrollment information for my events
- **US-195**: As a user switching between different event domains, I see appropriate data for each
- **US-198**: User tries to access data from other domains through URL manipulation → Access control prevents

### Enrollment Period Restrictions
#### Test Cases
- **US-066**: As a user during closed enrollment period, I cannot access enrollment interface
- **US-083**: User tries to access enrollment actions for sessions they can't join → Proper permission checking
- **US-191**: User attempts to bypass enrollment restrictions through direct requests → Server validation prevents

### Proposal Period Restrictions  
#### Test Cases
- **US-099**: As a user without birth date, I cannot submit proposals
- **US-100**: As a user during closed proposal period, I cannot access proposal form

---

## Tests Requiring Fixture: 03_events_with_sessions.json

**Fixture provides**: Sessions (scheduled and unscheduled), spaces, agenda items

### Session Viewing
#### Test Cases
- **US-049**: As a visitor, I can see all sessions organized by time slots
- **US-050**: As a visitor, I can see participant counts for each session
- **US-053**: As a visitor viewing event with unscheduled sessions, I see them listed separately
- **US-056**: User tries to access sessions directly without going through event → Proper navigation maintained

### Basic Enrollment Interface (No Capacity Limits Yet)
#### Test Cases
- **US-051**: As a logged-in user, I can see my enrollment status for each session
- **US-054**: As a logged-in user, I can see enrollment status for me and connected users
- **US-057**: As a logged-in user, I can access enrollment interface for any session
- **US-058**: As a user, I can see myself and all connected users in enrollment table
- **US-059**: As a user, I can select different options (enroll/waitlist/cancel) for each person
- **US-061**: As a user, I can see current enrollment status for each person clearly
- **US-063**: As a user with no connected users, I only see myself in enrollment table
- **US-072**: As a user, I can enroll directly in sessions with available spots
- **US-074**: As a user, I can cancel my enrollment in sessions
- **US-078**: As a user already enrolled, I cannot enroll again in same session
- **US-079**: As a user not enrolled, I cannot cancel enrollment
- **US-129**: As a user, I can see real-time participant counts on all sessions
- **US-148**: As a user, I see clear status indicators throughout the interface
- **US-149**: As a user, I can access enrollment management through intuitive "Manage" buttons
- **US-150**: As a user, I can view enrollment status in convenient modals

### UI Behavior
#### Test Cases
- **US-151**: As a user with JavaScript disabled, basic functionality still works
- **US-152**: As a user on mobile device, interface remains usable
- **US-154**: User keeps opening multiple modals → Interface handles gracefully
- **US-155**: User tries to navigate with browser back/forward → Proper state management
- **US-156**: User bookmarks specific modal states → Graceful handling of invalid states

---

## Tests Requiring Fixture: 04_sessions_with_time_slots.json

**Fixture provides**: Time slots, overlapping sessions for conflict detection

### Time Conflict Detection
#### Test Cases
- **US-062**: As a user, I see time conflict warnings for people already enrolled elsewhere
- **US-068**: User tries to enroll someone with time conflict → Warning message and limitation to waitlist
- **US-077**: As a user with time conflicts, I can only join waiting list
- **US-081**: User tries to enroll in conflicting time slots → Clear conflict explanations
- **US-120**: As a user, I see clear warnings when trying to enroll in overlapping sessions
- **US-121**: As a user with conflicts, I can still join waiting lists
- **US-122**: As a user, conflicts are checked for both myself and connected users
- **US-123**: As a user, time conflicts prevent direct enrollment but allow waiting list
- **US-124**: As a user with connected user in overlapping session, I get appropriate warnings
- **US-125**: As a user, system correctly handles sessions with no time information
- **US-126**: As a user, conflicts are detected across different days if times overlap
- **US-127**: User insists on enrolling despite multiple conflict warnings → System maintains restriction
- **US-128**: User tries to enroll connected user in conflicting time → Clear explanation of limitation

---

## Tests Requiring Fixture: 05_limited_capacity_sessions.json

**Fixture provides**: Sessions with various capacities, full sessions, waiting lists, enrolled users

### Capacity Management
#### Test Cases
- **US-060**: As a user, I can enroll multiple people simultaneously if capacity allows
- **US-064**: As a user trying to enroll more people than available spots, I get clear error
- **US-067**: User selects enroll for everyone when session is full → Clear capacity error message
- **US-069**: User submits form without selecting anyone → Warning to select at least one person
- **US-070**: User rapidly submits enrollment form multiple times → Proper handling of duplicate requests
- **US-071**: User tries to enroll and cancel same person → Form validation prevents conflicting selections
- **US-073**: As a user, I can join waiting list when session is full
- **US-075**: As a user, I can leave waiting lists I've joined
- **US-076**: As a user trying to enroll in full session, I'm offered waiting list only
- **US-080**: User keeps trying to enroll in full sessions → Consistent "full" messaging
- **US-082**: User rapidly enrolls and cancels same session → System handles gracefully
- **US-130**: As a user, I see accurate "X/Y enrolled" counts including waiting list
- **US-131**: As a user, system prevents over-enrollment by validating total requests
- **US-132**: As a user, I get helpful error when requesting more spots than available
- **US-133**: As a user, participant counts update immediately after enrollments/cancellations
- **US-135**: As a user viewing session at capacity, I see accurate "Full" indicators
- **US-136**: User keeps trying to enroll large groups in full sessions → Consistent capacity errors
- **US-137**: User expects to bypass capacity limits → System maintains integrity

### Waiting List Management
#### Test Cases
- **US-084**: As a user on waiting list, I get automatically promoted when spots open
- **US-085**: As a user, I can see my position in waiting lists
- **US-086**: As a user, I can see waiting list sizes on session displays
- **US-087**: As a user being promoted, system checks for time conflicts before confirming
- **US-088**: As a user with time conflicts when promoted, I remain on waiting list
- **US-089**: As a user, I see multiple people get promoted when multiple spots open
- **US-090**: As a user canceling enrollment, I see waiting list get promoted immediately
- **US-091**: User keeps joining and leaving waiting lists → System tracks positions correctly
- **US-092**: User expects immediate promotion when spot opens but has conflict → Clear explanation why not promoted
- **US-138**: As a user canceling enrollment, waiting list users get promoted automatically
- **US-139**: As a user, promotion respects time conflict rules
- **US-140**: As a user, I can cancel enrollments for myself and connected users
- **US-141**: As a user, I see clear feedback about who got promoted when I cancel
- **US-142**: As a user canceling when no one is waiting, no promotions occur
- **US-143**: As a user, promotion skips people with time conflicts
- **US-144**: As a user canceling multiple enrollments, system promotes multiple people if possible
- **US-145**: User rapidly enrolls and cancels to manipulate waiting list → System handles gracefully

### Status Display
#### Test Cases
- **US-180**: As a user, I see accurate status badges (enrolled, waiting, available, conflict)
- **US-181**: As a user, I get clear success messages after actions
- **US-182**: As a user, I see helpful error messages when actions fail
- **US-185**: As a user, status updates reflect immediately after actions
- **US-186**: As a user during error conditions, I get specific helpful guidance
- **US-187**: User ignores status indicators and tries invalid actions → Clear prevention and explanation

### Concurrent Operations
#### Test Cases
- **US-134**: As a user during concurrent enrollments, system maintains data consistency
- **US-189**: As a user, my enrollments succeed even when others are enrolling simultaneously
- **US-190**: As a user, I see accurate capacity counts even during high traffic
- **US-191**: As a user, the last person to enroll in final spot gets the spot
- **US-192**: As a user enrolling when spot gets taken by someone else, I get clear failure message
- **US-193**: As a user, system prevents double-enrollment even with concurrent requests
- **US-195**: User repeatedly submits same enrollment rapidly → System deduplicates properly
- **US-196**: User opens multiple browser tabs and tries to enroll from all → Consistent behavior

---

## Tests Requiring Fixture: 06_proposal_periods.json

**Fixture provides**: Events with proposal periods, proposal categories, spaces, time slots, proposals

### Proposal Submission
#### Test Cases
- **US-093**: As a logged-in user with complete profile, I can submit general session proposals
- **US-094**: As a user, I can submit proposals for specific time slots
- **US-095**: As a user, I can specify title, description, requirements, and special needs
- **US-096**: As a user, I can set participant limits within category boundaries
- **US-097**: As a user, I can select tags from available categories
- **US-101**: As a user, I get validation errors for participant limits outside boundaries
- **US-102**: As a user, I cannot submit proposals without required title
- **US-103**: As a user in event with no proposal categories, I see appropriate message
- **US-104**: User submits proposals with minimal information → System accepts if requirements met
- **US-105**: User tries to set participant limit to 1000 → Validation prevents exceeding maximums
- **US-106**: User leaves all optional fields empty → System creates valid proposal
- **US-107**: User enters extremely long descriptions → Field length validation
- **US-108**: User tries to submit same proposal multiple times → System allows (no duplicate prevention)

### Proposal Management (Superuser)
#### Test Cases
- **US-109**: As a superuser, I can see all pending proposals on event page
- **US-110**: As a superuser, I can view detailed proposal information in modals
- **US-111**: As a superuser, I can accept proposals by assigning space and time slot
- **US-112**: As a superuser, I see proposal preferences highlighted in time slot selection
- **US-113**: As a superuser, accepted proposals become sessions automatically
- **US-114**: As a superuser, I cannot accept proposals without selecting space and time slot
- **US-115**: As a superuser in event with no spaces/time slots, I see appropriate messages
- **US-116**: As a regular user, I cannot see proposal management interface
- **US-117**: Superuser tries to accept proposal without proper selections → Clear validation messages
- **US-118**: Superuser repeatedly clicks accept button → Prevents duplicate session creation
- **US-119**: Superuser tries to assign same time/space to multiple proposals → System should prevent conflicts
- **US-194**: As a superuser, I have access to proposal management features

---

## Tests Requiring Fixture: 07_tags_and_categories.json

**Fixture provides**: Tag categories (with/without icons), tags, tag assignments to sessions and proposals

### Tag Display
#### Test Cases
- **US-098**: As a user, I can enter custom tags when category allows free-text
- **US-171**: As a user, I see bootstrap icons next to tags that have category icons configured
- **US-172**: As a user, I see consistent icons for all tags within the same category
- **US-173**: As a user viewing session lists, tag icons help me quickly identify tag types
- **US-174**: As a user creating proposals, I see category icons in the tag selection interface
- **US-175**: As a user, tags without category icons display normally without broken elements
- **US-176**: As a user, invalid icon names don't break the display
- **US-177**: As a user viewing mixed sessions (some with icons, some without), display remains consistent
- **US-178**: User expects all tags to have icons → System handles mixed icon states gracefully
- **US-179**: User tries to interact with tag icons → Icons are visual-only, don't interfere with functionality

### Session Filtering
#### Test Cases
- **US-157**: As a user, I can filter sessions by typing in the search box (title or host)
- **US-158**: As a user, I can filter sessions by enrollment status (available, full, enrolled, waiting)
- **US-159**: As a user, I can filter sessions by tags organized in categories with optgroups
- **US-160**: As a user, I can combine multiple filters simultaneously for precise results
- **US-161**: As a user, I can clear all filters with one button click
- **US-162**: As a user, empty time slot sections are automatically hidden when filtered
- **US-163**: As a user with no JavaScript, filtering controls don't appear but sessions remain visible
- **US-164**: As a user viewing events with no tags, tag filter dropdown shows only "All tags" option
- **US-165**: As a user filtering sessions, time slot headers remain visible even when sections are empty
- **US-166**: As a user with sessions having inconsistent tag data, filtering works gracefully
- **US-167**: User rapidly changes filters → Interface responds smoothly without lag
- **US-168**: User selects filters that match no sessions → Clear "no results" state
- **US-169**: User tries to use special characters in search → Search works with any input
- **US-170**: User refreshes page with filters applied → Filters reset to default state

---

## Tests Requiring Fixture: 08_connected_users.json

**Fixture provides**: Manager user with connected users (adult, teen, child), some with enrollments

### Connected Users with Enrollments
#### Test Cases
- **US-030**: User tries to add 50+ connected users → System should handle gracefully
- **US-031**: User adds connected users with identical names → System allows but shows clearly in lists
- **US-032**: User deletes connected user who has active enrollments → Confirm safety of deletion
- **US-036**: As a user editing connected user with active enrollments, I see appropriate warnings
- **US-065**: As a user with people already enrolled, I see appropriate status indicators
- **US-146**: User expects to cancel others' enrollments → Proper permission restrictions
- **US-153**: As a user with many connected users, interface remains manageable
- **US-183**: As a user, I can distinguish between my status and connected users' status
- **US-184**: As a user with mixed enrollment status (some enrolled, some waiting), I see clear summary
- **US-196**: As a user, I cannot see enrollment details for sessions I'm not involved with
- **US-197**: As a user, my connected users' data is private to me
- **US-199**: User attempts to view other users' connected user information → Privacy protection maintains

---

## Tests Not Requiring Specific Fixtures (System-Level)

### Data Validation Edge Cases
#### Test Cases
- **US-197**: As a user, all my valid data gets saved correctly
- **US-198**: As a user, I can recover from validation errors without losing other data
- **US-199**: As a user, system handles special characters in names/descriptions
- **US-200**: As a user entering data at exact validation boundaries, system handles correctly
- **US-201**: As a user with very long names/descriptions, system truncates or validates gracefully
- **US-202**: As a user entering unusual but valid birth dates, system accepts correctly
- **US-203**: User keeps entering invalid data formats → Consistent validation messaging
- **US-204**: User tries to inject malicious content in text fields → Proper sanitization
- **US-205**: User attempts to manipulate form data through browser tools → Server-side validation prevents

### System Error Conditions
#### Test Cases
- **US-188**: User dismisses error messages and retries same invalid action → Consistent error messaging
- **US-194**: As a user during system high load, I get appropriate feedback about delays
- **US-200**: As a user encountering system errors, I get helpful error messages
- **US-201**: As a user, I can retry failed actions appropriately
- **US-202**: As a user, temporary system issues don't corrupt my data
- **US-203**: As a user during database connection issues, I get appropriate feedback
- **US-204**: As a user when sessions become unavailable, I see updated status
- **US-205**: As a user during Auth0 outages, system handles gracefully
- **US-206**: User keeps retrying failed actions → System doesn't accumulate bad state
- **US-207**: User refuses to acknowledge error messages → System maintains safety

### Data Integrity
#### Test Cases
- **US-208**: As a user, my enrollment history is preserved correctly
- **US-209**: As a user, I can see audit trail of my actions where appropriate
- **US-210**: As a user, cancelled enrollments properly promote waiting lists
- **US-211**: As a user with orphaned data (connected user deletions), system handles gracefully
- **US-212**: As a user when sessions get deleted, my enrollments are handled appropriately
- **US-213**: As a user during data migration scenarios, my data integrity is maintained
- **US-214**: User creates complex enrollment scenarios then changes mind repeatedly → System maintains consistency
- **US-215**: User tries to exploit edge cases in waiting list promotion → System remains fair and consistent

---

## Test Execution Guidelines

### Progressive Testing Approach
1. Start with tests requiring no fixtures
2. Load fixtures incrementally as you progress through sections
3. Each fixture builds on the previous ones
4. Run all tests for a fixture before loading the next one

### Test Data Summary

| Fixture | Key Data Provided |
|---------|-------------------|
| 01_base_setup.json | Sites, spheres, admin/host users |
| 02_events_without_sessions.json | Various event states |
| 03_events_with_sessions.json | Sessions, spaces, agenda items |
| 04_sessions_with_time_slots.json | Time slots, overlapping sessions |
| 05_limited_capacity_sessions.json | Full sessions, waiting lists, enrollments |
| 06_proposal_periods.json | Proposal categories, proposals |
| 07_tags_and_categories.json | Tags with/without icons |
| 08_connected_users.json | Manager with connected users |

### Success Metrics
- All tests pass for each fixture level before proceeding
- No data corruption when loading fixtures incrementally
- Clear error messages for all failure scenarios
- Consistent behavior across all fixture states