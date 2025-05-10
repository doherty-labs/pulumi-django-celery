import pulumi_ec as ec
import pulumi
from schema import EnvType, FullStackDeployment


class ElasticCloudSetup:
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
        self.elastic_provider = provider.elastic

    def _setup_elastic_cloud(self):
        latest_version = ec.get_stack(
            version_regex="latest", region="gcp-europe-west2", lock=False
        ).version

        db = ec.Deployment(
            resource_name=f"{self.resource_prefix}elastic-deployment",
            name=f"{self.resource_prefix}elastic-deployment",
            region="gcp-europe-west2",
            version=latest_version,
            deployment_template_id=self.instance_config.es_instance_size,
            elasticsearch={
                "hot": {
                    "size": "1g",
                    "zone_count": 1,
                    "autoscaling": {
                        "autoscale": False,
                    },
                },
                "autoscale": False,
            },
        )

        es_details = {
            "url": db.elasticsearch.https_endpoint,
            "username": db.elasticsearch_username,
            "password": db.elasticsearch_password,
        }

        pulumi.export("es_details", es_details)

        return es_details

    def setup(self) -> dict:
        # Create Elastic Cloud resources
        return self._setup_elastic_cloud()
