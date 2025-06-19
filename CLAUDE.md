# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ludamus is a Django-based event management system for organizing gaming sessions (RPG and board games). It features multi-tenant architecture, OAuth authentication via Auth0, and comprehensive enrollment management.

## Development Commands

### Running the Development Server
```bash
poe dj start
```

### Database Operations
```bash
poe dj makemigrations
poe dj migrate
poe dj loaddata db.json  # Load sample data
```

### Code Quality Commands
```bash
# Format code
poe format  # or: black src tests

# Lint code
poe lint    # or: ruff check src tests
poe pylint  # or: pylint src

# Type checking
poe mypy    # or: mypy src

# Lint templates
poe djlint  # or: djlint src/ludamus/templates --reformat
```

### Compile messages

```bash
poe dj compilemessages
```

### Running Tests
```bash
# Note: No automated tests implemented yet
poe dj test
```

## Architecture Overview

### Multi-Tenant Structure
The system uses a hierarchical multi-tenant architecture:
- **Spheres**: Top-level organizational units (provinces, topics, organizations)
- **Sites**: Django sites framework for multi-domain support (subdomain-based spheres)
- **Events**: Time-bound gatherings within spheres
- **Sessions**: Individual activities within events

### Key Design Patterns

1. **Adapters Pattern**: 
   - `src/ludamus/adapters/` separates external interfaces
   - `db/django/` - Database models and ORM layer
   - `web/django/` - Views, forms, URLs, middleware
   - `oauth.py` - Auth0 integration

2. **Authentication Flow**:
   - Auth0 OAuth integration with custom callback handling
   - User types: Active users and Connected users (family/friends)
   - Age validation (16+ requirement) enforced in forms
   - Connected users managed through a manager relationship

3. **Enrollment System**:
   - Multi-user enrollment (self + connected users)
   - Capacity management with automatic waiting list promotion
   - Time conflict detection prevents double-booking
   - Real-time status tracking (confirmed/waiting)

4. **Proposal Workflow**:
   - Users submit session proposals during proposal period
   - Superusers accept proposals, converting them to sessions
   - Tag system with categories (select-type and type-in)
   - Proposals linked to sessions after acceptance

### Critical Business Logic

1. **Session Enrollment** (`views.py:408-713`):
   - Validates user age and enrollment period
   - Checks capacity and time conflicts
   - Handles waiting list promotion on cancellation
   - Supports batch operations for multiple users

2. **Proposal System** (`views.py:716-1033`):
   - Enforces proposal submission period
   - Dynamic form generation based on tag categories
   - Converts accepted proposals to scheduled sessions

3. **Time Conflict Detection**:
   - `Session.overlaps_with()` method checks for scheduling conflicts
   - Prevents enrollment in overlapping sessions
   - Considers both start and end times

## Environment Configuration

Required environment variables:
- `AUTH0_DOMAIN` - Auth0 domain
- `AUTH0_CLIENT_ID` - Auth0 client ID
- `AUTH0_CLIENT_SECRET` - Auth0 client secret
- `SECRET_KEY` - Django secret key
- `ROOT_DOMAIN` - Root domain for multi-site support (e.g., zagrajmy.local)
- `SUPPORT_EMAIL` - Support email address (default: support@zagrajmy.net)

## Database Schema Highlights

Key models to understand:
- `User`: Custom user model with birth_date and user_type
- `Event`: Main gatherings with enrollment/proposal periods
- `Session`: Individual activities with capacity limits
- `SessionParticipation`: Tracks user enrollments with status
- `Proposal`: User-submitted session ideas
- `Space` & `TimeSlot`: Physical and temporal scheduling
- `AgendaItem`: Links sessions to spaces

## Testing Approach

Comprehensive TEST_PLAN.md with 215+ user stories covering:
- Authentication flows
- Multi-user enrollment scenarios
- Capacity management edge cases
- Time conflict handling
- Proposal submission and acceptance

Note: Automated tests not yet implemented (tests/ directory empty).

## Principles

- Clean Architecture
- SOLID principles
- Strict typing
- Command Query Separation
- Write short clean functions (up to 7 statements)
