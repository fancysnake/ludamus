# PR Split Plan

- Schema and DTOs: migrations 0026–0030 for event location fields, sphere hero_description/visibility/images; model and DTO updates; adjust unit tests.
- Root landing: Index root branch plus `templates/root/index.html` listing public spheres; depends on visibility from schema.
- Event list hero: `templates/index.html` hero using `current_sphere.hero_description` with supporting CSS (hero/navbar/common); avoid theme removals here.
- Event detail hero/location: `templates/chronology/event.html` location display and optional map embed with map tag/filter; scoped CSS; depends on schema.
- Assets/themes: vendor `static/css/bootstrap.css`, fonts, theme removals, cinematic/prose styles; isolated to static changes.
- Docs/tooling: `AGENTS.md`, `docs/UI_STYLE.md`, `.pre-commit-config.yaml`, `.pylintrc`, `pyproject.toml` tweaks; no app behavior changes.

