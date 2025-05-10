from pulumi import Output, ResourceOptions
from schema import EnvType, FullStackDeployment
import pulumi_onepassword as onepassword
from collections.abc import MutableMapping


class VaultSetup:
    def __init__(
        self, env_type: EnvType, config: FullStackDeployment, secret_values: dict
    ) -> None:
        self.env_type = env_type
        self.config = config
        self.resource_prefix = f"{env_type.value}-{config.project_name}-"
        self.secret_values: dict[str, Output[str]] = secret_values
        provider = list(
            filter(lambda x: x.env_type == self.env_type, config.providers)
        )[0].provider
        self.onepassword_provider = provider.onepassword

    def flatten(self, dictionary, parent_key="", separator="_"):
        items = []
        for key, value in dictionary.items():
            new_key = parent_key + separator + key if parent_key else key
            if isinstance(value, MutableMapping):
                items.extend(self.flatten(value, new_key, separator=separator).items())
            else:
                items.append((new_key, value))
        return dict(items)

    def setup(self):
        section_names = self.secret_values.keys()
        op_sections: list[dict] = []
        for section_name in section_names:
            section_values = self.flatten(self.secret_values[section_name])
            section_items = [
                {"label": key, "value": value, "type": "CONCEALED"}
                for key, value in section_values.items()
            ]

            op_sections.append(
                {
                    "label": section_name,
                    "fields": section_items,
                }
            )

        onepassword.Item(
            resource_name=f"{self.resource_prefix}-secret",
            vault=self.onepassword_provider.vault_id,
            tags=[self.env_type.value],
            title=self.config.project_name,
            sections=op_sections,
            opts=ResourceOptions(replace_on_changes=["sections"]),
        )
