import requests
import urllib.parse

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
    return {'Authorization': f'Bearer {access_token}'}

def encode_project_path(full_name):
    """URL‑encode the repository path for GitLab API."""
    return urllib.parse.quote(full_name, safe='')

def fetch_repo_tree(repository, branch='main'):
    """Fetch the recursive tree of a GitLab repository."""
    encoded_path = encode_project_path(repository.full_name)
    url = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/tree'
    headers = get_headers(repository.access_token)
    params = {'recursive': True, 'ref': branch, 'per_page': 100}
    all_items = []
    page = 1
    while True:
        params['page'] = page
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return None, f'Failed to fetch repo tree: {response.status_code}'
        data = response.json()
        if not data:
            break
        all_items.extend(data)
        page += 1
    return all_items, None

def is_scannable_file(file_path):
    """Determine if a file should be scanned (same as GitHub)."""
    if any(skip in file_path for skip in [
        'node_modules/', 'venv/', '.git/',
        'dist/', 'build/', '__pycache__/',
        '.min.js', '.min.css', 'migrations/',
        'static/', 'media/',
    ]):
        return False
    return any(file_path.endswith(ext) for ext in SCANNABLE_EXTENSIONS)

def fetch_file_content(repository, file_path, branch='main'):
    """Fetch raw file content from GitLab."""
    encoded_path = encode_project_path(repository.full_name)
    url = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/files/{urllib.parse.quote(file_path, safe="")}/raw'
    headers = get_headers(repository.access_token)
    params = {'ref': branch}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return None, f'Failed to fetch file: {response.status_code}'
    try:
        return response.text, None
    except Exception as e:
        return None, f'Failed to decode file: {str(e)}'

def fetch_dependency_files(repository, branch='main'):
    """Fetch common dependency files (same as GitHub)."""
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
        content, error = fetch_file_content(repository, filename, branch)
        if content:
            found_files[filename] = content
    return found_files

def get_scannable_files(repository, branch='main'):
    """Get a prioritized list of files to scan (max MAX_FILES)."""
    tree, error = fetch_repo_tree(repository, branch)
    if error:
        return None, error
    scannable = [
        item for item in tree
        if item['type'] == 'blob' and is_scannable_file(item['path'])
    ]
    # Prioritize config files, Python, then JS/TS
    scannable = sorted(scannable, key=lambda x: (
        0 if any(x['path'].endswith(ext) for ext in ['.env', '.yaml', '.yml']) else
        1 if x['path'].endswith('.py') else
        2 if x['path'].endswith(('.js', '.ts', '.jsx', '.tsx')) else
        3
    ))
    return scannable[:MAX_FILES], None

def fetch_files_for_scan(repository, branch='main'):
    """Main entry point: fetch all files (scannable + dependency files)."""
    scannable_files, error = get_scannable_files(repository, branch)
    if error:
        return None, None, error
    files_content = {}
    for file_info in scannable_files:
        file_path = file_info['path']
        content, err = fetch_file_content(repository, file_path, branch)
        if content and len(content) <= MAX_FILE_SIZE:
            files_content[file_path] = content
    dependency_files = fetch_dependency_files(repository, branch)
    return files_content, dependency_files, None

def fetch_repo_issues(repository, state='opened'):
    """Fetch issues from GitLab and return them in a common format (title, body)."""
    encoded_path = encode_project_path(repository.full_name)
    url = f'https://gitlab.com/api/v4/projects/{encoded_path}/issues'
    headers = get_headers(repository.access_token)
    params = {'state': state, 'per_page': 100}
    all_issues = []
    page = 1
    while True:
        params['page'] = page
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return None, f'Failed to fetch issues: {response.status_code}'
        data = response.json()
        if not data:
            break
        all_issues.extend(data)
        page += 1
    issues = [{'title': i['title'], 'body': i.get('description', '')} for i in all_issues]
    return issues, None
