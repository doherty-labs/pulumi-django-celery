import pulumi
from schema import (
    EnvType,
    FullStackDeployment,
)
import pulumi_github as github


def setup_github(config: FullStackDeployment) -> dict:
    # repo = github.Repository(
    #     name=config.project_name,
    #     resource_name=config.project_name,
    #     private=True,
    #     auto_init=True,
    # )

    repo = github.get_repository(name=config.project_name)

    service_account_token = list(
        filter(lambda x: x.env_type == EnvType.common, config.providers)
    )[0].provider.onepassword.service_account_token

    github.ActionsSecret(
        resource_name="op_service_account_token",
        repository=repo.name,
        plaintext_value=service_account_token,
        secret_name="OP_SERVICE_ACCOUNT_TOKEN",
    )

    output = {
        "repo_name": repo.name,
        "repo_url": repo.html_url,
        "repo_id": repo.id,
    }
    pulumi.export("github_repo", output)
    return output
