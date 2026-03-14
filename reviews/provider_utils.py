# reviews/provider_utils.py
from reposcanner.github_service import (
    fetch_pr_diff as github_fetch_diff,
    fetch_pr_files as github_fetch_files,
    fetch_single_pr as github_fetch_single,
)
from pullrequests.gitlab_service import (
    fetch_mr_diff as gitlab_fetch_diff,
    fetch_mr_files as gitlab_fetch_files,
    fetch_single_mr as gitlab_fetch_single,
)


def fetch_diff(repository, pull_request):
    """Fetch unified diff for a pull/merge request."""
    if repository.provider == 'github':
        return github_fetch_diff(repository, pull_request.number)
    elif repository.provider == 'gitlab':
        return gitlab_fetch_diff(repository, pull_request.number)
    else:
        return None, f'Unsupported provider: {repository.provider}'


def fetch_files(repository, pull_request):
    """Fetch file list for a pull/merge request."""
    if repository.provider == 'github':
        return github_fetch_files(repository, pull_request.number)
    elif repository.provider == 'gitlab':
        return gitlab_fetch_files(repository, pull_request.number)
    else:
        return None, f'Unsupported provider: {repository.provider}'


def fetch_pull_request(repository, number):
    """Fetch a single pull/merge request from the provider."""
    if repository.provider == 'github':
        return github_fetch_single(repository, number)
    elif repository.provider == 'gitlab':
        return gitlab_fetch_single(repository, number)
    else:
        return None, f'Unsupported provider: {repository.provider}'