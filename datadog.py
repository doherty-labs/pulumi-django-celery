import pulumi
from schema import (
    EnvType,
    FullStackDeployment,
)
import pulumi_datadog as datadog


def setup_datadog(config: FullStackDeployment) -> dict:
    provider = list(filter(lambda x: x.env_type == EnvType.common, config.providers))[
        0
    ].provider
    datadog_provider = provider.datadog

    datadog_apps: dict = {
        "site": "datadoghq.eu",
        "api_key": datadog_provider.api_key,
        "app_key": datadog_provider.app_key,
        "api_url": datadog_provider.api_url,
    }

    for webapp in config.webapps:
        app = datadog.RumApplication(
            resource_name=webapp.name,
            name=webapp.name,
            type="browser",
        )

        datadog_apps[webapp.name] = {
            "client_token": app.client_token,
            "application_id": app.id,
            "site": "datadoghq.eu",
            "app_name": webapp.name,
        }

    pulumi.export(
        "datadog_apps",
        datadog_apps,
    )

    return datadog_apps
