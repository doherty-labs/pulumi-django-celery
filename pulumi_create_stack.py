from auth0 import setup_auth0
from datadog import setup_datadog
from digitalocean_setup import DigitalOceanSetup
from elastic_setup import ElasticCloudSetup
from github import setup_github
from kubernetes_setup import KubernetesSetup
from schema import (
    EnvType,
    FullStackDeployment,
)

from vault_setup import VaultSetup


def create_pulumi_program(
    env_type: EnvType,
    config: FullStackDeployment,
):
    if env_type == EnvType.common:
        github = setup_github(config)
        datadog = setup_datadog(config)
        VaultSetup(
            env_type,
            config,
            {
                "github": github,
                "datadog": datadog,
            },
        ).setup()
        return

    if env_type == EnvType.local:
        auth = setup_auth0(env_type, config)
        VaultSetup(
            env_type,
            config,
            {
                "auth0": auth,
            },
        ).setup()

    if env_type in [EnvType.staging, EnvType.dev, EnvType.prod]:
        auth = setup_auth0(env_type, config)
        do = DigitalOceanSetup(env_type, config)
        do_config, k8_provider = do.setup()

        es = ElasticCloudSetup(env_type, config)
        es_config = es.setup()

        k8 = KubernetesSetup(
            env_type,
            config,
            k8_provider,
            {
                "digitalocean": do_config,
                "elastic": es_config,
                "auth0": auth,
            },
        )
        k8_secrets = k8.setup()

        VaultSetup(
            env_type,
            config,
            {
                "digitalocean": do_config,
                "elastic": es_config,
                "auth0": auth,
                "kubernetes": k8_secrets,
            },
        ).setup()
