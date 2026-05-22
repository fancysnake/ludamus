"""Forms for the chronology event panel."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.utils.translation import gettext_lazy as _
from pydantic import ValidationError

from ludamus.pacts.chronology import IntegrationImplementationId

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ludamus.pacts.chronology import IntegrationImplementation, IntegrationKind
    from ludamus.pacts.multiverse import ConnectionDTO


def integration_signature(connection_id: int, config_json: dict[str, object]) -> str:
    canonical = json.dumps(config_json, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{connection_id}:{canonical}".encode()).hexdigest()


class EventIntegrationForm(forms.Form):
    """Add / edit form for an event integration of a given kind."""

    display_name = forms.CharField(label=_("Display name"), max_length=255, strip=True)
    implementation = forms.ChoiceField(label=_("Implementation"))
    connection = forms.ChoiceField(label=_("Connection"))
    config_json = forms.CharField(
        label=_("Configuration (JSON)"),
        widget=forms.Textarea(attrs={"rows": 12, "spellcheck": "false"}),
        initial="{}",
    )
    last_ok_signature = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(
        self,
        *args: Any,
        kind: IntegrationKind,
        implementations: Mapping[
            IntegrationImplementationId, IntegrationImplementation
        ],
        connections: Iterable[ConnectionDTO],
        initial_connection_id: int | None = None,
        initial_config_json: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.kind = kind
        self._implementations: dict[
            IntegrationImplementationId, IntegrationImplementation
        ] = dict(implementations)
        impl_field = cast("forms.ChoiceField", self.fields["implementation"])
        impl_field.choices = [
            (impl_id.value, impl_id.value) for impl_id in self._implementations
        ]
        conn_field = cast("forms.ChoiceField", self.fields["connection"])
        conn_field.choices = [(str(c.pk), c.display_name) for c in connections]
        self._initial_connection_id = initial_connection_id
        self._initial_config_json = initial_config_json

    def clean_implementation(self) -> IntegrationImplementationId:
        raw = self.cleaned_data.get("implementation") or ""
        try:
            return IntegrationImplementationId(raw)
        except ValueError as exc:
            raise forms.ValidationError(
                _("Unknown implementation for this kind.")
            ) from exc

    def clean_config_json(self) -> dict[str, object]:
        raw = self.cleaned_data.get("config_json") or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(
                _("Not valid JSON: %(error)s") % {"error": str(exc)}
            ) from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError(_("Configuration must be a JSON object."))
        return parsed

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        identifier = cleaned.get("implementation")
        config_json = cleaned.get("config_json")
        if isinstance(identifier, IntegrationImplementationId) and isinstance(
            config_json, dict
        ):
            if (impl := self._implementations.get(identifier)) is None:
                self.add_error(
                    "implementation", _("Unknown implementation for this kind.")
                )
            else:
                try:
                    impl.config_model.model_validate(config_json)
                except ValidationError as exc:
                    self._attach_pydantic_errors(exc)

        if not self.errors:
            self._enforce_check_signature(cleaned)
        return cleaned

    def _attach_pydantic_errors(self, exc: ValidationError) -> None:
        for err in exc.errors():
            path = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
            self.add_error("config_json", f"{path}: {err.get('msg', '')}")

    def _enforce_check_signature(self, cleaned: dict[str, object]) -> None:
        connection_id_raw = cleaned.get("connection")
        config_json = cleaned.get("config_json")
        if not isinstance(connection_id_raw, str) or not isinstance(config_json, dict):
            return
        connection_id = int(connection_id_raw)

        if (
            self._initial_connection_id == connection_id
            and self._initial_config_json == config_json
        ):
            return

        expected = integration_signature(connection_id, config_json)
        provided_raw = cleaned.get("last_ok_signature")
        provided = provided_raw.strip() if isinstance(provided_raw, str) else ""
        if provided != expected:
            self.add_error(
                None,
                _(
                    'Run "Check integration" against the current connection '
                    "and configuration before saving."
                ),
            )
