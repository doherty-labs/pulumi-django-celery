import pulumi
from schema import (
    EnvType,
    FullStackDeployment,
    WebappAuthType,
)
import pulumi_auth0 as auth0
import pulumi_random as random

default_entity_permissions = ["create", "read", "update", "delete", "list", "analytics"]


def setup_auth0(env_type: EnvType, config: FullStackDeployment) -> dict:
    resource_prefix = f"{env_type.value}-{config.project_name}-"
    auth0_domain = list(filter(lambda x: x.env_type == env_type, config.providers))[
        0
    ].provider.auth0.domain
    resource_server = auth0.ResourceServer(
        resource_name=resource_prefix + "auth0-resource-server",
        identifier=f"https://{env_type.value}-api-{config.project_name}.{config.main_domain}",
        name=resource_prefix + "api",
        signing_alg="RS256",
        allow_offline_access=True,
        token_lifetime=8600,
        skip_consent_for_verifiable_first_party_clients=True,
        enforce_policies=True,
    )

    auth0_rest_api_client = auth0.Client(
        resource_name=resource_prefix + "auth0-rest-api-client",
        name=resource_prefix + "auth0-rest-api-client",
        app_type="non_interactive",
        is_first_party=True,
        jwt_configuration={
            "alg": "RS256",
        },
    )

    auth0_rest_api_client_secret = auth0.get_client(
        client_id=auth0_rest_api_client.client_id,
    ).client_secret

    roles_dict: dict = {}
    for role in config.roles:
        roles_dict[role] = auth0.Role(
            resource_name=resource_prefix + f"auth0-role-{role}",
            name=role,
            description=f"{role} role for {env_type.value}",
        ).id

    scopes: list[str] = ["openid", "profile", "email", "offline_access"]
    for entity in config.entities:
        for permission in default_entity_permissions:
            name = f"{permission}:{entity}"
            auth0.ResourceServerScope(
                resource_name=resource_prefix + f"auth0-scope-{name}",
                description=f"{permission} permission for {entity}",
                resource_server_identifier=resource_server.identifier,
                scope=name,
            )
            scopes.append(name)

    auth0.ClientGrant(
        resource_name=resource_prefix + "auth0-management-api-client-grant",
        client_id=auth0_rest_api_client.client_id,
        audience=f"https://{auth0_domain}/api/v2/",
        scopes=[
            "read:users",
            "create:users",
            "update:users",
            "delete:users",
            "read:connections",
            "read:organizations",
            "update:organizations",
            "create:organizations",
            "delete:organizations",
            "read:organization_members",
            "create:organization_members",
            "delete:organization_members",
            "read:organization_connections",
            "update:organization_connections",
            "create:organization_connections",
            "delete:organization_connections",
            "read:organization_member_roles",
            "create:organization_member_roles",
            "delete:organization_member_roles",
            "read:organization_invitations",
            "create:organization_invitations",
            "delete:organization_invitations",
            "read:organizations_summary",
            "read:roles",
            "create:roles",
            "delete:roles",
            "update:roles",
        ],
    )

    auth0.ClientGrant(
        resource_name=resource_prefix + "auth0-api-client-grant",
        client_id=auth0_rest_api_client.client_id,
        audience=resource_server.identifier,
        scopes=[scope for scope in scopes],
    )

    generated_secret = random.RandomUuid(
        resource_name=resource_prefix + "auth0-webapp-secret",
    ).result

    webapps: list[dict] = []
    for webapp in config.webapps:
        hosts = []
        base_url = ""

        if env_type == EnvType.local:
            base_url = f"http://localhost:{webapp.dev_port}"
            hosts = [base_url]

        if env_type in EnvType.dev:
            base_url = f"https://qa-{webapp.name}.{config.main_domain}"
            hosts = [
                base_url,
            ]

        if env_type in EnvType.staging:
            base_url = f"https://staging-{webapp.name}.{config.main_domain}"
            hosts = [
                base_url,
            ]

        if env_type == EnvType.prod and webapp.is_root is False:
            base_url = f"https://{webapp.name}.{config.main_domain}"
            hosts = [
                base_url,
            ]

        if env_type == EnvType.prod and webapp.is_root is True:
            base_url = f"https://{config.main_domain}"
            hosts = [
                base_url,
            ]

        webapp_client = auth0.Client(
            resource_name=resource_prefix + f"auth0-webapp-client-{webapp.name}",
            name=resource_prefix + f"auth0-webapp-client-{webapp.name}",
            app_type="regular_web",
            oidc_conformant=True,
            is_first_party=True,
            grant_types=["refresh_token", "authorization_code"],
            jwt_configuration={
                "alg": "RS256",
            },
            refresh_token={
                "leeway": 86400,
                "token_lifetime": 86400,
                "rotation_type": "rotating",
                "expiration_type": "expiring",
                "infinite_token_lifetime": False,
                "infinite_idle_token_lifetime": False,
            },
            callbacks=[f"{host}/auth/callback" for host in hosts],
            allowed_clients=hosts,
            allowed_origins=hosts,
            allowed_logout_urls=hosts,
            organization_require_behavior="post_login_prompt"
            if webapp.auth_type == WebappAuthType.b2b
            else "no_prompt",
            organization_usage="require"
            if webapp.auth_type == WebappAuthType.b2b
            else "deny",
        )

        webapp_client_secret = auth0.get_client(
            client_id=webapp_client.client_id,
        ).client_secret

        webapps.append(
            {
                "base_url": base_url,
                "scopes": " ".join(scopes),
                "identifier": resource_server.identifier,
                "client_id": webapp_client.client_id,
                "client_secret": webapp_client_secret,
                "domain": auth0_domain,
                "app_name": webapp.name,
                "generated_secret": generated_secret,
            }
        )

    db_connection = auth0.get_connection(name="Username-Password-Authentication")

    google_connection = auth0.get_connection(name="google-oauth2")

    output = {
        "audience": resource_server.identifier,
        "rest_api": {
            "domain": auth0_domain,
            "identifier": resource_server.identifier,
            "client_id": auth0_rest_api_client.client_id,
            "client_secret": auth0_rest_api_client_secret,
        },
        "db_connection_id": db_connection.id,
        "google_connection_id": google_connection.id,
        "roles": roles_dict,
    }

    for webapp in webapps:
        client_name = webapp.get("app_name") + "_client"
        output[client_name] = {
            "base_url": webapp.get("base_url"),
            "scopes": webapp.get("scopes"),
            "identifier": webapp.get("identifier"),
            "client_id": webapp.get("client_id"),
            "client_secret": webapp.get("client_secret"),
            "domain": webapp.get("domain"),
            "app_name": webapp.get("app_name"),
            "generated_secret": webapp.get("generated_secret"),
        }

    pulumi.export(
        "auth0_setup_output",
        output,
    )

    return output
