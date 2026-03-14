import google.generativeai as genai
import json
import os
from .provider_utils import fetch_diff, fetch_files

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


def build_review_prompt(pull_request, diff, files):
    files_summary = ''
    if files:
        for f in files[:10]:
            filename = f.get('filename') or f.get('new_path', '')
            additions = f.get('additions', 0)
            deletions = f.get('deletions', 0)
            files_summary += f"- {filename} (+{additions} -{deletions})\n"

    prompt = f"""
You are an expert code reviewer. Review the following Pull Request and identify issues.

PR Title: {pull_request.title}
PR Description: {pull_request.description or 'No description provided'}
Base Branch: {pull_request.base_branch}
Head Branch: {pull_request.head_branch}

Files Changed:
{files_summary}

Code Diff:
{diff[:8000]}

Your task is to analyze this code and return a JSON response with the following structure:
{{
    "summary": "A 2-3 sentence overall summary of the PR and its quality",
    "issues": [
        {{
            "title": "Short title of the issue",
            "description": "Detailed description of the issue",
            "severity": "critical|warning|info",
            "category": "security|performance|logic|style|testing|documentation",
            "file_name": "path/to/file.ext or null",
            "line_number": 42 or null,
            "code_snippet": "the problematic code snippet or null",
            "suggestion": "How to fix this issue"
        }}
    ]
}}

Severity guidelines:
- critical: Security vulnerabilities, data loss risks, breaking bugs
- warning: Performance issues, bad practices, potential bugs
- info: Style improvements, documentation, minor suggestions

Return ONLY the JSON object, no other text.
"""
    return prompt


def analyze_code_with_gemini(pull_request, repository):
    diff, error = fetch_diff(repository, pull_request)
    if error:
        return None, error

    if not diff or len(diff.strip()) == 0:
        return {
            'summary': 'No code changes found in this PR.',
            'issues': []
        }, None

    files, _ = fetch_files(repository, pull_request)

    prompt = build_review_prompt(pull_request, diff, files)

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]

        result = json.loads(response_text.strip())
        return result, None

    except json.JSONDecodeError as e:
        return None, f'Failed to parse AI response: {str(e)}'
    except Exception as e:
        return None, f'AI service error: {str(e)}'