# TODO

```mermaid
---
config:
  kanban:
    ticketBaseUrl: 'https://github.com/fancysnake/ludamus/issues/#TICKET#'
---
kanban
  Wishlist
    [Reasonable Cyclomatic Complexity thresholds]@{
      assigned: 'agent-readiness'
    }
    [Dead code detection tooling]@{ assigned: 'agent-readiness' }
    [Duplicate code detection tooling]@{ assigned: 'agent-readiness' }
    [Technical debt markers tracking]@{ assigned: 'agent-readiness' }
    [Feature flag system]@{ assigned: 'agent-readiness' }
    [Automated release notes]@{ assigned: 'agent-readiness' }
    [Automated deployment pipelines]@{ assigned: 'agent-readiness' }
    [Test suite duration monitoring]@{ assigned: 'agent-readiness' }
    [Auto-generated technical docs]@{ assigned: 'agent-readiness' }
    [Architecture diagrams]@{ assigned: 'agent-readiness' }
    [Priority/type/area labels]@{ assigned: 'agent-readiness' }
    [Request tracing]@{ assigned: 'agent-readiness' }
    [Engineering telemetry]@{ assigned: 'agent-readiness' }
    [Sentry with source maps]@{ assigned: 'agent-readiness' }
    [PagerDuty/alert rules]@{ assigned: 'agent-readiness' }
    [Incident response playbooks]@{ assigned: 'agent-readiness' }
    [Real-time deploy impact]@{ assigned: 'agent-readiness' }
    [Log sanitization/scrubbing]@{ assigned: 'agent-readiness' }
    [Analytics instrumentation]@{ assigned: 'agent-readiness' }
    [Errors to actionable issues]@{ assigned: 'agent-readiness' }

  Epics
    [Migrate to HTMX]@{ assigned: 'frontend', ticket: 10 }

  Backlog
    [Add blurred image placeholders - Plaiceholder-style progressive blur]@{
      assigned: 'frontend'
    }
    [Door cards - printable room schedules]@{ assigned: 'panel' }
    [Konwencik app sync]@{ assigned: 'panel' }
    [Add gh cli]@{ assigned: 'agent-readiness' }
    [TypeScript/mypy strict mode]@{ assigned: 'agent-readiness' }
    [Test coverage thresholds]@{ assigned: 'agent-readiness' }
    [Isolated/parallel test execution]@{ assigned: 'agent-readiness' }
    [AGENTS.md file]@{ assigned: 'agent-readiness' }
    [Claude skills definitions]@{ assigned: 'agent-readiness' }
    [Structured issue templates]@{ assigned: 'agent-readiness' }
    [Pull request templates]@{ assigned: 'agent-readiness' }
    [Development container configuration]@{ assigned: 'agent-readiness' }
    [CODEOWNERS file]@{ assigned: 'agent-readiness' }
    [Structured logging]@{ assigned: 'agent-readiness' }
    [Support Markdown in Session.description]@{
      assigned: 'sessions',
      ticket: 9
    }
    [Sphere creation command]@{ assigned: 'management', ticket: 14 }
    [Add versioning and changelog]@{ assigned: 'documentation', ticket: 23 }
    [Venues rework]@{ assigned: 'panel', ticket: 155 }

  Roadmap
    [Session hosts list - discount tiers and confirmation workflow]@{
      assigned: 'panel'
    }
    [Change log for timetable history - marketing notifications]@{
      assigned: 'panel'
    }
    [Organizer permissions - by program category]@{ assigned: 'panel' }
    [News/announcements - for event page]@{ assigned: 'panel' }
    [View and edit proposals]@{ assigned: 'user-proposals' }
    [Profile page - current and past proposals with statuses]@{
      assigned: 'user-proposals'
    }
    [Resend old proposal]@{ assigned: 'user-proposals' }

  Sprint
    [Proposals management - filterable list and accept/reject workflow]@{
      assigned: 'panel'
    }
    [Timetable builder - drag-and-drop scheduling and conflict detection]@{
      assigned: 'panel'
    }
    [Program categories - configurable submission forms]@{ assigned: 'panel' }
    [Event settings - discount tiers, submission periods]@{ assigned: 'panel' }
```
