# ludamus

Event management website

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Code style: djLint](https://img.shields.io/badge/html%20style-djLint-blue.svg)](https://github.com/djlint/djlint)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)
![Static Badge](https://img.shields.io/badge/type%20checked-mypy-039dfc)
[![codecov](https://codecov.io/github/fancysnake/ludamus/graph/badge.svg?token=DB3HZP1OWT)](https://codecov.io/github/fancysnake/ludamus)

## Development

```bash
mise install      # Install Python, create venv
poetry install    # Install dependencies
mise run start    # Run Django dev server
```

### Tailwind CSS

Uses [django-tailwind-cli](https://github.com/django-commons/django-tailwind-cli) - no Node.js required.

`mise run start` runs Django + Tailwind watch together. CLI binary auto-downloads on first run.

**Deployment:**
```bash
mise run build-tailwind  # Build production CSS (run before collectstatic)
```
