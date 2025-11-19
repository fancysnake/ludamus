# Testing Strategy

## Component tests

Rules:

- common coverage should be 100%
- Write tests in classes

### Unit tests

Yes: classes, functions

No: views, commands

Structure: mimic code

Rules:

- mock at the highest level to avoid side effects
- check all mock calls
- no database

### Integration tests

Yes: views, commands

No: classes, functions

Structure: `view_module/test_url_name.py`

Rules:

- mock at the lowest level or not mock if possible
- check all mock calls
- check all side effects

Fixtures:

- Use pytest-factoryboy fixtures

Asserts:

- template name
- response context (including different cases for empty/non empty value
  of different keys)
- redirect location

## End-to-End tests

Yes: Full features, complete flows

## Migration to the new strategy

1. Review current integration tests and move them to correct directories and
   files.
2. If there are any existing tests that don't test views consider removing them
   or adding them to unit tests.
3. Ensure that after this the coverage of component tests is 100%.
4. Add e2e tests for current dynamic features.
