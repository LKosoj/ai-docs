from pathlib import Path
from typing import Set


CODE_EXTENSIONS = {
    ".py", ".pyi", ".pyx", ".js", ".jsx", ".ts", ".tsx", ".go", ".java",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".rs", ".rb", ".php", ".cs",
    ".kt", ".kts", ".swift", ".m", ".mm",
}

DOC_EXTENSIONS = {".md", ".rst", ".adoc", ".txt"}

CONFIG_EXTENSIONS = {
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".properties",
}

DATA_EXTENSIONS = {".csv", ".tsv", ".parquet", ".avro", ".jsonl"}


K8S_FILENAMES = {
    "deployment.yaml", "deployment.yml", "service.yaml", "service.yml",
    "ingress.yaml", "ingress.yml", "kustomization.yaml", "kustomization.yml",
}


CI_FILENAMES = {".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"}


HELM_FILENAMES = {"Chart.yaml", "Chart.yml", "values.yaml", "values.yml"}


DOCKER_FILENAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"}


TERRAFORM_EXTENSIONS = {".tf", ".tfvars"}


def classify_type(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()
    if name in DOCKER_FILENAMES or name.startswith("Dockerfile"):
        return "infra"
    if name in CI_FILENAMES or ".github/workflows" in path.as_posix():
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

    if name in CI_FILENAMES or ".github/workflows" in posix_path:
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

    return domains


def is_infra(domains: Set[str]) -> bool:
    return bool(domains.intersection({"kubernetes", "helm", "terraform", "ansible", "docker", "ci"}))

