import requests
import base64

SCANNABLE_EXTENSIONS = [
    '.py', '.js', '.ts', '.jsx', '.tsx',
    '.java', '.php', '.rb', '.go', '.cs',
    '.cpp', '.c', '.h', '.swift', '.kt',
    '.vue', '.html', '.css', '.scss',
    '.json', '.yaml', '.yml', '.env',
    '.sh', '.bash', '.sql',
]

MAX_FILE_SIZE = 50000
MAX_FILES = 20


def get_headers(access_token):
    return {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json',
    }


def fetch_repo_tree(repository, branch='main'):
    url = f'https://api.github.com/repos/{repository.full_name}/git/trees/{branch}?recursive=1'
    headers = get_headers(repository.access_token)
    response = requests.get(url, headers=headers)

    if response.status_code == 404:
        url = f'https://api.github.com/repos/{repository.full_name}/git/trees/master?recursive=1'
        response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None, f'Failed to fetch repo tree: {response.status_code}'

    tree = response.json().get('tree', [])
    return tree, None


def is_scannable_file(file_path):
    if any(skip in file_path for skip in [
        'node_modules/', 'venv/', '.git/',
        'dist/', 'build/', '__pycache__/',
        '.min.js', '.min.css', 'migrations/',
        'static/', 'media/',
    ]):
        return False

    return any(file_path.endswith(ext) for ext in SCANNABLE_EXTENSIONS)


def fetch_file_content(repository, file_path):
    url = f'https://api.github.com/repos/{repository.full_name}/contents/{file_path}'
    headers = get_headers(repository.access_token)
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None, f'Failed to fetch file: {response.status_code}'

    data = response.json()
    if data.get('encoding') == 'base64':
        try:
            content = base64.b64decode(data['content']).decode('utf-8', errors='ignore')
            return content, None
        except Exception as e:
            return None, f'Failed to decode file: {str(e)}'

    return None, 'Unknown encoding'


def fetch_dependency_files(repository):
    dependency_files = [
        'requirements.txt',
        'package.json',
        'Pipfile',
        'pom.xml',
        'build.gradle',
        'Gemfile',
        'composer.json',
    ]

    found_files = {}
    for filename in dependency_files:
        content, error = fetch_file_content(repository, filename)
        if content:
            found_files[filename] = content

    return found_files


def get_scannable_files(repository, branch='main'):
    tree, error = fetch_repo_tree(repository, branch)
    if error:
        return None, error

    scannable = [
        item for item in tree
        if item['type'] == 'blob' and is_scannable_file(item['path'])
    ]

    scannable = sorted(scannable, key=lambda x: (
        0 if any(x['path'].endswith(ext) for ext in ['.env', '.yaml', '.yml']) else
        1 if x['path'].endswith('.py') else
        2 if x['path'].endswith(('.js', '.ts', '.jsx', '.tsx')) else
        3
    ))

    return scannable[:MAX_FILES], None


def fetch_files_for_scan(repository, branch='main'):
    scannable_files, error = get_scannable_files(repository, branch)
    if error:
        return None, None, error

    files_content = {}
    for file_info in scannable_files:
        file_path = file_info['path']
        content, err = fetch_file_content(repository, file_path)
        if content and len(content) <= MAX_FILE_SIZE:
            files_content[file_path] = content

    dependency_files = fetch_dependency_files(repository)

    return files_content, dependency_files, None


def fetch_repo_issues(repository, state='open'):
    url = f'https://api.github.com/repos/{repository.full_name}/issues'
    headers = get_headers(repository.access_token)
    params = {'state': state, 'per_page': 100}  # Adjust per_page as needed
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        return None, f'Failed to fetch issues: {response.status_code}'

    issues = response.json()
    issues = [i for i in issues if 'pull_request' not in i]
    return issues, None


def fetch_pr_diff(repository, pr_number):
    """Fetch unified diff for a pull request."""
    url = f'https://api.github.com/repos/{repository.full_name}/pulls/{pr_number}'
    headers = {
        'Authorization': f'token {repository.access_token}',
        'Accept': 'application/vnd.github.v3.diff',
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text, None
    return None, f'Failed to fetch PR diff: {response.status_code}'


def fetch_pr_files(repository, pr_number):
    """Fetch list of files changed in a pull request."""
    url = f'https://api.github.com/repos/{repository.full_name}/pulls/{pr_number}/files'
    headers = get_headers(repository.access_token)  # reuse existing
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json(), None
    return None, f'Failed to fetch PR files: {response.status_code}'


def fetch_single_pr(repository, pr_number):
    """Fetch a single pull request details."""
    url = f'https://api.github.com/repos/{repository.full_name}/pulls/{pr_number}'
    headers = get_headers(repository.access_token)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json(), None
    return None, f'Failed to fetch PR: {response.status_code}'