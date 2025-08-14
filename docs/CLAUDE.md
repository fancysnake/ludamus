# Claude Editing Guildelines

## Development

- Don't add comments or docstrings, unless it's absolutely required to
  understand code logic
- In views use TemplateResponse for creating response object

## Testing

- Use faker for generating test data
- Move common test setup to pytest fixtures
- Fixtures should use simple names, like: site, event, time_slot or names
  representing their state, like published_event
- When naming variables, instead of using numbers (entity1, entity2), where
  there are only two entities use format like: entity, other_entity
- User client or authenticated_client for testing views
- use http.HTTPStatus for request status code assertions
