import google.generativeai as genai
import json
import os
from .github_service import fetch_files_for_scan

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


def build_scan_prompt(file_path, file_content, repository_name):
    return f"""
You are an expert code security and quality auditor. Analyze the following file from the repository "{repository_name}".

File: {file_path}

Content:
{file_content[:6000]}

Analyze this file thoroughly for:
1. Security vulnerabilities (hardcoded secrets, SQL injection, XSS, unsafe auth, exposed keys)
2. Performance issues (inefficient algorithms, memory leaks, unnecessary loops, blocking calls)
3. Code quality issues (duplication, long functions, poor naming, missing error handling)
4. Logic errors (edge cases, null checks, race conditions)
5. Style issues (code organization, readability)

Return ONLY a JSON object with this structure:
{{
    "issues": [
        {{
            "title": "Short title of the issue",
            "description": "Detailed description of what the issue is and why it matters",
            "severity": "critical|warning|info",
            "category": "security|performance|quality|dependency|style|logic",
            "file_path": "{file_path}",
            "line_number": null or integer,
            "code_snippet": "the problematic code or null",
            "suggestion": "How to fix this issue"
        }}
    ]
}}

Only report real issues. If the file looks clean, return empty issues array.
Return ONLY the JSON object, no other text.
"""


def build_dependency_prompt(dependency_files, repository_name):
    files_content = ''
    for filename, content in dependency_files.items():
        files_content += f'\n--- {filename} ---\n{content[:2000]}\n'

    return f"""
You are an expert in software dependencies and security. Analyze the following dependency files from "{repository_name}".

{files_content}

Check for:
1. Outdated packages with known vulnerabilities
2. Missing security-related packages
3. Conflicting dependencies
4. Unnecessary or unused dependencies
5. Missing version pinning

Return ONLY a JSON object with this structure:
{{
    "issues": [
        {{
            "title": "Short title",
            "description": "Detailed description",
            "severity": "critical|warning|info",
            "category": "dependency",
            "file_path": "requirements.txt or package.json etc",
            "line_number": null,
            "code_snippet": "the problematic dependency or null",
            "suggestion": "How to fix"
        }}
    ]
}}

Return ONLY the JSON object, no other text.
"""


def parse_ai_response(response_text):
    response_text = response_text.strip()
    if response_text.startswith('```json'):
        response_text = response_text[7:]
    if response_text.startswith('```'):
        response_text = response_text[3:]
    if response_text.endswith('```'):
        response_text = response_text[:-3]
    return json.loads(response_text.strip())


def build_summary_prompt(repository_name, total_files, all_issues):
    critical = sum(1 for i in all_issues if i.get('severity') == 'critical')
    warning = sum(1 for i in all_issues if i.get('severity') == 'warning')
    info = sum(1 for i in all_issues if i.get('severity') == 'info')

    security = sum(1 for i in all_issues if i.get('category') == 'security')
    performance = sum(1 for i in all_issues if i.get('category') == 'performance')
    quality = sum(1 for i in all_issues if i.get('category') == 'quality')

    return f"""
You are a senior engineering lead. Write a brief executive summary for a repository scan.

Repository: {repository_name}
Files Scanned: {total_files}
Total Issues: {len(all_issues)}
Critical: {critical}, Warnings: {warning}, Info: {info}
Security Issues: {security}, Performance: {performance}, Quality: {quality}

Write a 3-4 sentence summary covering:
1. Overall code health
2. Most critical concerns
3. Key recommendations

Return ONLY the summary text, no JSON, no formatting.
"""


def fetch_issues_for_repo(repository):
    if repository.provider == 'github':
        from .github_service import fetch_repo_issues
    elif repository.provider == 'gitlab':
        from .gitlab_service import fetch_repo_issues
    else:
        return None, f'Unsupported provider: {repository.provider}'
    return fetch_repo_issues(repository)

def scan_repository_with_gemini(repository, branch='main'):
    if repository.provider == 'github':
        from .github_service import fetch_files_for_scan
    elif repository.provider == 'gitlab':
        from .gitlab_service import fetch_files_for_scan
    else:
        return None, f'Unsupported provider: {repository.provider}'

    files_content, dependency_files, error = fetch_files_for_scan(repository, branch)

    if error:
        return None, error

    if not files_content:
        return {
            'summary': 'No scannable files found in this repository.',
            'issues': [],
            'total_files_scanned': 0
        }, None

    model = genai.GenerativeModel('gemini-1.5-flash')
    all_issues = []
    files_scanned = 0

    for file_path, content in files_content.items():
        try:
            prompt = build_scan_prompt(file_path, content, repository.full_name)
            response = model.generate_content(prompt)
            result = parse_ai_response(response.text)
            issues = result.get('issues', [])
            all_issues.extend(issues)
            files_scanned += 1
        except Exception:
            continue

    if dependency_files:
        try:
            prompt = build_dependency_prompt(dependency_files, repository.full_name)
            response = model.generate_content(prompt)
            result = parse_ai_response(response.text)
            dep_issues = result.get('issues', [])
            all_issues.extend(dep_issues)
        except Exception:
            pass

    try:
        summary_prompt = build_summary_prompt(
            repository.full_name,
            files_scanned,
            all_issues
        )
        summary_response = model.generate_content(summary_prompt)
        summary = summary_response.text.strip()
    except Exception:
        summary = f'Scanned {files_scanned} files and found {len(all_issues)} issues.'

    return {
        'summary': summary,
        'issues': all_issues,
        'total_files_scanned': files_scanned
    }, None