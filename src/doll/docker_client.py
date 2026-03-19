import docker
from docker import DockerClient

from doll.config import config


def get_client() -> DockerClient:
    kwargs = {}
    if config.docker_host:
        kwargs["base_url"] = config.docker_host
    return docker.DockerClient(**kwargs)


def list_repositories() -> dict[str, list[str]]:
    """Parse all RepoTags from Docker into {repo: [tags]}.

    When DOLL_FILTER_REGISTRY is enabled, only images tagged with the
    configured registry prefix (DOLL_REGISTRY) are included, and the
    prefix is stripped from the repository name so that images appear
    as bare names (e.g. "myapp" instead of "registry.local:5000/myapp").
    """
    client = get_client()
    repos: dict[str, list[str]] = {}
    registry_prefix = config.registry + "/"
    for image in client.images.list():
        for repo_tag in (image.tags or []):
            # Skip digest references like "repo@sha256:..."
            if "@" in repo_tag:
                continue
            # repo_tag is e.g. "ubuntu:22.04" or "myregistry/app:latest"
            repo, _, tag = repo_tag.rpartition(":")
            if not repo:
                continue

            if config.filter_registry:
                if not repo.startswith(registry_prefix):
                    continue
                repo = repo[len(registry_prefix):]

            repos.setdefault(repo, []).append(tag)
    return repos


def get_tags(name: str) -> list[str] | None:
    """Return tags for a specific repo name, or None if not found."""
    repos = list_repositories()
    return repos.get(name)
