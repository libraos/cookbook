import re

import pytest
import yaml

from conftest import ROOT


def test_compose_runtime_default_matches_quickstart_docs():
    quickstart = ROOT / "get-started"
    compose = yaml.safe_load((quickstart / "docker-compose.yml").read_text())
    image = compose["services"]["libraos"]["image"]
    default = re.fullmatch(r"(ghcr\.io/libraos/libraos):\$\{LIBRAOS_VERSION:-(v\d+\.\d+\.\d+)\}", image)
    assert default, "Compose must default to a stable Runtime tag and allow an override"
    repository, version = default.groups()
    assert f"defaults to kernel **{version}**" in (ROOT / "README.md").read_text()
    assert f"`{repository}:{version}`" in (quickstart / "README.md").read_text()
    assert not re.search(r"^\s*LIBRAOS_VERSION=", (quickstart / ".env.example").read_text(), re.M)


@pytest.mark.parametrize("recipe", [
    "content-moderation", "customer-support", "document-qa", "finance",
    "healthcare", "legaltech", "ticket-routing",
])
def test_legacy_recipe_entry_points_still_link_to_canonical_recipe(recipe):
    pointer = (ROOT / recipe / "README.md").read_text()
    assert f"(../recipes/{recipe}/)" in pointer
    assert (ROOT / "recipes" / recipe / "README.md").is_file()
