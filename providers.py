

from schema import Auth0Provider, CloudflareProvider, DatadogProvider, DigitalOceanProvider, DjangoCeleryAppProvider, ElasticCloudProvider, GithubProvider, OnePasswordProvider, Provider

auth0_local = Auth0Provider(
    domain="xxxxx.us.auth0.com",
    client_id="xxxxx",
    client_secret="xxxxx",
)

auth0_dev = Auth0Provider(
    domain="xxxxx.uk.auth0.com",
    client_id="xxxxx",
    client_secret="xxxxx",
)

onepassword_local = OnePasswordProvider(
    service_account_token="ops_xxxxx",
    vault_id="xxxxx",
    vault_name="xxxxx",
    op_connect_token="xxxxx",
    credentials={
        "verifier": {
            "salt": "xxxxx",
            "localHash": "xxxxx",
        },
        "encCredentials": {
            "kid": "xxxxx",
            "enc": "xxxxx",
            "cty": "xxxxx",
            "iv": "xxxxx",
            "data": "xxxxx",
        },
        "version": "2",
        "deviceUuid": "xxxxx",
        "uniqueKey": {
            "alg": "xxxxx",
            "ext": True,
            "k": "xxxxx",
            "key_ops": ["encrypt", "decrypt"],
            "kty": "oct",
            "kid": "xxxxx",
        },
    },
)

onepassword_dev = OnePasswordProvider(
    service_account_token="ops_xxxxx",
    vault_id="xxxxx",
    vault_name="xxxxx",
    op_connect_token="xxxxx",
    credentials={
        "verifier": {
            "salt": "xxxxx",
            "localHash": "xxxxx",
        },
        "encCredentials": {
            "kid": "xxxxx",
            "enc": "xxxxx",
            "cty": "xxxxx",
            "iv": "xxxxx",
            "data": "xxxxx",
        },
        "version": "2",
        "deviceUuid": "xxxxx",
        "uniqueKey": {
            "alg": "xxxxx",
            "ext": True,
            "k": "xxxxx",
            "key_ops": ["encrypt", "decrypt"],
            "kty": "oct",
            "kid": "xxxxx",
        },
    },
)

onepassword_common = OnePasswordProvider(
    service_account_token="ops_xxxxx",
    vault_id="xxxxx",
    vault_name="xxxxx",
    op_connect_token="xxxxx",
    credentials={
        "verifier": {
            "salt": "xxxxx",
            "localHash": "xxxxx",
        },
        "encCredentials": {
            "kid": "xxxxx",
            "enc": "xxxxx",
            "cty": "xxxxx",
            "iv": "xxxxx",
            "data": "xxxxx",
        },
        "version": "2",
        "deviceUuid": "xxxxx",
        "uniqueKey": {
            "alg": "xxxxx",
            "ext": True,
            "k": "xxxxx",
            "key_ops": ["encrypt", "decrypt"],
            "kty": "oct",
            "kid": "xxxxx",
        },
    },
)

standard_provider = Provider(
        digitalocean=DigitalOceanProvider(
            token="dop_v1_xxxxx",
            spaces_access_id="xxxxx",
            spaces_secret_key="xxxxx",
            docker_reg_username="xxxxx@gmail.com",
        ),
        auth0=auth0_local,
        github=GithubProvider(
            token="xxxxx",
            owner="xxxxx",
        ),
        cloudflare=CloudflareProvider(
            token="xxxxx",
            email="xxxxx@gmail.com",
        ),
        onepassword=onepassword_common,
        datadog=DatadogProvider(
            api_key="xxxxx",
            app_key="xxxxx",
        ),
        elastic=ElasticCloudProvider(
            api_key="xxxxx"
        ),
        django_celery_app=DjangoCeleryAppProvider(
            flower_user="xxxxx",
            flower_password="xxxxx",
            django_superuser_username="xxxxx",
            django_superuser_email="xxxxx@gmail.com",
            django_superuser_password="xxxxx",
        ),
    )



def get_common_provider():
    common_provider = standard_provider.model_copy()
    common_provider.onepassword = onepassword_common
    return common_provider

def get_local_provider():
    local_provider = standard_provider.model_copy()
    local_provider.onepassword = onepassword_local
    return local_provider

def get_dev_provider():
    dev_provider = standard_provider.model_copy()
    dev_provider.onepassword = onepassword_dev
    dev_provider.auth0 = auth0_dev
    return dev_provider