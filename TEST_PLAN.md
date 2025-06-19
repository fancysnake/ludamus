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
- As an anoymous user, when I try access page that requires login I get redirected to the login required page
- As a user, I can open root site home page
- As a user on wrong domain, I get redirected to correct domain before login
- As a user when no events exist, I see appropriate empty state
- As a user, when I try to open not existing page, I get a 404 error page
- As a user, when I stumble on an HTTP 500 error, I get a 500 error page

---

## Tests Requiring Fixture: 01_base_setup.json

**Fixture provides**: Sites, spheres, and test users (event_host, session_host, admin_user)

### User Authentication & Login
#### Test Cases
- As a new user, I can log in via Auth0 and get automatically registered
- As a returning user, I can log in and see "Welcome back!" message
- As a new user, I'm redirected to profile completion after first login
- As a user, I can log out and get redirected back to Auth0 logout

### Profile Management
#### Test Cases
- As a new user, I can complete my profile with name, birth date, and email
- As an existing user, I can update my profile information
- As a user, I see validation errors clearly when submitting invalid data
- As a user over 16, my profile gets accepted and I can access full features
- As a user under 16, I cannot create a profile (age validation fails)
- As a user with duplicate email, I see appropriate error message
- As a user with invalid birth date (future date), I get validation error
- As a user without completing profile, I'm blocked from enrollments/proposals
- User tries to enter obviously fake birth date (like 1900) → Accepted if over 16 rule
- User leaves required fields empty and keeps submitting → Clear validation messages persist
- User tries to set birth date to make them exactly 16 → Edge case validation testing
- User enters extremely long names/emails → Field length validation

### Basic Connected Users Management (No Enrollments)
#### Test Cases
- As an anonymous user, I can open custom sphere page.
- As a user, I can add family members/friends as connected users
- As a user, I can set connected user's name and birth date
- As a user, I can see all my connected users in a list
- As a user, I can edit connected user information
- As a user, I cannot add connected user with duplicate name
- As a user adding infant connected user, system accepts any age
- As a user with no connected users, I see helpful empty state message
- As a user, I can edit connected user's information
- As a user, I can delete connected users I no longer manage
- As a user, I can see connected user ages calculated automatically
- As a user, I cannot edit connected users to have invalid data
- User rapidly creates and deletes same connected user → System handles gracefully
- User tries to edit connected user to have birth date in future → Validation prevents

### Basic Permission Tests
#### Test Cases
- As a regular user, I cannot access superuser features
- User tries to manipulate URLs to access others' data → Access denied appropriately

---

## Tests Requiring Fixture: 02_events_without_sessions.json

**Fixture provides**: Various event states (past, live, future, with/without enrollment periods)

### Public Event Discovery
#### Test Cases
- As a visitor, I can see all upcoming events
- As a visitor, I can see event names, descriptions, and dates
- As a visitor, I can distinguish between UPCOMING, LIVE, and PAST events
- As a visitor, I can click on events to see details
- As a visitor, events from other domains/spheres are not visible
- User bookmarks event URLs from other domains → Properly handled access control
- As a visitor, I can see complete event information
- As a visitor viewing event with no sessions, I see appropriate message
- User constantly refreshes event page → Consistent data display

### Authenticated Event Access
#### Test Cases
- As a user, I can easily navigate between events, sessions, and profile sections
- As a user, I can only see data relevant to my sphere/domain
- As a user, I can see appropriate enrollment information for my events
- As a user switching between different event domains, I see appropriate data for each
- User tries to access data from other domains through URL manipulation → Access control prevents

### Enrollment Period Restrictions
#### Test Cases
- As a user during closed enrollment period, I cannot access enrollment interface
- User tries to access enrollment actions for sessions they can't join → Proper permission checking
- User attempts to bypass enrollment restrictions through direct requests → Server validation prevents

### Proposal Period Restrictions  
#### Test Cases
- As a user without birth date, I cannot submit proposals
- As a user during closed proposal period, I cannot access proposal form

---

## Tests Requiring Fixture: 03_events_with_sessions.json

