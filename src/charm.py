#!/usr/bin/env python3
# Copyright 2026 alexlukens
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import logging
import re
from typing import Optional

import yaml

import ops
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer

logger = logging.getLogger(__name__)

RELATION_NAME = "traefik-route"


class TraefikK8SPathRedirectorCharm(ops.CharmBase):
    """Publish a Traefik route for path redirects."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self._route_requirer: Optional[TraefikRouteRequirer] = None
        self.framework.observe(self.on.config_changed, self._on_reconcile)
        self.framework.observe(self.on.leader_elected, self._on_reconcile)
        self.framework.observe(self.on.upgrade_charm, self._on_reconcile)
        self.framework.observe(
            self.on[RELATION_NAME].relation_created, self._on_relation_created
        )
        self._ensure_route_requirer()

    def _on_relation_created(self, event: ops.RelationEvent) -> None:
        self._ensure_route_requirer(event.relation)
        self._on_reconcile(event)

    def _on_route_ready(self, event: ops.EventBase) -> None:
        self._on_reconcile(event)

    def _ensure_route_requirer(self, relation: Optional[ops.Relation] = None) -> None:
        if self._route_requirer:
            return
        relation = relation or self.model.get_relation(RELATION_NAME)
        if not relation:
            return
        self._route_requirer = TraefikRouteRequirer(self, relation, RELATION_NAME, raw=True)
        self.framework.observe(self._route_requirer.on.ready, self._on_route_ready)

    def _on_reconcile(self, event: ops.EventBase) -> None:
        direct_redirects, error = self._parse_redirect_map(
            self.model.config["direct_path_redirects"], "direct_path_redirects"
        )
        if error:
            self.unit.status = ops.BlockedStatus(error)
            return

        regex_redirects, error = self._parse_redirect_map(
            self.model.config["regex_path_redirects"], "regex_path_redirects"
        )
        if error:
            self.unit.status = ops.BlockedStatus(error)
            return

        error = self._validate_paths(direct_redirects, regex_redirects)
        if error:
            self.unit.status = ops.BlockedStatus(error)
            return

        self._ensure_route_requirer()
        relation = self.model.get_relation(RELATION_NAME)
        if not relation:
            self.unit.status = ops.WaitingStatus("waiting for traefik-route relation")
            return

        if not self.unit.is_leader():
            self.unit.status = ops.WaitingStatus("waiting for leader")
            return

        if not self._route_requirer:
            self.unit.status = ops.WaitingStatus("waiting for traefik-route relation")
            return

        self._route_requirer.submit_to_traefik(
            config=self._build_traefik_config(direct_redirects, regex_redirects)
        )
        self.unit.status = ops.ActiveStatus()

    def _validate_paths(
        self, direct_redirects: dict[str, str], regex_redirects: dict[str, str]
    ) -> Optional[str]:
        if not direct_redirects and not regex_redirects:
            return "at least one redirect must be configured"

        error = self._validate_redirect_map(
            direct_redirects, "direct_path_redirects", from_path_is_regex=False
        )
        if error:
            return error

        return self._validate_redirect_map(
            regex_redirects, "regex_path_redirects", from_path_is_regex=True
        )

    def _validate_redirect_map(
        self,
        redirects: dict[str, str],
        name: str,
        *,
        from_path_is_regex: bool,
    ) -> Optional[str]:
        for from_path, to_path in redirects.items():
            if not from_path:
                return f"{name} keys must be non-empty"
            if not from_path_is_regex and not from_path.startswith("/"):
                return f"{name} keys must start with '/'"
            if not to_path:
                return f"{name} values must be non-empty"
            if not self._is_absolute_url(to_path) and not to_path.startswith("/"):
                return f"{name} values must start with '/' or be an absolute URL"
        return None

    def _build_traefik_config(
        self, direct_redirects: dict[str, str], regex_redirects: dict[str, str]
    ) -> dict:
        routers: dict[str, dict] = {}
        middlewares: dict[str, dict] = {}
        index = 0

        for from_path, to_path in direct_redirects.items():
            self._add_redirect_entry(
                routers, middlewares, index, from_path, to_path, from_path_is_regex=False
            )
            index += 1

        for from_path, to_path in regex_redirects.items():
            self._add_redirect_entry(
                routers, middlewares, index, from_path, to_path, from_path_is_regex=True
            )
            index += 1

        return {"http": {"routers": routers, "middlewares": middlewares}}

    def _add_redirect_entry(
        self,
        routers: dict[str, dict],
        middlewares: dict[str, dict],
        index: int,
        from_path: str,
        to_path: str,
        *,
        from_path_is_regex: bool,
    ) -> None:
        base_name = f"{self.app.name}-path-redirect-{index}"
        router_name = base_name
        tls_router_name = f"{base_name}-tls"
        middleware_name = f"{base_name}-middleware"
        rule_type = "PathRegexp" if from_path_is_regex else "PathPrefix"

        if from_path_is_regex:
            escaped_from = self._normalize_path_regex(from_path)
            redirect_regex = rf"^(https?://[^/]+){escaped_from}(.*)$"
            replacement = (
                f"{to_path}${{2}}"
                if self._is_absolute_url(to_path)
                else f"${{1}}{to_path}${{2}}"
            )
        else:
            escaped_from = re.escape(from_path)
            redirect_regex = rf"^(https?://[^/]+){escaped_from}$"
            replacement = to_path if self._is_absolute_url(to_path) else f"${{1}}{to_path}"

        routers[router_name] = {
            "rule": f"{rule_type}(`{from_path}`)",
            "service": "noop@internal",
            "middlewares": [middleware_name],
        }
        routers[tls_router_name] = {
            "rule": f"{rule_type}(`{from_path}`)",
            "service": "noop@internal",
            "middlewares": [middleware_name],
            "tls": {},
        }
        middlewares[middleware_name] = {
            "redirectRegex": {
                "regex": redirect_regex,
                "replacement": replacement,
                "permanent": True,
            }
        }

    @staticmethod
    def _parse_redirect_map(value: object, name: str) -> tuple[dict[str, str], Optional[str]]:
        if value is None:
            return {}, None

        if isinstance(value, dict):
            data = value
        else:
            raw_value = str(value).strip()
            if not raw_value:
                return {}, None
            try:
                data = yaml.safe_load(raw_value)
            except yaml.YAMLError as exc:
                return {}, f"{name} must be a map: {exc}"

        if data is None:
            return {}, None
        if not isinstance(data, dict):
            return {}, f"{name} must be a map"

        result: dict[str, str] = {}
        for key, val in data.items():
            cleaned_key = str(key).strip()
            cleaned_value = str(val).strip()
            result[cleaned_key] = cleaned_value
        return result, None

    @staticmethod
    def _normalize_path_regex(value: str) -> str:
        if value.startswith("^"):
            value = value[1:]
        if value.endswith("$"):
            value = value[:-1]
        return value

    @staticmethod
    def _is_absolute_url(value: str) -> bool:
        return value.startswith("http://") or value.startswith("https://")


if __name__ == "__main__":  # pragma: nocover
    ops.main(TraefikK8SPathRedirectorCharm)
