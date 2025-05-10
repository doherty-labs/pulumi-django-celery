from providers import get_common_provider, get_dev_provider, get_local_provider
from pulumi_create_stack import create_pulumi_program
from schema import (
    EnvInstanceType,
    EnvProviders,
    EnvType,
    FullStackDeployment,
    InstancesType,
    Webapp,
    WebappAuthType,
)
from pulumi import automation as auto


def build_stack(
    env: EnvType,
    config: FullStackDeployment,
):
    def pulumi_program():
        return create_pulumi_program(env, config)

    stack_name = f"{config.project_name}-{env.value}"
    provider = list(filter(lambda x: x.env_type == env, config.providers))[0].provider
    stack = auto.create_or_select_stack(
        stack_name=stack_name,
        project_name=config.project_name,
        program=pulumi_program,
    )

    stack.set_config(
        "digitalocean:token", auto.ConfigValue(provider.digitalocean.token)
    )
    stack.set_config(
        "digitalocean:spacesAccessId",
        auto.ConfigValue(provider.digitalocean.spaces_access_id),
    )
    stack.set_config(
        "digitalocean:spacesSecretKey",
        auto.ConfigValue(provider.digitalocean.spaces_secret_key),
    )

    stack.set_config("ec:apikey", auto.ConfigValue(provider.elastic.api_key))

    stack.set_config("auth0:clientId", auto.ConfigValue(provider.auth0.client_id))
    stack.set_config(
        "auth0:clientSecret", auto.ConfigValue(provider.auth0.client_secret)
    )
    stack.set_config("auth0:domain", auto.ConfigValue(provider.auth0.domain))

    stack.set_config("github:token", auto.ConfigValue(provider.github.token))
    stack.set_config("github:owner", auto.ConfigValue(provider.github.owner))

    stack.set_config("cloudflare:apiToken", auto.ConfigValue(provider.cloudflare.token))

    stack.set_config("datadog:apiKey", auto.ConfigValue(provider.datadog.api_key))
    stack.set_config("datadog:apiUrl", auto.ConfigValue(provider.datadog.api_url))
    stack.set_config("datadog:appKey", auto.ConfigValue(provider.datadog.app_key))

    stack.set_config(
        "onepassword:serviceAccountToken",
        auto.ConfigValue(provider.onepassword.service_account_token),
    )

    return stack


def create_stack(
    env: EnvType,
    config: FullStackDeployment,
) -> dict:
    stack = build_stack(env, config)
    up_res = stack.up(on_output=print, refresh=True, diff=True)
    return {"env": env.value, "outputs": up_res.outputs}


def delete_stack(
    env: EnvType,
    config: FullStackDeployment,
) -> dict:
    stack = build_stack(env, config)
    stack.destroy(on_output=print)
    stack.workspace.remove_stack(stack_name=stack.name)


if __name__ == "__main__":
    ws = auto.LocalWorkspace()
    ws.install_plugin("github", "v6.7.0")
    ws.install_plugin("digitalocean", "v4.40.1")
    ws.install_plugin("auth0", "v3.14.0")
    ws.install_plugin("ec", "v0.10.5")
    ws.install_plugin("cloudflare", "v5.49.1")
    ws.install_plugin_from_server(
        "onepassword", "v1.1.3", "github://api.github.com/1Password/pulumi-onepassword"
    )
    ws.install_plugin("datadog", "v4.46.0")

    standard_instance_type = InstancesType(
        db_size="db-s-1vcpu-1gb",
        k8_node_pool_size="s-4vcpu-8gb",
        k8_min_node_count=7,
        k8_max_node_count=7,
        caching_size="db-s-1vcpu-1gb",
        pg_pool_size=20,
        default_region="lon1",
    )

    config = FullStackDeployment(
        project_name="xxxxx",
        env_types=[EnvType.common, EnvType.local, EnvType.dev],
        instances=[
            EnvInstanceType(
                instances=standard_instance_type,
                env_type=EnvType.dev,
            ),
        ],
        webapps=[
            Webapp(
                name="landing",
                auth_type=WebappAuthType.b2c,
                dev_port=3000,
                is_root=True,
            ),
            Webapp(name="merchant", auth_type=WebappAuthType.b2b, dev_port=3002),
            Webapp(name="operations", auth_type=WebappAuthType.b2c, dev_port=3003),
        ],
        roles=["admin", "operations", "partner", "merchant"],
        entities=[
            "merchant",
            "partner",
            "customer",
            "order",
            "product",
        ],
        main_domain="xxxxx.com",
        providers=[
            EnvProviders(env_type=EnvType.common, provider=get_common_provider()),
            EnvProviders(env_type=EnvType.local, provider=get_local_provider()),
            EnvProviders(env_type=EnvType.dev, provider=get_dev_provider()),
        ],
    )

    for env in config.env_types:
        create_stack(env, config)
