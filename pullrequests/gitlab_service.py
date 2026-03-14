import requests
from django.utils.dateparse import parse_datetime

def get_headers(access_token):
    return {'Authorization': f'Bearer {access_token}'}

def encode_project_path(full_name):
    """URL‑encode the repository path for GitLab API."""
    import urllib.parse
    return urllib.parse.quote(full_name, safe='')

def fetch_mrs_from_gitlab(repository, status_filter='all'):
    """
    Fetch merge requests from GitLab and return them in a normalized list.
    status_filter: 'all', 'opened', 'closed', 'merged'
    """
    all_mrs = []
    page = 1
    per_page = 100
    encoded_path = encode_project_path(repository.full_name)
    state_map = {
        'all': None,
        'open': 'opened',
        'closed': 'closed',
        'merged': 'merged'
    }
    gitlab_state = state_map.get(status_filter)

    while True:
        url = f'https://gitlab.com/api/v4/projects/{encoded_path}/merge_requests'
        headers = get_headers(repository.access_token)
        params = {
            'per_page': per_page,
            'page': page,
            'state': gitlab_state,
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return None, f'GitLab API error: {response.status_code}'

        mrs = response.json()
        if not mrs:
            break

        all_mrs.extend(mrs)
        page += 1

    return all_mrs, None


def normalize_mr(mr_data):
    """
    Convert a GitLab merge request dict to a structure compatible with
    our PullRequest model (mirroring GitHub's fields).
    """
    # Determine status
    if mr_data.get('state') == 'merged':
        status = 'merged'
    elif mr_data.get('state') == 'closed':
        status = 'closed'
    else:
        status = 'open'
    merged_at = parse_datetime(mr_data.get('merged_at')) if mr_data.get('merged_at') else None
    closed_at = parse_datetime(mr_data.get('closed_at')) if mr_data.get('closed_at') else None
    created_at = parse_datetime(mr_data.get('created_at')) if mr_data.get('created_at') else None
    updated_at = parse_datetime(mr_data.get('updated_at')) if mr_data.get('updated_at') else None
    author = mr_data.get('author', {})
    github_username = author.get('username', '')
    github_avatar = author.get('avatar_url', '')

    return {
        'id': mr_data.get('id'),                 # GitLab global ID -> github_id
        'iid': mr_data.get('iid'),                # project‑scoped number -> number
        'title': mr_data.get('title', ''),
        'description': mr_data.get('description', ''),
        'state': status,
        'author_username': github_username,
        'author_avatar': github_avatar,
        'web_url': mr_data.get('web_url', ''),
        'target_branch': mr_data.get('target_branch', ''),
        'source_branch': mr_data.get('source_branch', ''),
        'merged_at': merged_at,
        'closed_at': closed_at,
        'created_at': created_at,
        'updated_at': updated_at,
        'additions': 0,
        'deletions': 0,
        'changed_files': 0,
        'comments_count': mr_data.get('user_notes_count', 0),
        'review_comments_count': 0,
        'commits_count': mr_data.get('commits_count', 0),
        'is_draft': mr_data.get('draft', False),
    }


def fetch_mr_files_from_gitlab(repository, mr_iid):
    """
    Fetch the changes (files) of a specific merge request.
    Returns a list of file dicts with keys: filename, status, additions, deletions, patch.
    """
    encoded_path = encode_project_path(repository.full_name)
    url = f'https://gitlab.com/api/v4/projects/{encoded_path}/merge_requests/{mr_iid}/changes'
    headers = get_headers(repository.access_token)
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None, f'GitLab API error: {response.status_code}'

    data = response.json()
    changes = data.get('changes', [])
    files = []
    for change in changes:
        files.append({
            'filename': change.get('new_path', ''),
            'status': change.get('new_file', False) and 'added' or
                      (change.get('deleted_file', False) and 'removed' or 'modified'),
            'additions': change.get('additions', 0),
            'deletions': change.get('deletions', 0),
            'patch': change.get('diff', ''),
        })
    return files, None


def fetch_mr_diff(repository, mr_iid):
    """Fetch unified diff for a merge request by reconstructing from file diffs."""
    files, error = fetch_mr_files_from_gitlab(repository, mr_iid)
    if error:
        return None, error
    diff_lines = []
    for f in files:
        if f.get('patch'):
            diff_lines.append(f'--- a/{f["filename"]}')
            diff_lines.append(f'+++ b/{f["filename"]}')
            diff_lines.append(f['patch'])
    return '\n'.join(diff_lines), None


def fetch_mr_files(repository, mr_iid):
    """Fetch files of a merge request."""
    return fetch_mr_files_from_gitlab(repository, mr_iid)


def fetch_single_mr(repository, mr_iid):
    """Fetch a single merge request details."""
    encoded_path = encode_project_path(repository.full_name)
    url = f'https://gitlab.com/api/v4/projects/{encoded_path}/merge_requests/{mr_iid}'
    headers = get_headers(repository.access_token)
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None, f'Failed to fetch MR: {response.status_code}'
    return response.json(), None