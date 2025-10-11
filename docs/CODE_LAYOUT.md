# Code Layout

## URL structure

### Pages

Nouns, with slash in the end.

- **url:** `/{namespace}/({subnamespace}/)?{page}/{subpage}/`
- **template:** `/{namespace}/({subnamespace}/)?{page}/{subpage}.html`
- **view:** `({subnamespace})?{Page}{Subpage}PageView`

### Actions

Verbs, `do` prefix on page level, no slash in the end.

- **url:** `/{namespace}/({subnamespace}/)?({page}/{subpage}/)?do/{action}/{subaction}`
- **template:** none
- **view:** `({subnamespace})?({Page}{Subpage})?{Action}ActionView`

### Component

Nouns, `parts` prefix on page level, no slash in the end.

- **url:** `/{namespace}/({subnamespace}/)?({page}/{subpage}/)?parts/{part}`
- **template:** `/{namespace}/({subnamespace}/)?({page}/{subpage}/)?parts/{part}.html`
- **view:** `({subnamespace})?({Page}{Subpage})?{part}ComponentView`
