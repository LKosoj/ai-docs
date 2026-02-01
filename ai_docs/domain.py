from pathlib import Path
from typing import Set


CODE_EXTENSION_DESCRIPTIONS = {
    ".py": "Python",
    ".pyi": "Python (типизация)",
    ".pyx": "Cython",
    ".js": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (TSX)",
    ".go": "Go",
    ".java": "Java",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".kt": "Kotlin",
    ".kts": "Kotlin (Script)",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".vb": "Visual Basic",
    ".bas": "BASIC",
    ".sql": "SQL",
    ".pas": "Pascal",
    ".dpr": "Delphi/Pascal",
    ".pp": "Pascal",
    ".r": "R",
    ".pl": "Perl",
    ".pm": "Perl Module",
    ".f": "Fortran",
    ".for": "Fortran",
    ".f90": "Fortran",
    ".f95": "Fortran",
    ".f03": "Fortran",
    ".f08": "Fortran",
    ".sb3": "Scratch",
    ".adb": "Ada",
    ".ads": "Ada (Spec)",
    ".asm": "Assembly",
    ".s": "Assembly",
    ".ino": "Arduino",
    ".htm": "HTML",
    ".html": "HTML",
    ".css": "CSS",
}

DOC_EXTENSION_DESCRIPTIONS = {
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".adoc": "AsciiDoc",
    ".txt": "Text",
}

CONFIG_EXTENSION_DESCRIPTIONS = {
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".conf": "Config",
    ".env": "Environment",
    ".properties": "Properties",
}

CODE_EXTENSIONS = set(CODE_EXTENSION_DESCRIPTIONS)
DOC_EXTENSIONS = set(DOC_EXTENSION_DESCRIPTIONS)
CONFIG_EXTENSIONS = set(CONFIG_EXTENSION_DESCRIPTIONS)

DATA_EXTENSIONS = {".csv", ".tsv", ".parquet", ".avro", ".jsonl"}


K8S_FILENAMES = {
    "deployment.yaml", "deployment.yml", "service.yaml", "service.yml",
    "ingress.yaml", "ingress.yml", "kustomization.yaml", "kustomization.yml",
}

CI_FILENAMES = {".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"}
CI_PATH_MARKERS = {".github/workflows", ".circleci", ".buildkite"}
CI_FILENAMES_EXTRA = {"bitbucket-pipelines.yml", "buildkite.yml", "pipeline.yml"}


HELM_FILENAMES = {"Chart.yaml", "Chart.yml", "values.yaml", "values.yml"}


DOCKER_FILENAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"}

OBSERVABILITY_FILENAMES = {
    "prometheus.yml", "prometheus.yaml", "alertmanager.yml", "alertmanager.yaml",
    "loki.yml", "loki.yaml", "promtail.yml", "promtail.yaml", "tempo.yml", "tempo.yaml",
    "otel-collector.yml", "otel-collector.yaml", "opentelemetry-collector.yml", "opentelemetry-collector.yaml",
    "jaeger.yml", "jaeger.yaml", "zipkin.yml", "zipkin.yaml",
}
OBSERVABILITY_PATH_MARKERS = {
    "prometheus", "grafana", "loki", "tempo", "otel", "opentelemetry",
    "jaeger", "zipkin", "logstash", "fluentd", "fluent-bit",
}
SERVICE_MESH_MARKERS = {
    "istio", "linkerd", "consul", "cilium", "envoy", "traefik", "nginx-ingress",
    "service-mesh", "servicemesh", "ingress", "gateway",
}
DATA_STORAGE_MARKERS = {
    "postgres", "mysql", "mariadb", "redis", "mongo", "mongodb", "cassandra",
    "clickhouse", "elasticsearch", "opensearch", "kafka", "minio", "s3",
}

TERRAFORM_EXTENSIONS = {".tf", ".tfvars"}


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
    return bool(
        domains.intersection(
            {
                "kubernetes",
                "helm",
                "terraform",
                "ansible",
                "docker",
                "ci",
                "observability",
                "service_mesh",
                "data_storage",
            }
        )
    )
