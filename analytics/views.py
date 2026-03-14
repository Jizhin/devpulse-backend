from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg, Q
from accounts.models import User
from repositories.models import Repository
from pullrequests.models import PullRequest
from reviews.models import CodeReview, ReviewIssue
import requests as req


def calculate_quality_score(critical, warning, info):
    score = 100
    score -= critical * 10
    score -= warning * 5
    score -= info * 1
    return max(0, min(100, score))


def get_grade(score):
    if score >= 90:
        return 'A+'
    elif score >= 80:
        return 'A'
    elif score >= 70:
        return 'B+'
    elif score >= 60:
        return 'B'
    else:
        return 'C'


# ─── GitHub live fetch helpers ────────────────────────────────────────────────

def github_headers(token):
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }


def gitlab_headers(token):
    return {'Authorization': f'Bearer {token}'}


def fetch_github_commits_for_user(repository, username):
    """Fetch commits by a specific author from a GitHub repo."""
    url = f'https://api.github.com/repos/{repository.full_name}/commits'
    params = {'author': username, 'per_page': 100}
    all_commits = []
    page = 1
    while page <= 5:  # cap at 500 commits per repo
        params['page'] = page
        response = req.get(url, headers=github_headers(repository.access_token), params=params)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        all_commits.extend(data)
        page += 1
    return all_commits


def fetch_gitlab_commits_for_user(repository, username):
    """Fetch commits by a specific author from a GitLab repo."""
    import urllib.parse
    encoded = urllib.parse.quote(repository.full_name, safe='')
    url = f'https://gitlab.com/api/v4/projects/{encoded}/repository/commits'
    params = {'author': username, 'per_page': 100}
    all_commits = []
    page = 1
    while page <= 5:
        params['page'] = page
        response = req.get(url, headers=gitlab_headers(repository.access_token), params=params)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        all_commits.extend(data)
        page += 1
    return all_commits


def fetch_github_user_profile(username, token):
    """Fetch GitHub public profile for a user."""
    url = f'https://api.github.com/users/{username}'
    response = req.get(url, headers=github_headers(token))
    if response.status_code == 200:
        return response.json()
    return {}


def fetch_gitlab_user_profile(username, token):
    """Fetch GitLab public profile for a user."""
    url = f'https://gitlab.com/api/v4/users?username={username}'
    response = req.get(url, headers=gitlab_headers(token))
    if response.status_code == 200:
        data = response.json()
        return data[0] if data else {}
    return {}


def build_developer_live_data(username, repositories):
    """
    Fetch live data from GitHub/GitLab for a developer across all their repos.
    Returns aggregated commit stats, languages, recent commits.
    """
    total_commits = 0
    recent_commits = []
    languages = {}
    repos_contributed = []
    profile = {}

    for repo in repositories:
        # Fetch profile once from first repo's provider
        if not profile:
            if repo.provider == 'github':
                profile = fetch_github_user_profile(username, repo.access_token)
            else:
                profile = fetch_gitlab_user_profile(username, repo.access_token)

        # Fetch commits
        if repo.provider == 'github':
            commits = fetch_github_commits_for_user(repo, username)
        else:
            commits = fetch_gitlab_commits_for_user(repo, username)

        if commits:
            total_commits += len(commits)
            repos_contributed.append({
                'repo': repo.full_name,
                'provider': repo.provider,
                'commit_count': len(commits),
            })
            # Collect recent commits (latest 3 per repo)
            for c in commits[:3]:
                if repo.provider == 'github':
                    recent_commits.append({
                        'message': c.get('commit', {}).get('message', '').split('\n')[0][:100],
                        'date': c.get('commit', {}).get('author', {}).get('date', ''),
                        'sha': c.get('sha', '')[:7],
                        'repo': repo.full_name,
                        'url': c.get('html_url', ''),
                    })
                else:
                    recent_commits.append({
                        'message': c.get('title', '').split('\n')[0][:100],
                        'date': c.get('created_at', ''),
                        'sha': c.get('short_id', ''),
                        'repo': repo.full_name,
                        'url': c.get('web_url', ''),
                    })

        # Track language
        if repo.language:
            languages[repo.language] = languages.get(repo.language, 0) + 1

    # Sort recent commits by date descending
    recent_commits.sort(key=lambda x: x.get('date', ''), reverse=True)

    return {
        'profile': {
            'name': profile.get('name') or profile.get('public_name') or username,
            'bio': profile.get('bio') or profile.get('job_title', ''),
            'location': profile.get('location', ''),
            'public_repos': profile.get('public_repos') or profile.get('projects_limit', 0),
            'followers': profile.get('followers', 0),
            'avatar': profile.get('avatar_url') or profile.get('avatar', ''),
            'profile_url': profile.get('html_url') or profile.get('web_url', ''),
        },
        'total_commits': total_commits,
        'repos_contributed': repos_contributed,
        'recent_commits': recent_commits[:15],
        'languages': languages,
    }


