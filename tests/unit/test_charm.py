# Copyright 2026 alexlukens
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import json

from ops import testing

from charm import RELATION_NAME, TraefikK8SPathRedirectorCharm


def test_waiting_without_relation():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    state_in = testing.State(config={"from_path": "/from", "to_path": "/to"})

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert isinstance(state_out.unit_status, testing.WaitingStatus)


def test_invalid_config_blocks():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    state_in = testing.State(
        config={"from_path": "from", "to_path": "/to", "from_path_is_regex": False}
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert isinstance(state_out.unit_status, testing.BlockedStatus)
    assert "from_path" in state_out.unit_status.message


def test_relation_data_published():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    relation = testing.Relation(
        endpoint=RELATION_NAME, interface="traefik_route", remote_app_name="traefik-k8s"
    )
    state_in = testing.State(
        leader=True,
        relations={relation},
        config={"from_path": "/from", "to_path": "/to", "from_path_is_regex": False},
    )

    state_out = ctx.run(ctx.on.relation_joined(relation), state_in)

    relation_out = state_out.get_relation(relation.id)
    route_config = json.loads(relation_out.local_app_data["config"])
    router_name = "traefik-k8s-path-redirector-path-redirect"
    middleware_name = "traefik-k8s-path-redirector-path-redirect-middleware"
    router = route_config["http"]["routers"][router_name]
    middleware = route_config["http"]["middlewares"][middleware_name]
    assert router["rule"] == "PathPrefix(`/from`)"
    assert router["middlewares"] == [middleware_name]
    assert middleware["redirectRegex"]["replacement"] == "${1}/to${2}"
    assert state_out.unit_status == testing.ActiveStatus()


def test_regex_from_path_allowed():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    relation = testing.Relation(
        endpoint=RELATION_NAME, interface="traefik_route", remote_app_name="traefik-k8s"
    )
    state_in = testing.State(
        leader=True,
        relations={relation},
        config={"from_path": "^/old(/.*)?$", "to_path": "/new", "from_path_is_regex": True},
    )

    state_out = ctx.run(ctx.on.relation_joined(relation), state_in)

    relation_out = state_out.get_relation(relation.id)
    route_config = json.loads(relation_out.local_app_data["config"])
    router_name = "traefik-k8s-path-redirector-path-redirect"
    middleware_name = "traefik-k8s-path-redirector-path-redirect-middleware"
    router = route_config["http"]["routers"][router_name]
    middleware = route_config["http"]["middlewares"][middleware_name]
    assert router["rule"] == "PathRegexp(`^/old(/.*)?$`)"
    assert middleware["redirectRegex"]["regex"] == "^(https?://[^/]+)/old(/.*)?(.*)$"


def test_absolute_url_to_path_allowed():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    relation = testing.Relation(
        endpoint=RELATION_NAME, interface="traefik_route", remote_app_name="traefik-k8s"
    )
    state_in = testing.State(
        leader=True,
        relations={relation},
        config={
            "from_path": "/from",
            "to_path": "https://ubuntu.net/hello",
            "from_path_is_regex": False,
        },
    )

    state_out = ctx.run(ctx.on.relation_joined(relation), state_in)

    relation_out = state_out.get_relation(relation.id)
    route_config = json.loads(relation_out.local_app_data["config"])
    middleware_name = "traefik-k8s-path-redirector-path-redirect-middleware"
    middleware = route_config["http"]["middlewares"][middleware_name]
    assert middleware["redirectRegex"]["replacement"] == "https://ubuntu.net/hello${2}"
