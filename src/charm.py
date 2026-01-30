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

import json
import logging
import re
from typing import Optional

import ops

logger = logging.getLogger(__name__)

RELATION_NAME = "traefik-route"


class TraefikK8SPathRedirectorCharm(ops.CharmBase):
    """Publish a Traefik route for path redirects."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.framework.observe(self.on.config_changed, self._on_reconcile)
        relation_events = self.on[RELATION_NAME]
        self.framework.observe(relation_events.relation_created, self._on_reconcile)
        self.framework.observe(relation_events.relation_joined, self._on_reconcile)
        self.framework.observe(relation_events.relation_changed, self._on_reconcile)
        self.framework.observe(relation_events.relation_broken, self._on_reconcile)
        self.framework.observe(self.on.leader_elected, self._on_reconcile)
        self.framework.observe(self.on.upgrade_charm, self._on_reconcile)

    def _on_reconcile(self, event: ops.EventBase) -> None:
        from_path = str(self.model.config["from_path"]).strip()
        to_path = str(self.model.config["to_path"]).strip()
        error = self._validate_paths(from_path, to_path)
        if error:
            self.unit.status = ops.BlockedStatus(error)
            return

        relation = self.model.get_relation(RELATION_NAME)
        if not relation:
            self.unit.status = ops.WaitingStatus("waiting for traefik-route relation")
            return

        if not self.unit.is_leader():
            self.unit.status = ops.WaitingStatus("waiting for leader")
            return

        relation.data[self.app]["config"] = json.dumps(
            self._build_traefik_config(from_path, to_path)
        )
        self.unit.status = ops.ActiveStatus()

    def _validate_paths(self, from_path: str, to_path: str) -> Optional[str]:
        if not from_path or not from_path.startswith("/"):
            return "from_path must start with '/'"
        if not to_path or not to_path.startswith("/"):
            return "to_path must start with '/'"
        return None

    def _build_traefik_config(self, from_path: str, to_path: str) -> dict:
        router_name = f"{self.app.name}-path-redirect"
        middleware_name = f"{self.app.name}-path-redirect-middleware"
        escaped_from = re.escape(from_path)
        redirect_regex = rf"^(https?://[^/]+){escaped_from}(.*)$"
        replacement = f"${{1}}{to_path}${{2}}"
        return {
            "http": {
                "routers": {
                    router_name: {
                        "rule": f"PathPrefix(`{from_path}`)",
                        "service": "noop@internal",
                        "middlewares": [middleware_name],
                    }
                },
                "middlewares": {
                    middleware_name: {
                        "redirectRegex": {
                            "regex": redirect_regex,
                            "replacement": replacement,
                            "permanent": True,
                        }
                    }
                },
            }
        }


if __name__ == "__main__":  # pragma: nocover
    ops.main(TraefikK8SPathRedirectorCharm)
