import pulumi
from schema import (
    EnvType,
    FullStackDeployment,
)
import pulumi_digitalocean as digitalocean
import pulumi_kubernetes as k8s
import pulumi_random as random
import pulumiverse_time as time


class DigitalOceanSetup:
    def __init__(self, env_type: EnvType, config: FullStackDeployment) -> None:
        if env_type not in [EnvType.dev, EnvType.staging, EnvType.prod]:
            raise ValueError("Invalid environment type")

        self.env_type = env_type
        self.config = config
        self.resource_prefix = f"{env_type.value}-{config.project_name}-"

        self.instance_config = list(
            filter(lambda x: x.env_type == env_type, config.instances)
        )[0].instances

        provider = list(
            filter(lambda x: x.env_type == self.env_type, config.providers)
        )[0].provider
        self.digitalocean_provider = provider.digitalocean

    def setup_vpc(self) -> None:
        do_vpc = digitalocean.Vpc(
            resource_name=self.resource_prefix + "digitalocean-vpc",
            region=self.instance_config.default_region,
            name=self.resource_prefix + "digitalocean-vpc",
        )
        self.do_vpc = do_vpc

    def setup_bucket(self) -> dict:
        do_space = digitalocean.SpacesBucket(
            resource_name=self.resource_prefix + "digitalocean-space",
            name=self.resource_prefix + "bucket",
            region=self.instance_config.default_region,
            force_destroy=True,
            cors_rules=[
                {
                    "allowed_headers": ["*"],
                    "allowed_methods": ["GET", "PUT", "POST"],
                    "allowed_origins": ["*"],
                    "max_age_seconds": 3600,
                }
            ],
        )

        self.bucket = do_space
        bucket_details = {
            "name": do_space.name,
            "region": do_space.region,
            "endpoint": do_space.endpoint,
            "access_key": self.digitalocean_provider.spaces_access_id,
            "secret_key": self.digitalocean_provider.spaces_secret_key,
            "origin": do_space.bucket_domain_name,
        }
        pulumi.export("bucket", bucket_details)
        return bucket_details

    def setup_cdn(self) -> dict:
        cdn_space = digitalocean.SpacesBucket(
            resource_name=self.resource_prefix + "digitalocean-cdn-space",
            name=self.resource_prefix + "cdn-bucket",
            region=self.instance_config.default_region,
            acl="public-read",
            force_destroy=True,
            cors_rules=[
                {
                    "allowed_headers": ["*"],
                    "allowed_methods": ["GET", "PUT", "POST"],
                    "allowed_origins": ["*"],
                    "max_age_seconds": 3600,
                }
            ],
        )

        self.cdn_bucket = cdn_space

        cdn = digitalocean.Cdn(
            resource_name=self.resource_prefix + "digitalocean-cdn",
            origin=cdn_space.bucket_domain_name,
        )

        cdn_details = {
            "endpoint": cdn.endpoint,
            "origin": cdn.origin,
            "bucket": {
                "name": cdn_space.name,
                "region": cdn_space.region,
                "endpoint": cdn_space.endpoint,
                "access_key": self.digitalocean_provider.spaces_access_id,
                "secret_key": self.digitalocean_provider.spaces_secret_key,
            },
        }

        pulumi.export("cdn", cdn_details)
        return cdn_details

    def setup_redis(self) -> dict:
        redis_db_cluster = digitalocean.DatabaseCluster(
            resource_name=self.resource_prefix + "digitalocean-redis",
            engine="redis",
            version="7",
            size=self.instance_config.caching_size,
            node_count=self.instance_config.caching_node_count,
            region=self.instance_config.default_region,
            private_network_uuid=self.do_vpc.id,
            tags=[self.env_type],
            maintenance_windows=[
                {
                    "day": self.instance_config.maintenance_window_day,
                    "hour": self.instance_config.maintenance_window_time,
                }
            ],
        )

        self.redis_db_cluster = redis_db_cluster

        redis_url = pulumi.Output.all(
            redis_db_cluster.password,
            redis_db_cluster.private_host,
            redis_db_cluster.port,
        ).apply(
            lambda args: f"rediss://default:{args[0]}@{args[1]}:{args[2]}?ssl_cert_reqs=CERT_REQUIRED"
        )

        redis_details = {
            "host": redis_db_cluster.private_host,
            "port": redis_db_cluster.port,
            "password": redis_db_cluster.password,
            "username": redis_db_cluster.user,
            "version": redis_db_cluster.version,
            "url": redis_url,
        }

        pulumi.export("redis", redis_details)
        return redis_details

    def setup_postgres(self) -> dict:
        postgres_db_cluster = digitalocean.DatabaseCluster(
            resource_name=self.resource_prefix + "digitalocean-postgres",
            engine="pg",
            version="16",
            node_count=self.instance_config.db_cluster_node_count,
            size=self.instance_config.db_size,
            region=self.instance_config.default_region,
            private_network_uuid=self.do_vpc.id,
            tags=[self.env_type],
            maintenance_windows=[
                {
                    "day": self.instance_config.maintenance_window_day,
                    "hour": self.instance_config.maintenance_window_time,
                }
            ],
        )

        self.postgres_db_cluster = postgres_db_cluster

        pg_db = digitalocean.DatabaseDb(
            resource_name=self.resource_prefix + "digitalocean-db",
            cluster_id=postgres_db_cluster.id,
            name="main",
        )

        pg_db_connection_pool = digitalocean.DatabaseConnectionPool(
            resource_name=self.resource_prefix + "digitalocean-db-connection-pool",
            name=self.resource_prefix + "db-connection-pool",
            db_name=pg_db.name,
            cluster_id=postgres_db_cluster.id,
            mode="transaction",
            size=self.instance_config.pg_pool_size,
            user=postgres_db_cluster.user,
        )

        pg_details = {
            "db": {
                "host": postgres_db_cluster.host,
                "username": postgres_db_cluster.user,
                "password": postgres_db_cluster.password,
                "port": postgres_db_cluster.port,
                "database": pg_db.name,
                "version": postgres_db_cluster.version,
            },
            "connection_pool": {
                "host": pg_db_connection_pool.host,
                "username": pg_db_connection_pool.user,
                "password": pg_db_connection_pool.password,
                "port": pg_db_connection_pool.port,
                "database": pg_db_connection_pool.name,
                "version": postgres_db_cluster.version,
            },
        }

        pulumi.export("postgres", pg_details)
        return pg_details

    def setup_docker_registry(self) -> dict:
        self.docker_registry = digitalocean.ContainerRegistry(
            resource_name=self.resource_prefix + "digitalocean-docker-registry",
            subscription_tier_slug="professional",
            name=self.resource_prefix + "digitalocean-docker-registry",
        )

        docker_registry_k8_user = digitalocean.ContainerRegistryDockerCredentials(
            resource_name=self.resource_prefix
            + "digitalocean-docker-registry-credentials-k8-user",
            registry_name=self.docker_registry.name,
            write=False,
        )

        docker_registry_github_user = digitalocean.ContainerRegistryDockerCredentials(
            resource_name=self.resource_prefix
            + "digitalocean-docker-registry-credentials-github-user",
            registry_name=self.docker_registry.name,
            write=True,
        )

        registry_details = {
            "name": self.docker_registry.name,
            "region": self.docker_registry.region,
            "endpoint": self.docker_registry.endpoint,
            "server_url": self.docker_registry.server_url,
            "k8_user": {
                "docker_credentials": docker_registry_k8_user.docker_credentials,
            },
            "github_user": {
                "docker_credentials": docker_registry_github_user.docker_credentials,
            },
        }

        pulumi.export("docker_registry", registry_details)
        return registry_details

    def setup_k8_cluster(self) -> dict:
        k8_version = digitalocean.get_kubernetes_versions()

        k8_cluster = digitalocean.KubernetesCluster(
            resource_name=self.resource_prefix + "digitalocean-k8-cluster",
            region=self.instance_config.default_region,
            name=self.resource_prefix + "k8-cluster",
            vpc_uuid=self.do_vpc.id,
            version=k8_version.latest_version,
            auto_upgrade=True,
            destroy_all_associated_resources=True,
            registry_integration=True,
            tags=[self.env_type],
            ha=True if self.env_type == EnvType.prod else False,
            maintenance_policy={
                "day": self.instance_config.maintenance_window_day,
                "start_time": self.instance_config.maintenance_window_time,
            },
            node_pool={
                "name": self.resource_prefix + "node-pool",
                "size": self.instance_config.k8_node_pool_size,
                "auto_scale": True,
                "min_nodes": self.instance_config.k8_min_node_count,
                "max_nodes": self.instance_config.k8_max_node_count,
            },
            opts=pulumi.ResourceOptions(
                depends_on=[self.docker_registry],
            ),
        )

        self.k8_cluster = k8_cluster

        k8_cluster_details = {
            "name": k8_cluster.name,
            "region": k8_cluster.region,
            "endpoint": k8_cluster.endpoint,
            "kubeconfig": k8_cluster.kube_configs[0].raw_config,
        }

        pulumi.export("k8_cluster", k8_cluster_details)
        return k8_cluster_details

    def setup_firewalls(self) -> None:
        digitalocean.DatabaseFirewall(
            resource_name=self.resource_prefix + "digitalocean-postgres-firewall",
            cluster_id=self.postgres_db_cluster.id,
            rules=[{"type": "k8s", "value": self.k8_cluster.id}],
        )

        digitalocean.DatabaseFirewall(
            resource_name=self.resource_prefix + "digitalocean-redis-firewall",
            cluster_id=self.redis_db_cluster.id,
            rules=[{"type": "k8s", "value": self.k8_cluster.id}],
        )

    def setup_do_project(self) -> None:
        mapped_env = {
            EnvType.dev: "Development",
            EnvType.staging: "Staging",
            EnvType.prod: "Production",
        }

        digitalocean.Project(
            resource_name=self.resource_prefix + "digitalocean-project",
            name=self.resource_prefix + "project",
            purpose=self.env_type.value,
            environment=mapped_env[self.env_type],
            description=f"{self.env_type.value} environment for {self.config.project_name}",
            resources=[
                self.postgres_db_cluster.cluster_urn,
                self.redis_db_cluster.cluster_urn,
                self.k8_cluster.cluster_urn,
                self.bucket.bucket_urn,
                self.cdn_bucket.bucket_urn,
            ],
        )

    def setup_django_secret_key(self) -> str:
        secret_key = random.RandomUuid(
            resource_name=self.resource_prefix + "django-secret-key",
        )

        pulumi.export("django_secret_key", secret_key.result)
        return secret_key.result

    def setup(self) -> tuple[dict, k8s.Provider]:
        self.setup_vpc()
        bucket = self.setup_bucket()
        cdn = self.setup_cdn()
        db = self.setup_postgres()
        redis = self.setup_redis()
        docker = self.setup_docker_registry()
        k8 = self.setup_k8_cluster()
        self.setup_firewalls()
        self.setup_do_project()

        k8_node_pool_propagation = time.Sleep(
            self.resource_prefix + "k8_node_pool",
            create_duration="300s",
            destroy_duration="300s",
            triggers={
                "kubeconfig": k8.get("kubeconfig"),
            },
        )

        return {
            "bucket": bucket,
            "cdn": cdn,
            "postgres": db,
            "redis": redis,
            "docker": docker,
            "k8": k8,
            "django_secret_key": self.setup_django_secret_key(),
            "digitalocean_token": self.digitalocean_provider.token,
        }, k8s.Provider(
            f"{self.env_type.value}-k8s",
            kubeconfig=k8_node_pool_propagation.triggers["kubeconfig"],
            delete_unreachable=True
        )