**Fixture provides**: Sessions (scheduled and unscheduled), spaces, agenda items

### Session Viewing
#### Test Cases
- As a visitor, I can see all sessions organized by time slots
- As a visitor, I can see participant counts for each session
- As a visitor viewing event with unscheduled sessions, I see them listed separately
- User tries to access sessions directly without going through event → Proper navigation maintained

### Basic Enrollment Interface (No Capacity Limits Yet)
#### Test Cases
- As a logged-in user, I can see my enrollment status for each session
- As a logged-in user, I can see enrollment status for me and connected users
- As a logged-in user, I can access enrollment interface for any session
- As a user, I can see myself and all connected users in enrollment table
- As a user, I can select different options (enroll/waitlist/cancel) for each person
- As a user, I can see current enrollment status for each person clearly
- As a user with no connected users, I only see myself in enrollment table
- As a user, I can enroll directly in sessions with available spots
- As a user, I can cancel my enrollment in sessions
- As a user already enrolled, I cannot enroll again in same session
- As a user not enrolled, I cannot cancel enrollment
- As a user, I can see real-time participant counts on all sessions
- As a user, I see clear status indicators throughout the interface
- As a user, I can access enrollment management through intuitive "Manage" buttons
- As a user, I can view enrollment status in convenient modals

### UI Behavior
#### Test Cases
- As a user with JavaScript disabled, basic functionality still works
- As a user on mobile device, interface remains usable
- User keeps opening multiple modals → Interface handles gracefully
- User tries to navigate with browser back/forward → Proper state management
- User bookmarks specific modal states → Graceful handling of invalid states

---

## Tests Requiring Fixture: 04_sessions_with_time_slots.json

**Fixture provides**: Time slots, overlapping sessions for conflict detection

### Time Conflict Detection
#### Test Cases
- As a user, I see time conflict warnings for people already enrolled elsewhere
- User tries to enroll someone with time conflict → Warning message and limitation to waitlist
- As a user with time conflicts, I can only join waiting list
- User tries to enroll in conflicting time slots → Clear conflict explanations
- As a user, I see clear warnings when trying to enroll in overlapping sessions
- As a user with conflicts, I can still join waiting lists
- As a user, conflicts are checked for both myself and connected users
- As a user, time conflicts prevent direct enrollment but allow waiting list
- As a user with connected user in overlapping session, I get appropriate warnings
- As a user, system correctly handles sessions with no time information
- As a user, conflicts are detected across different days if times overlap
- User insists on enrolling despite multiple conflict warnings → System maintains restriction
- User tries to enroll connected user in conflicting time → Clear explanation of limitation

---

## Tests Requiring Fixture: 05_limited_capacity_sessions.json

**Fixture provides**: Sessions with various capacities, full sessions, waiting lists, enrolled users

### Capacity Management
#### Test Cases
- As a user, I can enroll multiple people simultaneously if capacity allows
- As a user trying to enroll more people than available spots, I get clear error
- User selects enroll for everyone when session is full → Clear capacity error message
- User submits form without selecting anyone → Warning to select at least one person
- User rapidly submits enrollment form multiple times → Proper handling of duplicate requests
- User tries to enroll and cancel same person → Form validation prevents conflicting selections
- As a user, I can join waiting list when session is full
- As a user, I can leave waiting lists I've joined
- As a user trying to enroll in full session, I'm offered waiting list only
- User keeps trying to enroll in full sessions → Consistent "full" messaging
- User rapidly enrolls and cancels same session → System handles gracefully
- As a user, I see accurate "X/Y enrolled" counts including waiting list
- As a user, system prevents over-enrollment by validating total requests
- As a user, I get helpful error when requesting more spots than available
- As a user, participant counts update immediately after enrollments/cancellations
- As a user viewing session at capacity, I see accurate "Full" indicators
- User keeps trying to enroll large groups in full sessions → Consistent capacity errors
- User expects to bypass capacity limits → System maintains integrity

