import docker
from docker import DockerClient

from doll.config import config


def get_client() -> DockerClient:
    kwargs = {}
    if config.docker_host:
        kwargs["base_url"] = config.docker_host
    return docker.DockerClient(**kwargs)


def list_repositories() -> dict[str, list[str]]:
    """Parse all RepoTags from Docker into {repo: [tags]}."""
    client = get_client()
    repos: dict[str, list[str]] = {}
    for image in client.images.list():
        for repo_tag in (image.tags or []):
            # Skip digest references like "repo@sha256:..."
            if "@" in repo_tag:
                continue
            # repo_tag is e.g. "ubuntu:22.04" or "myregistry/app:latest"
            repo, _, tag = repo_tag.rpartition(":")
            if not repo:
                continue
            repos.setdefault(repo, []).append(tag)
    return repos


def get_tags(name: str) -> list[str] | None:
    """Return tags for a specific repo name, or None if not found."""
    repos = list_repositories()
    return repos.get(name)
