import json
import jinja2
import yaml
import pulumi_kubernetes as k8
import pulumi
from schema import EnvType, FullStackDeployment
from pulumi_kubernetes.helm.v4 import Chart
import pulumi_random as random
from pulumi_kubernetes.core.v1 import Secret, Namespace
from pulumi_kubernetes.yaml.v2 import ConfigGroup
from pulumi import Output


def create_template(path: str) -> jinja2.Template:
    with open(path, "r") as f:
        template = jinja2.Template(f.read())
    return template


datadog_yaml_template_path = "templates/datadog.yaml"


class KubernetesSetup:
    def __init__(
        self,
        env_type: EnvType,
        config: FullStackDeployment,
        k8_provider: k8.Provider,
        secrets: dict,
    ) -> None:
        if env_type not in [EnvType.dev, EnvType.staging, EnvType.prod]:
            raise ValueError("Invalid environment type")

        self.env_type = env_type
        self.config = config
        self.resource_prefix = f"{env_type.value}-{config.project_name}-"
        self.k8_provider = k8_provider

        provider = list(
            filter(lambda x: x.env_type == self.env_type, config.providers)
        )[0].provider
        self.cloudflare_provider = provider.cloudflare
        self.datadog_provider = provider.datadog
        self.onepassword = provider.onepassword
        self.django = provider.django_celery_app
        self.secrets = secrets

    def _setup_k8_dashboard(self):
        """
        kubectl -n kubernetes-dashboard port-forward svc/kubernetes-dashboard-kong-proxy 8443:443
        kubectl get secret admin-user -n kubernetes-dashboard -o jsonpath={".data.token"} | base64 -d
        https://localhost:8443/
        """

        k8_dash_namespace = Namespace(
            "kubernetes-dashboard",
            metadata={"name": "kubernetes-dashboard"},
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        k8_dash = Chart(
            "kubernetes-dashboard",
            namespace="kubernetes-dashboard",
            chart="kubernetes-dashboard",
            repository_opts={
                "repo": "https://kubernetes.github.io/dashboard/",
            },
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider, depends_on=[k8_dash_namespace]
            ),
        )

        sa_admin = ConfigGroup(
            "service_account_admin_user",
            objs=[
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {
                        "name": "admin-user",
                        "namespace": "kubernetes-dashboard",
                    },
                }
            ],
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider, depends_on=[k8_dash]
            ),
        )

        ConfigGroup(
            "role_binding_admin_user",
            objs=[
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "ClusterRoleBinding",
                    "metadata": {
                        "name": "admin-user",
                    },
                    "roleRef": {
                        "apiGroup": "rbac.authorization.k8s.io",
                        "kind": "ClusterRole",
                        "name": "cluster-admin",
                    },
                    "subjects": [
                        {
                            "kind": "ServiceAccount",
                            "name": "admin-user",
                            "namespace": "kubernetes-dashboard",
                        }
                    ],
                },
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "metadata": {
                        "name": "admin-user",
                        "namespace": "kubernetes-dashboard",
                        "annotations": {
                            "kubernetes.io/service-account.name": "admin-user"
                        },
                    },
                    "type": "kubernetes.io/service-account-token",
                },
            ],
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider, depends_on=[k8_dash, sa_admin]
            ),
        )

    def setup(self):
        self._setup_k8_dashboard()
        Chart(
            "kedacore",
            namespace="default",
            chart="keda",
            repository_opts={
                "repo": "https://kedacore.github.io/charts",
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        Chart(
            "metrics-server",
            namespace="default",
            chart="metrics-server",
            repository_opts={
                "repo": "https://kubernetes-sigs.github.io/metrics-server",
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        Chart(
            "kube-state-metrics",
            namespace="default",
            chart="kube-state-metrics",
            repository_opts={
                "repo": "https://prometheus-community.github.io/helm-charts",
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        cert_manager = Chart(
            "cert-manager",
            namespace="default",
            chart="cert-manager",
            repository_opts={
                "repo": "https://charts.jetstack.io",
            },
            values={"installCRDs": True},
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        Chart(
            "external-dns",
            namespace="default",
            chart="oci://registry-1.docker.io/bitnamicharts/external-dns",
            values={
                "provider": "cloudflare",
                "cloudflare": {
                    "apiToken": self.cloudflare_provider.token,
                    "proxied": True,
                },
                "domainFilters": [self.config.main_domain],
                "txtOwnerId": "external-dns",
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        rabbitmq_password = random.RandomPassword(
            "rabbitmq-password", length=16, special=True, override_special="!@#$%^&*()"
        ).result

        Chart(
            "rabbitmq",
            namespace="default",
            chart="oci://registry-1.docker.io/bitnamicharts/rabbitmq",
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
            values={
                "auth": {"username": "main_user", "password": rabbitmq_password},
                "extraConfiguration": """
                    default_vhost = myvhost
                    default_permissions.configure = .*
                    default_permissions.read = .*
                    default_permissions.write = .*
                """,
                "metrics": {"enabled": True},
            },
        )

        Chart(
            "onepassword",
            namespace="default",
            chart="connect",
            repository_opts={
                "repo": "https://1password.github.io/connect-helm-charts",
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
            values={
                "connect": {
                    "credentials": json.dumps(
                        self.onepassword.credentials, default=str
                    ),
                },
                "operator": {
                    "create": True,
                    "token": {
                        "value": self.onepassword.op_connect_token,
                    },
                },
            },
        )

        # https://www.haproxy.com/blog/autoscaling-with-the-haproxy-kubernetes-ingress-controller-and-keda
        Chart(
            "kubernetes-ingress-haproxy",
            namespace="default",
            chart="kubernetes-ingress",
            repository_opts={"repo": "https://haproxytech.github.io/helm-charts"},
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
            values={
                "controller": {
                    "podAnnotations": {
                        "prometheus.io/scrape": "true",
                        "prometheus.io/port": "1024",
                        "prometheus.io/path": "/metrics",
                    },
                    "service": {
                        "type": "LoadBalancer",
                    },
                }
            },
        )

        Chart(
            "prometheus",
            namespace="default",
            chart="prometheus",
            repository_opts={
                "repo": "https://prometheus-community.github.io/helm-charts"
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        cf_secret = Secret(
            "cloudflare-api-token-secret",
            type="Opaque",
            metadata={"name": "cloudflare-api-token-secret"},
            string_data={
                "api-token": self.cloudflare_provider.token,
            },
            opts=pulumi.ResourceOptions(provider=self.k8_provider, depends_on=[]),
        )

        cf_issuer = ConfigGroup(
            "cloudflare-cluster-issuer",
            objs=[
                {
                    "apiVersion": "cert-manager.io/v1",
                    "kind": "ClusterIssuer",
                    "metadata": {
                        "name": "cloudflare-cluster-issuer",
                    },
                    "spec": {
                        "acme": {
                            "server": "https://acme-staging-v02.api.letsencrypt.org/directory",
                            "email": self.cloudflare_provider.email,
                            "privateKeySecretRef": {
                                "name": "cloudflare-cluster-issuer",
                            },
                            "solvers": [
                                {
                                    "http01": {
                                        "ingress": {
                                            "ingressClassName": "haproxy",
                                        },
                                    }
                                }
                            ],
                        }
                    },
                }
            ],
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider, depends_on=[cert_manager, cf_secret]
            ),
        )

        ConfigGroup(
            "cloudflare-cluster-certificate",
            objs=[
                {
                    "apiVersion": "cert-manager.io/v1",
                    "kind": "Certificate",
                    "metadata": {
                        "name": "cloudflare-cluster-certificate",
                        "namespace": "default",
                    },
                    "spec": {
                        "secretName": "domain-tls",
                        "issuerRef": {
                            "name": "cloudflare-cluster-issuer",
                        },
                        "duration": "2160h0m0s",
                        "renewBefore": "720h0m0s",
                        "dnsNames": [
                            self.config.main_domain,
                            f"*.{self.config.main_domain}",
                        ],
                    },
                }
            ],
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider,
                depends_on=[cert_manager, cf_secret, cf_issuer],
            ),
        )

        redis_host = self.secrets.get("digitalocean").get("redis").get("host")
        redis_port = self.secrets.get("digitalocean").get("redis").get("port")
        redis_password = self.secrets.get("digitalocean").get("redis").get("password")
        redis_username = self.secrets.get("digitalocean").get("redis").get("username")
        redis_url = self.secrets.get("digitalocean").get("redis").get("url")

        postgres_host = (
            self.secrets.get("digitalocean").get("postgres").get("db").get("host")
        )
        postgres_port = (
            self.secrets.get("digitalocean").get("postgres").get("db").get("port")
        )
        postgres_password = (
            self.secrets.get("digitalocean").get("postgres").get("db").get("password")
        )
        postgres_username = (
            self.secrets.get("digitalocean").get("postgres").get("db").get("username")
        )
        postgres_dbname = (
            self.secrets.get("digitalocean").get("postgres").get("db").get("database")
        )

        elasticsearch_host = self.secrets.get("elastic").get("url")
        elasticsearch_username = self.secrets.get("elastic").get("username")
        elasticsearch_password = self.secrets.get("elastic").get("password")

        datadog_yaml = pulumi.Output.all(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_password=redis_password,
            redis_url=redis_url,
            redis_user=redis_username,
            postgres_host=postgres_host,
            postgres_port=postgres_port,
            postgres_password=postgres_password,
            postgres_username=postgres_username,
            postgres_dbname=postgres_dbname,
            elasticsearch_host=elasticsearch_host,
            elasticsearch_username=elasticsearch_username,
            elasticsearch_password=elasticsearch_password,
        ).apply(
            lambda args: yaml.safe_load(
                create_template(datadog_yaml_template_path)
                .render(
                    api_key=self.datadog_provider.api_key,
                    redis_host=args["redis_host"],
                    redis_port=args["redis_port"],
                    redis_password=args["redis_password"],
                    redis_user=args["redis_user"],
                    redis_url=args["redis_url"],
                    postgres_host=args["postgres_host"],
                    postgres_port=args["postgres_port"],
                    postgres_password=args["postgres_password"],
                    postgres_username=args["postgres_username"],
                    postgres_dbname=args["postgres_dbname"],
                    elasticsearch_host=args["elasticsearch_host"],
                    elasticsearch_username=args["elasticsearch_username"],
                    elasticsearch_password=args["elasticsearch_password"],
                    rabbitmq_host="rabbitmq",
                )
                .encode("utf-8")
            )
        )

        Chart(
            resource_name="datadog-agent",
            namespace="default",
            chart="datadog",
            repository_opts={
                "repo": "https://helm.datadoghq.com",
            },
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider, depends_on=[], ignore_changes=[]
            ),
            values=datadog_yaml,
        )

        formatted_rabbitmq_url = Output.all(rabbitmq_password).apply(
            lambda args: f"amqp://main_user:{args[0]}@rabbitmq:5672/myvhost"
        )

        Secret(
            "django-rest-api",
            type="Opaque",
            metadata={"name": "django-rest-api"},
            string_data={
                "celery_broker_url": formatted_rabbitmq_url,
                "django_superuser_username": self.django.django_superuser_username,
                "django_superuser_password": self.django.django_superuser_password,
                "django_superuser_email": self.django.django_superuser_email,
                "flower_user": self.django.flower_user,
                "flower_password": self.django.flower_password,
                "vault_name": self.onepassword.vault_name,
                "vault_id": self.onepassword.vault_id,
                "vault_service_account_token": self.onepassword.service_account_token,
            },
            opts=pulumi.ResourceOptions(
                provider=self.k8_provider,
            ),
        )

        return {
            "rabbitmq": {
                "password": rabbitmq_password,
                "username": "main_user",
                "host": "rabbitmq",
                "port": 5672,
                "vhost": "myvhost",
                "url": formatted_rabbitmq_url,
            }
        }
