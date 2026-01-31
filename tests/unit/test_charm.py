# Copyright 2026 alexlukens
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import yaml

from ops import testing

from charm import RELATION_NAME, TraefikK8SPathRedirectorCharm


def test_waiting_without_relation():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    state_in = testing.State(config={"direct_path_redirects": {"/from": "/to"}})

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert isinstance(state_out.unit_status, testing.WaitingStatus)


def test_invalid_config_blocks():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    state_in = testing.State(
        config={"direct_path_redirects": {"from": "/to"}}
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert isinstance(state_out.unit_status, testing.BlockedStatus)
    assert "direct_path_redirects" in state_out.unit_status.message


def test_relation_data_published():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    relation = testing.Relation(
        endpoint=RELATION_NAME, interface="traefik_route", remote_app_name="traefik-k8s"
    )
    state_in = testing.State(
        leader=True,
        relations={relation},
        config={"direct_path_redirects": {"/from": "/to"}},
    )

    state_out = ctx.run(ctx.on.relation_created(relation), state_in)

    relation_out = state_out.get_relation(relation.id)
    route_config = yaml.safe_load(relation_out.local_app_data["config"])
    router_name = "traefik-k8s-path-redirector-path-redirect-0"
    tls_router_name = "traefik-k8s-path-redirector-path-redirect-0-tls"
    middleware_name = "traefik-k8s-path-redirector-path-redirect-0-middleware"
    router = route_config["http"]["routers"][router_name]
    tls_router = route_config["http"]["routers"][tls_router_name]
    middleware = route_config["http"]["middlewares"][middleware_name]
    assert router["rule"] == "PathPrefix(`/from`)"
    assert router["middlewares"] == [middleware_name]
    assert tls_router["rule"] == "PathPrefix(`/from`)"
    assert tls_router["middlewares"] == [middleware_name]
    assert middleware["redirectRegex"]["regex"] == "^(https?://[^/]+)/from$"
    assert middleware["redirectRegex"]["replacement"] == "${1}/to"
    assert relation_out.local_app_data["raw"] == "True"
    assert state_out.unit_status == testing.ActiveStatus()


def test_regex_from_path_allowed():
    ctx = testing.Context(TraefikK8SPathRedirectorCharm)
    relation = testing.Relation(
        endpoint=RELATION_NAME, interface="traefik_route", remote_app_name="traefik-k8s"
    )
    state_in = testing.State(
        leader=True,
        relations={relation},
        config={"regex_path_redirects": {"^/old(/.*)?$": "/new"}},
    )

    state_out = ctx.run(ctx.on.relation_created(relation), state_in)

    relation_out = state_out.get_relation(relation.id)
    route_config = yaml.safe_load(relation_out.local_app_data["config"])
    router_name = "traefik-k8s-path-redirector-path-redirect-0"
    tls_router_name = "traefik-k8s-path-redirector-path-redirect-0-tls"
    middleware_name = "traefik-k8s-path-redirector-path-redirect-0-middleware"
    router = route_config["http"]["routers"][router_name]
    tls_router = route_config["http"]["routers"][tls_router_name]
    middleware = route_config["http"]["middlewares"][middleware_name]
    assert router["rule"] == "PathRegexp(`^/old(/.*)?$`)"
    assert tls_router["rule"] == "PathRegexp(`^/old(/.*)?$`)"
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
            "direct_path_redirects": {"/from": "https://ubuntu.net/hello"},
        },
    )

    state_out = ctx.run(ctx.on.relation_created(relation), state_in)

    relation_out = state_out.get_relation(relation.id)
    route_config = yaml.safe_load(relation_out.local_app_data["config"])
    middleware_name = "traefik-k8s-path-redirector-path-redirect-0-middleware"
    middleware = route_config["http"]["middlewares"][middleware_name]
    assert middleware["redirectRegex"]["replacement"] == "https://ubuntu.net/hello"
