from pathlib import Path
from typing import Set

from .domain_rules import (
    CI_FILENAMES,
    CI_FILENAMES_EXTRA,
    CI_PATH_MARKERS,
    CODE_EXTENSION_DESCRIPTIONS,
    CODE_EXTENSIONS,
    CONFIG_EXTENSION_DESCRIPTIONS,
    CONFIG_EXTENSIONS,
    DATA_EXTENSIONS,
    DATA_STORAGE_MARKERS,
    DOC_EXTENSION_DESCRIPTIONS,
    DOC_EXTENSIONS,
    DOCKER_FILENAMES,
    HELM_FILENAMES,
    INFRA_DOMAINS,
    K8S_FILENAMES,
    OBSERVABILITY_FILENAMES,
    OBSERVABILITY_PATH_MARKERS,
    SERVICE_MESH_MARKERS,
    TERRAFORM_EXTENSIONS,
)


def classify_type(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()
    if name in DOCKER_FILENAMES or name.startswith("Dockerfile"):
        return "infra"
    if name in CI_FILENAMES or name in CI_FILENAMES_EXTRA or any(marker in path.as_posix() for marker in CI_PATH_MARKERS):
        return "ci"
    if suffix in TERRAFORM_EXTENSIONS:
        return "infra"
    if suffix in CODE_EXTENSIONS:
        return "code"
    if suffix in DOC_EXTENSIONS:
        return "docs"
    if suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix in DATA_EXTENSIONS:
        return "data"
    return "other"


def detect_domains(path: Path, content_snippet: str) -> Set[str]:
    domains: Set[str] = set()
    posix_path = path.as_posix()
    name = path.name
    suffix = path.suffix.lower()
    content = content_snippet or ""

    if name in DOCKER_FILENAMES or name.startswith("Dockerfile"):
        domains.add("docker")

    if "docker" in posix_path and (suffix in {".yml", ".yaml"} or name.startswith("Dockerfile")):
        domains.add("docker")

    if name in CI_FILENAMES or name in CI_FILENAMES_EXTRA or any(marker in posix_path for marker in CI_PATH_MARKERS):
        domains.add("ci")

    if name in HELM_FILENAMES or "charts/" in posix_path or "/templates/" in posix_path:
        domains.add("helm")

    if suffix in TERRAFORM_EXTENSIONS or "terraform" in posix_path:
        domains.add("terraform")

    if "ansible" in posix_path or "/roles/" in posix_path or "/tasks/" in posix_path:
        domains.add("ansible")

    if name in K8S_FILENAMES or "k8s" in posix_path or "kubernetes" in posix_path:
        domains.add("kubernetes")

    if suffix in {".yml", ".yaml"}:
        if "apiVersion" in content and "kind" in content:
            domains.add("kubernetes")

    if name in OBSERVABILITY_FILENAMES or any(marker in posix_path for marker in OBSERVABILITY_PATH_MARKERS):
        domains.add("observability")

    if any(marker in posix_path for marker in SERVICE_MESH_MARKERS):
        domains.add("service_mesh")
        if "ingress" in posix_path:
            domains.add("kubernetes")

    if suffix in {".yml", ".yaml"}:
        if "kind: Ingress" in content or "kind: Gateway" in content:
            domains.add("service_mesh")
            domains.add("kubernetes")
        if "VirtualService" in content or "DestinationRule" in content or "ServiceEntry" in content:
            domains.add("service_mesh")

    if any(marker in posix_path for marker in DATA_STORAGE_MARKERS):
        domains.add("data_storage")

    return domains


def is_infra(domains: Set[str]) -> bool:
    return bool(domains.intersection(INFRA_DOMAINS))


__all__ = [
    "CODE_EXTENSION_DESCRIPTIONS",
    "CONFIG_EXTENSION_DESCRIPTIONS",
    "DOC_EXTENSION_DESCRIPTIONS",
    "classify_type",
    "detect_domains",
    "is_infra",
]