# ─── Developer Detail View ────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_developer_detail(request, username):
    """
    Full developer profile: DB stats + live GitHub/GitLab data.
    """
    # Get all PRs for this developer across user's repos
    pull_requests = PullRequest.objects.filter(
        repository__owner=request.user,
        github_username=username
    ).select_related('repository')

    if not pull_requests.exists():
        return Response({'error': 'Developer not found'}, status=status.HTTP_404_NOT_FOUND)

    # DB stats
    total_prs = pull_requests.count()
    merged_prs = pull_requests.filter(status='merged').count()
    open_prs = pull_requests.filter(status='open').count()
    closed_prs = pull_requests.filter(status='closed').count()
    total_additions = sum(pr.additions for pr in pull_requests)
    total_deletions = sum(pr.deletions for pr in pull_requests)
    total_changed_files = sum(pr.changed_files for pr in pull_requests)
    total_commits_from_prs = sum(pr.commits_count for pr in pull_requests)

    # Review stats
    total_issues = 0
    critical_issues = 0
    warning_issues = 0
    info_issues = 0
    categories = {}
    pr_reviews = []

    for pr in pull_requests:
        reviews = CodeReview.objects.filter(pull_request=pr, status='completed')
        for review in reviews:
            total_issues += review.total_issues
            critical_issues += review.critical_count
            warning_issues += review.warning_count
            info_issues += review.info_count

            issues = ReviewIssue.objects.filter(review=review)
            for issue in issues:
                categories[issue.category] = categories.get(issue.category, 0) + 1

        if reviews.exists():
            latest = reviews.order_by('-created_at').first()
            pr_reviews.append({
                'pr_number': pr.number,
                'pr_title': pr.title,
                'pr_status': pr.status,
                'total_issues': latest.total_issues,
                'critical': latest.critical_count,
                'warning': latest.warning_count,
                'info': latest.info_count,
                'review_date': latest.created_at.isoformat(),
            })

    quality_score = calculate_quality_score(critical_issues, warning_issues, info_issues)
    grade = get_grade(quality_score)

    # Get unique repos this developer contributed to
    repo_ids = pull_requests.values_list('repository_id', flat=True).distinct()
    repositories = Repository.objects.filter(id__in=repo_ids)

    # Live data from GitHub/GitLab
    live_data = build_developer_live_data(username, repositories)

    # Recent PRs (last 10)
    recent_prs = []
    for pr in pull_requests.order_by('-github_created_at')[:10]:
        recent_prs.append({
            'number': pr.number,
            'title': pr.title,
            'status': pr.status,
            'additions': pr.additions,
            'deletions': pr.deletions,
            'changed_files': pr.changed_files,
            'commits_count': pr.commits_count,
            'repository': pr.repository.full_name,
            'provider': pr.repository.provider,
            'url': pr.url,
            'created_at': pr.github_created_at.isoformat() if pr.github_created_at else None,
            'merged_at': pr.merged_at.isoformat() if pr.merged_at else None,
        })

    return Response({
        'developer': {
            'username': username,
            'avatar': pull_requests.first().github_avatar,
            'provider': repositories.first().provider if repositories.exists() else 'github',
            # DB stats
            'total_prs': total_prs,
            'merged_prs': merged_prs,
            'open_prs': open_prs,
            'closed_prs': closed_prs,
            'total_additions': total_additions,
            'total_deletions': total_deletions,
            'total_changed_files': total_changed_files,
            'total_commits_from_prs': total_commits_from_prs,
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'warning_issues': warning_issues,
            'info_issues': info_issues,
            'quality_score': quality_score,
            'grade': grade,
            'categories': categories,
            'top_issue_category': max(categories, key=categories.get) if categories else None,
            # Live data from GitHub/GitLab
            'live': live_data,
            # Recent activity
            'recent_prs': recent_prs,
            'pr_reviews': pr_reviews,
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_developer(request, username):
    """
    Re-fetch live data for a developer from GitHub/GitLab.
    Returns only the live portion (commits, profile, languages).
    """
    pull_requests = PullRequest.objects.filter(
        repository__owner=request.user,
        github_username=username
    ).select_related('repository')

    if not pull_requests.exists():
        return Response({'error': 'Developer not found'}, status=status.HTTP_404_NOT_FOUND)

    repo_ids = pull_requests.values_list('repository_id', flat=True).distinct()
    repositories = Repository.objects.filter(id__in=repo_ids)

    live_data = build_developer_live_data(username, repositories)

    return Response({
        'live': live_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_developer_analytics(request):
    repository_id = request.query_params.get('repository_id')

    pull_requests = PullRequest.objects.filter(
        repository__owner=request.user
    )

    if repository_id:
        pull_requests = pull_requests.filter(repository_id=repository_id)

    developers = {}

    for pr in pull_requests:
        username = pr.github_username
        if not username:
            continue

        if username not in developers:
            developers[username] = {
                'username': username,
                'avatar': pr.github_avatar,
                'total_prs': 0,
                'merged_prs': 0,
                'open_prs': 0,
                'closed_prs': 0,
                'total_issues': 0,
                'critical_issues': 0,
                'warning_issues': 0,
                'info_issues': 0,
                'additions': 0,
                'deletions': 0,
                'changed_files': 0,
                'categories': {},
            }

        dev = developers[username]
        dev['total_prs'] += 1
        dev['additions'] += pr.additions
        dev['deletions'] += pr.deletions
        dev['changed_files'] += pr.changed_files

        if pr.status == 'merged':
            dev['merged_prs'] += 1
        elif pr.status == 'open':
            dev['open_prs'] += 1
        elif pr.status == 'closed':
            dev['closed_prs'] += 1

        reviews = CodeReview.objects.filter(
            pull_request=pr,
            status='completed'
        )

        for review in reviews:
            dev['total_issues'] += review.total_issues
            dev['critical_issues'] += review.critical_count
            dev['warning_issues'] += review.warning_count
            dev['info_issues'] += review.info_count

            issues = ReviewIssue.objects.filter(review=review)
            for issue in issues:
                cat = issue.category
                dev['categories'][cat] = dev['categories'].get(cat, 0) + 1

    result = []
    for username, dev in developers.items():
        score = calculate_quality_score(
            dev['critical_issues'],
            dev['warning_issues'],
            dev['info_issues']
        )
        grade = get_grade(score)

        top_category = None
        if dev['categories']:
            top_category = max(dev['categories'], key=dev['categories'].get)

        result.append({
            'username': dev['username'],
            'avatar': dev['avatar'],
            'total_prs': dev['total_prs'],
            'merged_prs': dev['merged_prs'],
            'open_prs': dev['open_prs'],
            'closed_prs': dev['closed_prs'],
            'total_issues': dev['total_issues'],
            'critical_issues': dev['critical_issues'],
            'warning_issues': dev['warning_issues'],
            'info_issues': dev['info_issues'],
            'additions': dev['additions'],
            'deletions': dev['deletions'],
            'changed_files': dev['changed_files'],
            'quality_score': score,
            'grade': grade,
            'top_issue_category': top_category,
        })

    result.sort(key=lambda x: x['quality_score'], reverse=True)

    return Response({
        'developers': result,
        'count': len(result)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_repository_analytics(request):
    repository_id = request.query_params.get('repository_id')

    repositories = Repository.objects.filter(owner=request.user)

    if repository_id:
        repositories = repositories.filter(id=repository_id)

    result = []
    for repo in repositories:
        total_prs = PullRequest.objects.filter(repository=repo).count()
        open_prs = PullRequest.objects.filter(repository=repo, status='open').count()
        merged_prs = PullRequest.objects.filter(repository=repo, status='merged').count()
        closed_prs = PullRequest.objects.filter(repository=repo, status='closed').count()

        total_reviews = CodeReview.objects.filter(
            repository=repo,
            status='completed'
        ).count()

        issues = ReviewIssue.objects.filter(review__repository=repo)
        total_issues = issues.count()
        critical_issues = issues.filter(severity='critical').count()
        warning_issues = issues.filter(severity='warning').count()
        info_issues = issues.filter(severity='info').count()

        security_issues = issues.filter(category='security').count()
        performance_issues = issues.filter(category='performance').count()
        logic_issues = issues.filter(category='logic').count()
        style_issues = issues.filter(category='style').count()

        avg_score = 100
        if total_issues > 0:
            avg_score = calculate_quality_score(
                critical_issues,
                warning_issues,
                info_issues
            )

        result.append({
            'id': repo.id,
            'name': repo.name,
            'full_name': repo.full_name,
            'language': repo.language,
            'total_prs': total_prs,
            'open_prs': open_prs,
            'merged_prs': merged_prs,
            'closed_prs': closed_prs,
            'total_reviews': total_reviews,
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'warning_issues': warning_issues,
            'info_issues': info_issues,
            'security_issues': security_issues,
            'performance_issues': performance_issues,
            'logic_issues': logic_issues,
            'style_issues': style_issues,
            'quality_score': avg_score,
            'grade': get_grade(avg_score),
        })

    return Response({
        'repositories': result,
        'count': len(result)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_overview_stats(request):
    total_repos = Repository.objects.filter(owner=request.user).count()
    total_prs = PullRequest.objects.filter(repository__owner=request.user).count()
    open_prs = PullRequest.objects.filter(repository__owner=request.user, status='open').count()
    merged_prs = PullRequest.objects.filter(repository__owner=request.user, status='merged').count()
    total_reviews = CodeReview.objects.filter(repository__owner=request.user, status='completed').count()
    total_issues = ReviewIssue.objects.filter(review__repository__owner=request.user).count()
    critical_issues = ReviewIssue.objects.filter(review__repository__owner=request.user, severity='critical').count()

    return Response({
        'stats': {
            'total_repos': total_repos,
            'total_prs': total_prs,
            'open_prs': open_prs,
            'merged_prs': merged_prs,
            'total_reviews': total_reviews,
            'total_issues': total_issues,
            'critical_issues': critical_issues,
        }
    }, status=status.HTTP_200_OK)