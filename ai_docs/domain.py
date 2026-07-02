from pathlib import Path
from typing import Iterable, Set, Tuple

from .domain_rules import (
    CI_FILENAMES,
    CI_FILENAMES_EXTRA,
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


def _path_segments(path: Path) -> Tuple[str, ...]:
    return tuple(part.lower() for part in path.parts if part and part != path.anchor)


def _has_segment(parts: Tuple[str, ...], markers: Iterable[str]) -> bool:
    marker_set = {marker.lower() for marker in markers}
    return any(part in marker_set for part in parts)


def _has_sequence(parts: Tuple[str, ...], sequence: Tuple[str, ...]) -> bool:
    if len(parts) < len(sequence):
        return False
    normalized = tuple(part.lower() for part in sequence)
    return any(
        parts[index : index + len(normalized)] == normalized
        for index in range(len(parts) - len(normalized) + 1)
    )


def _has_ci_path(parts: Tuple[str, ...]) -> bool:
    return (
        _has_sequence(parts, (".github", "workflows"))
        or ".circleci" in parts
        or ".buildkite" in parts
    )


def classify_type(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()
    parts = _path_segments(path)
    if name in DOCKER_FILENAMES or name.startswith("Dockerfile"):
        return "infra"
    if name in CI_FILENAMES or name in CI_FILENAMES_EXTRA or _has_ci_path(parts):
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
    parts = _path_segments(path)
    name = path.name
    suffix = path.suffix.lower()
    content = content_snippet or ""
    is_code = suffix in CODE_EXTENSIONS
    is_yaml = suffix in {".yml", ".yaml"}

    if name in DOCKER_FILENAMES or name.startswith("Dockerfile"):
        domains.add("docker")

    if "docker" in parts and (is_yaml or name.startswith("Dockerfile")):
        domains.add("docker")

    if name in CI_FILENAMES or name in CI_FILENAMES_EXTRA or _has_ci_path(parts):
        domains.add("ci")

    if name in HELM_FILENAMES or "charts" in parts or (is_yaml and "templates" in parts):
        domains.add("helm")

    if suffix in TERRAFORM_EXTENSIONS or "terraform" in parts:
        domains.add("terraform")

    if not is_code and ("ansible" in parts or "roles" in parts):
        domains.add("ansible")

    if name in K8S_FILENAMES or "k8s" in parts or "kubernetes" in parts:
        domains.add("kubernetes")

    if is_yaml:
        if "apiVersion" in content and "kind" in content:
            domains.add("kubernetes")

    if name in OBSERVABILITY_FILENAMES or (not is_code and _has_segment(parts, OBSERVABILITY_PATH_MARKERS)):
        domains.add("observability")

    if not is_code and _has_segment(parts, SERVICE_MESH_MARKERS):
        domains.add("service_mesh")
        if "ingress" in parts or "nginx-ingress" in parts:
            domains.add("kubernetes")

    if is_yaml:
        if "kind: Ingress" in content or "kind: Gateway" in content:
            domains.add("service_mesh")
            domains.add("kubernetes")
        if "VirtualService" in content or "DestinationRule" in content or "ServiceEntry" in content:
            domains.add("service_mesh")

    if not is_code and _has_segment(parts, DATA_STORAGE_MARKERS):
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
