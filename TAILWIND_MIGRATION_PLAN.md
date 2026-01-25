# Tailwind 4 Migration Plan

## Overview

Replace Bootstrap 5 with production-grade Tailwind 4, matching mockup-1.html design (Outfit font, warm/coral/teal palette, playful aesthetic).

## Build System

**Tool**: [django-tailwind-cli](https://github.com/django-commons/django-tailwind-cli)
- No Node.js dependency
- Auto-downloads Tailwind CLI binary (pinned version in settings)
- Integrated with Django management commands

## File Structure

```
src/ludamus/
├── static/
│   ├── css/
│   │   ├── index.css     # Source: @theme config + components
│   │   └── output.css    # Generated (gitignored locally, built in CI/Docker)
│   └── vendor/
│       └── htmx.min.js   # Keep - remove Bootstrap files
```

## Phase 1: Infrastructure ✅

### 1.1 Settings
```python
INSTALLED_APPS = [..., "django_tailwind_cli", ...]

TAILWIND_CLI_VERSION = "4.1.18"
TAILWIND_CLI_SRC_CSS = "static/css/index.css"
TAILWIND_CLI_DIST_CSS = "css/output.css"
```

### 1.2 mise.toml tasks
```toml
[tasks.start]
description = "Start Django + Tailwind watch mode"
run = "django-admin tailwind runserver"

[tasks.build-tailwind]
description = "Build Tailwind CSS (production)"
run = "django-admin tailwind build"
```

### 1.3 index.css with @theme (Tailwind 4 CSS-first config)

Colors from mockup-1.html:
- **warm**: cream tones (#fdfcfb → #252220)
- **coral**: primary accent (#fef5f3 → #842a1b, main: #f85a3c)
- **teal**: secondary (#f0fdfa → #134e45, main: #14b89b)

Components layer:
- `.btn-primary`, `.btn-secondary`, `.btn-teal`
- `.alert-*` variants
- `.card`, `.card-header`, `.card-body`

### 1.4 Dockerfile
```dockerfile
# Build Tailwind CSS (django-tailwind-cli downloads binary automatically)
RUN django-admin tailwind build
```

### 1.5 Form templatetags ✅
- `{% tw_form form %}` - render full form
- `{% tw_field field %}` - render single field
- Replaces `{% bootstrap_form %}` and `{% bootstrap_field %}`

## Phase 2: Base Template Migration

Convert `base.html`:
1. Replace Bootstrap CSS with `output.css`
2. Keep HTMX
3. Convert navbar to Tailwind (sticky, warm-50 bg, coral accents)
4. Convert messages to `.alert-*` components
5. Convert footer

## Phase 3: Template Migration (by complexity)

### Tier 1 - Simple (5 templates)
- `crowd/login_required.html`
- `crowd/user/edit.html`
- `crowd/user/connected.html`
- `flatpages/default.html`
- `404_dynamic.html`, `500_dynamic.html`

### Tier 2 - Forms (4 templates)
- `chronology/propose_session.html`
- `chronology/accept_proposal.html`
- `chronology/enroll_select.html`
- `chronology/anonymous_*.html`

### Tier 3 - Index (1 template)
- `index.html` - event cards grid

### Tier 4 - Complex (2 templates)
- `chronology/_session_card.html` - match mockup card design
- `chronology/event.html` - largest template, do last

### Tier 5 - Panel ✅
- `panel/base.html` - switched from CDN to output.css

## Phase 4: Cleanup

1. Remove from settings:
   - `django_bootstrap5` from INSTALLED_APPS
   - Bootstrap entries from VENDOR_DEPENDENCIES
2. Delete files:
   - `static/vendor/bootstrap*`
   - `static/css/common.css`
   - `static/css/custom.css`
3. Remove from templates:
   - `{% load django_bootstrap5 %}`
   - Bootstrap class references

## Icon Strategy

Replace Bootstrap Icons with heroicons (already installed):
- `<i class="bi bi-calendar">` → `{% heroicon_outline "calendar" %}`
- ~25 icons to map

## Key Files to Modify

| File | Action |
|------|--------|
| `.gitignore` | Add `src/ludamus/static/css/output.css` ✅ |
| `mise.toml` | Add django-tailwind-cli tasks ✅ |
| `static/css/index.css` | Create with @theme ✅ |
| `Dockerfile` | Add `django-admin tailwind build` ✅ |
| `config/settings.py` | Add django_tailwind_cli, update VENDOR_DEPENDENCIES |
| `templates/base.html` | Full conversion |
| `templatetags/tailwind_forms.py` | Port from tailwind branch ✅ |

## Verification

1. `mise run start` - runs Django + Tailwind watch
2. `mise run build-tailwind` - generates output.css
3. Visual check: pages render with new design
4. `mise run test` - all tests pass
5. `docker build .` - builds successfully

## Decisions

- **Font hosting**: Google Fonts CDN (simple, fast)
- **output.css**: Gitignored, generated in CI/Docker
- **Migration**: Parallel - keep Bootstrap loaded until all templates converted
- **No tailwind.config.js**: Tailwind 4 uses CSS-first config via `@theme` in index.css