### Waiting List Management
#### Test Cases
- As a user on waiting list, I get automatically promoted when spots open
- As a user, I can see my position in waiting lists
- As a user, I can see waiting list sizes on session displays
- As a user being promoted, system checks for time conflicts before confirming
- As a user with time conflicts when promoted, I remain on waiting list
- As a user, I see multiple people get promoted when multiple spots open
- As a user canceling enrollment, I see waiting list get promoted immediately
- User keeps joining and leaving waiting lists → System tracks positions correctly
- User expects immediate promotion when spot opens but has conflict → Clear explanation why not promoted
- As a user canceling enrollment, waiting list users get promoted automatically
- As a user, promotion respects time conflict rules
- As a user, I can cancel enrollments for myself and connected users
- As a user, I see clear feedback about who got promoted when I cancel
- As a user canceling when no one is waiting, no promotions occur
- As a user, promotion skips people with time conflicts
- As a user canceling multiple enrollments, system promotes multiple people if possible
- User rapidly enrolls and cancels to manipulate waiting list → System handles gracefully

### Status Display
#### Test Cases
- As a user, I see accurate status badges (enrolled, waiting, available, conflict)
- As a user, I get clear success messages after actions
- As a user, I see helpful error messages when actions fail
- As a user, status updates reflect immediately after actions
- As a user during error conditions, I get specific helpful guidance
- User ignores status indicators and tries invalid actions → Clear prevention and explanation

### Concurrent Operations
#### Test Cases
- As a user during concurrent enrollments, system maintains data consistency
- As a user, my enrollments succeed even when others are enrolling simultaneously
- As a user, I see accurate capacity counts even during high traffic
- As a user, the last person to enroll in final spot gets the spot
- As a user enrolling when spot gets taken by someone else, I get clear failure message
- As a user, system prevents double-enrollment even with concurrent requests
- User repeatedly submits same enrollment rapidly → System deduplicates properly
- User opens multiple browser tabs and tries to enroll from all → Consistent behavior

---

## Tests Requiring Fixture: 06_proposal_periods.json

**Fixture provides**: Events with proposal periods, proposal categories, spaces, time slots, proposals

### Proposal Submission
#### Test Cases
- As a logged-in user with complete profile, I can submit general session proposals
- As a user, I can submit proposals for specific time slots
- As a user, I can specify title, description, requirements, and special needs
- As a user, I can set participant limits within category boundaries
- As a user, I can select tags from available categories
- As a user, I get validation errors for participant limits outside boundaries
- As a user, I cannot submit proposals without required title
- As a user in event with no proposal categories, I see appropriate message
- User submits proposals with minimal information → System accepts if requirements met
- User tries to set participant limit to 1000 → Validation prevents exceeding maximums
- User leaves all optional fields empty → System creates valid proposal
- User enters extremely long descriptions → Field length validation
- User tries to submit same proposal multiple times → System allows (no duplicate prevention)

### Proposal Management (Superuser)
#### Test Cases
- As a superuser, I can see all pending proposals on event page
- As a superuser, I can view detailed proposal information in modals
- As a superuser, I can accept proposals by assigning space and time slot
- As a superuser, I see proposal preferences highlighted in time slot selection
- As a superuser, accepted proposals become sessions automatically
- As a superuser, I cannot accept proposals without selecting space and time slot
- As a superuser in event with no spaces/time slots, I see appropriate messages
- As a regular user, I cannot see proposal management interface
- Superuser tries to accept proposal without proper selections → Clear validation messages
- Superuser repeatedly clicks accept button → Prevents duplicate session creation
- Superuser tries to assign same time/space to multiple proposals → System should prevent conflicts
- As a superuser, I have access to proposal management features

---

## Tests Requiring Fixture: 07_tags_and_categories.json

**Fixture provides**: Tag categories (with/without icons), tags, tag assignments to sessions and proposals

