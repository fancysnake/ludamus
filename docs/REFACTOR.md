# Refactor

This code is AI-generated mess. I'm going to gradually make it better,
to achieve satisfying level of code quality.

## Layers

I'm using my own idea for clean architecture code layout I called PLUMBING

- Pacts - ports/protocols
- Links - outbound adapters (to be used in binds only)
- Mills - domain logic (to be used in binds only)
- Binds - entrypoints
- Norms - settings (to be used in binds only)
- Gates - inbound adapters (to be used in binds only)
