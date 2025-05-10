from enum import StrEnum
from pydantic import BaseModel


class EnvType(StrEnum):
    common = "common"
    local = "local"
    dev = "dev"
    staging = "staging"
    prod = "prod"


class WebappAuthType(StrEnum):
    b2c = "b2c"
    b2b = "b2b"


class InstancesType(BaseModel):
    db_size: str = "db-s-1vcpu-1gb"
    k8_node_pool_size: str = "s-4vcpu-8gb"
    k8_min_node_count: int = 4
    k8_max_node_count: int = 6

    caching_size: str = "db-s-1vcpu-1gb"
    caching_node_count: int = 1
    pg_pool_size: int = 20
    default_region: str = "lon1"
    db_cluster_node_count: int = 1

    maintenance_window_day: str = "sunday"
    maintenance_window_time: str = "04:00"

    es_instance_size: str = "gcp-storage-optimized"


class EnvInstanceType(BaseModel):
    instances: InstancesType
    env_type: EnvType


class Webapp(BaseModel):
    name: str
    auth_type: WebappAuthType = WebappAuthType.b2c
    is_root: bool = False
    dev_port: int = 3000


class DigitalOceanProvider(BaseModel):
    token: str
    spaces_access_id: str
    spaces_secret_key: str
    docker_reg_username: str
    service_region: str = "lon1"
    bucket_region: str = "fra1"


class Auth0Provider(BaseModel):
    domain: str
    client_id: str
    client_secret: str


class GithubProvider(BaseModel):
    token: str
    owner: str


class CloudflareProvider(BaseModel):
    token: str
    email: str


class OnePasswordProvider(BaseModel):
    service_account_token: str
    vault_id: str
    vault_name: str
    credentials: dict
    op_connect_token: str


class DatadogProvider(BaseModel):
    api_key: str
    app_key: str
    api_url: str = "https://api.datadoghq.eu/"
    region: str = "datadoghq.eu"


class ElasticCloudProvider(BaseModel):
    api_key: str


class DjangoCeleryAppProvider(BaseModel):
    flower_user: str
    flower_password: str
    django_superuser_username: str
    django_superuser_password: str
    django_superuser_email: str


class Provider(BaseModel):
    digitalocean: DigitalOceanProvider
    auth0: Auth0Provider
    github: GithubProvider
    cloudflare: CloudflareProvider
    onepassword: OnePasswordProvider
    datadog: DatadogProvider
    elastic: ElasticCloudProvider
    django_celery_app: DjangoCeleryAppProvider


class EnvVars(BaseModel):
    name: str
    value: str
    env_type: EnvType
    app_name: str


class EnvProviders(BaseModel):
    provider: Provider
    env_type: EnvType


class FullStackDeployment(BaseModel):
    project_name: str
    env_types: list[EnvType] = [EnvType.common, EnvType.local, EnvType.dev]
    instances: list[EnvInstanceType]
    webapps: list[Webapp]
    roles: list[str]
    entities: list[str]
    main_domain: str
    env_vars: list[EnvVars] = []
    providers: list[EnvProviders]


class Auth0WebappSetupOutput(BaseModel):
    base_url: str
    scopes: list[str]
    domain: str
    identifier: str
    client_id: str
    client_secret: str
    app_name: str
    generated_secret: str


class Auth0ApiSetupOutput(BaseModel):
    domain: str
    identifier: str
    client_id: str
    client_secret: str


class Auth0SetupOutput(BaseModel):
    audience: str
    web_apps: list[Auth0WebappSetupOutput] = []
    rest_api: Auth0ApiSetupOutput
    db_connection_id: str


class GithubSetupOutput(BaseModel):
    repo_name: str
    repo_url: str
    repo_id: str


class DataDogSetupOutput(BaseModel):
    client_token: str
    application_id: str
    site: str
    app_name: str