### Tag Display
#### Test Cases
- As a user, I can enter custom tags when category allows free-text
- As a user, I see bootstrap icons next to tags that have category icons configured
- As a user, I see consistent icons for all tags within the same category
- As a user viewing session lists, tag icons help me quickly identify tag types
- As a user creating proposals, I see category icons in the tag selection interface
- As a user, tags without category icons display normally without broken elements
- As a user, invalid icon names don't break the display
- As a user viewing mixed sessions (some with icons, some without), display remains consistent
- User expects all tags to have icons → System handles mixed icon states gracefully
- User tries to interact with tag icons → Icons are visual-only, don't interfere with functionality

### Session Filtering
#### Test Cases
- As a user, I can filter sessions by typing in the search box (title or host)
- As a user, I can filter sessions by enrollment status (available, full, enrolled, waiting)
- As a user, I can filter sessions by tags organized in categories with optgroups
- As a user, I can combine multiple filters simultaneously for precise results
- As a user, I can clear all filters with one button click
- As a user, empty time slot sections are automatically hidden when filtered
- As a user with no JavaScript, filtering controls don't appear but sessions remain visible
- As a user viewing events with no tags, tag filter dropdown shows only "All tags" option
- As a user filtering sessions, time slot headers remain visible even when sections are empty
- As a user with sessions having inconsistent tag data, filtering works gracefully
- User rapidly changes filters → Interface responds smoothly without lag
- User selects filters that match no sessions → Clear "no results" state
- User tries to use special characters in search → Search works with any input
- User refreshes page with filters applied → Filters reset to default state

---

## Tests Requiring Fixture: 08_connected_users.json

**Fixture provides**: Manager user with connected users (adult, teen, child), some with enrollments

### Connected Users with Enrollments
#### Test Cases
- User tries to add 50+ connected users → System should handle gracefully
- User adds connected users with identical names → System allows but shows clearly in lists
- User deletes connected user who has active enrollments → Confirm safety of deletion
- As a user editing connected user with active enrollments, I see appropriate warnings
- As a user with people already enrolled, I see appropriate status indicators
- User expects to cancel others' enrollments → Proper permission restrictions
- As a user with many connected users, interface remains manageable
- As a user, I can distinguish between my status and connected users' status
- As a user with mixed enrollment status (some enrolled, some waiting), I see clear summary
- As a user, I cannot see enrollment details for sessions I'm not involved with
- As a user, my connected users' data is private to me
- User attempts to view other users' connected user information → Privacy protection maintains

---

## Tests Not Requiring Specific Fixtures (System-Level)

### Data Validation Edge Cases
#### Test Cases
- As a user, all my valid data gets saved correctly
- As a user, I can recover from validation errors without losing other data
- As a user, system handles special characters in names/descriptions
- As a user entering data at exact validation boundaries, system handles correctly
- As a user with very long names/descriptions, system truncates or validates gracefully
- As a user entering unusual but valid birth dates, system accepts correctly
- User keeps entering invalid data formats → Consistent validation messaging
- User tries to inject malicious content in text fields → Proper sanitization
- User attempts to manipulate form data through browser tools → Server-side validation prevents

### System Error Conditions
#### Test Cases
- User dismisses error messages and retries same invalid action → Consistent error messaging
- As a user during system high load, I get appropriate feedback about delays
- As a user encountering system errors, I get helpful error messages
- As a user, I can retry failed actions appropriately
- As a user, temporary system issues don't corrupt my data
- As a user during database connection issues, I get appropriate feedback
- As a user when sessions become unavailable, I see updated status
- As a user during Auth0 outages, system handles gracefully
- User keeps retrying failed actions → System doesn't accumulate bad state
- User refuses to acknowledge error messages → System maintains safety

### Data Integrity
#### Test Cases
- As a user, my enrollment history is preserved correctly
- As a user, I can see audit trail of my actions where appropriate
- As a user, cancelled enrollments properly promote waiting lists
- As a user with orphaned data (connected user deletions), system handles gracefully
- As a user when sessions get deleted, my enrollments are handled appropriately
- As a user during data migration scenarios, my data integrity is maintained
- User creates complex enrollment scenarios then changes mind repeatedly → System maintains consistency
- User tries to exploit edge cases in waiting list promotion → System remains fair and consistent

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