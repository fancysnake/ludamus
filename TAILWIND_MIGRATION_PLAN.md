# Tailwind 4 Migration Plan

## Overview

Replace Bootstrap 5 with production-grade Tailwind 4, matching mockup-1.html design (Outfit font, warm/coral/teal palette, playful aesthetic).

## Build System

**Tool**: Tailwind CLI standalone (via mise)
- No Node.js dependency in main project
- ~15MB binary, fast cold starts
- Native mise integration

## File Structure

```
src/ludamus/
├── static/
│   ├── css/
│   │   ├── input.css      # Source: @theme config + components
│   │   └── output.css     # Generated (gitignored locally, built in CI/Docker)
│   └── vendor/
│       └── htmx.min.js    # Keep - remove Bootstrap files
```

## Phase 1: Infrastructure

### 1.1 mise.toml additions
```toml
[tools]
tailwindcss = "4"

[tasks.tw]
description = "Tailwind watch mode"
run = "tailwindcss -i src/ludamus/static/css/input.css -o src/ludamus/static/css/output.css --watch"

[tasks.tw-build]
description = "Build Tailwind (minified)"
run = "tailwindcss -i src/ludamus/static/css/input.css -o src/ludamus/static/css/output.css --minify"

[tasks.dev]
description = "Django + Tailwind watch"
run = "tailwindcss -i src/ludamus/static/css/input.css -o src/ludamus/static/css/output.css --watch & django-admin runserver localhost:8000"
```

### 1.2 input.css with @theme (Tailwind 4 CSS-first config)

Colors from mockup-1.html:
- **warm**: cream tones (#fdfcfb → #252220)
- **coral**: primary accent (#fef5f3 → #842a1b, main: #f85a3c)
- **teal**: secondary (#f0fdfa → #134e45, main: #14b89b)

Components layer:
- `.form-input`, `.form-select`, `.form-textarea` (replacing django_bootstrap5)
- `.btn-primary`, `.btn-secondary`, `.btn-teal`
- `.alert-*` variants
- `.card`, `.card-header`, `.card-body`
- Session card styles from mockup (`.session-card`, gradient overlays)

### 1.3 tailwind.config.js (content paths)
```js
export default {
  content: [
    "./src/ludamus/templates/**/*.html",
    "./src/ludamus/static/**/*.js",
  ],
}
```

### 1.4 Dockerfile update
```dockerfile
# Add before collectstatic
RUN curl -sL https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    -o /usr/local/bin/tailwindcss && chmod +x /usr/local/bin/tailwindcss
RUN tailwindcss -i src/ludamus/static/css/input.css \
                -o src/ludamus/static/css/output.css --minify
```

### 1.5 Form templatetags

Port `tailwind_forms.py` from tailwind branch:
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

### Tier 5 - Panel (already Tailwind)
- `panel/base.html` - switch from CDN to output.css
- Update color palette to match

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
| `.gitignore` | Add `src/ludamus/static/css/output.css` |
| `mise.toml` | Add tailwindcss tool + tasks |
| `static/css/input.css` | Create with @theme |
| `tailwind.config.js` | Create with content paths |
| `Dockerfile` | Add Tailwind build step |
| `config/settings.py` | Remove django_bootstrap5, update VENDOR_DEPENDENCIES |
| `templates/base.html` | Full conversion |
| `templatetags/tailwind_forms.py` | Port from tailwind branch |
| `templates/forms/*.html` | Create field/form partials |

## Verification

1. `mise install` - installs Tailwind CLI
2. `mise run tw-build` - generates output.css
3. `mise run dev` - starts Django + watch mode
4. Visual check: pages render with new design
5. `mise run test` - all tests pass
6. `docker build .` - builds successfully
7. Check mockup-1.html side-by-side with event.html

## Decisions

- **Font hosting**: Google Fonts CDN (simple, fast)
- **output.css**: Gitignored, generated in CI/Docker
- **Migration**: Parallel - keep Bootstrap loaded until all templates converted
