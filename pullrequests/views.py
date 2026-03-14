from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.dateparse import parse_datetime
import requests

from .models import PullRequest
from .serializers import PullRequestSerializer, PullRequestSyncSerializer
from repositories.models import Repository
from .gitlab_service import (
    fetch_mrs_from_gitlab,
    fetch_mr_files_from_gitlab,
    normalize_mr,
)

def fetch_github_prs(repository, status_filter='all'):
    all_prs = []
    page = 1

    while True:
        url = f'https://api.github.com/repos/{repository.full_name}/pulls'
        headers = {
            'Authorization': f'token {repository.access_token}',
            'Accept': 'application/vnd.github.v3+json',
        }
        params = {
            'state': status_filter,
            'per_page': 100,
            'page': page,
        }
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return None, f'GitHub API error: {response.status_code}'

        prs = response.json()
        if not prs:
            break

        all_prs.extend(prs)
        page += 1

    return all_prs, None


def fetch_github_pr_files(repository, pr_number):
    url = f'https://api.github.com/repos/{repository.full_name}/pulls/{pr_number}/files'
    headers = {
        'Authorization': f'token {repository.access_token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None, 'Failed to fetch PR files from GitHub'

    files = []
    for f in response.json():
        files.append({
            'filename': f.get('filename'),
            'status': f.get('status'),
            'additions': f.get('additions'),
            'deletions': f.get('deletions'),
            'patch': f.get('patch'),
        })
    return files, None


def fetch_gitlab_mrs(repository, status_filter='all'):
    raw_mrs, error = fetch_mrs_from_gitlab(repository, status_filter)
    if error:
        return None, error
    normalized = [normalize_mr(mr) for mr in raw_mrs]
    return normalized, None


def fetch_gitlab_mr_files(repository, mr_iid):
    return fetch_mr_files_from_gitlab(repository, mr_iid)



def fetch_pull_requests(repository, status_filter='all'):
    if repository.provider == 'github':
        return fetch_github_prs(repository, status_filter)
    elif repository.provider == 'gitlab':
        return fetch_gitlab_mrs(repository, status_filter)
    else:
        return None, f'Unsupported provider: {repository.provider}'


def fetch_pull_request_files(repository, pr_number, provider):
    if provider == 'github':
        return fetch_github_pr_files(repository, pr_number)
    elif provider == 'gitlab':
        return fetch_gitlab_mr_files(repository, pr_number)
    else:
        return None, 'Unsupported provider'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_pull_requests(request):
    repository_id = request.query_params.get('repository_id')
    status_filter = request.query_params.get('status')
    branch = request.query_params.get('branch')

    pull_requests = PullRequest.objects.filter(repository__owner=request.user)

    if repository_id:
        pull_requests = pull_requests.filter(repository_id=repository_id)

    if branch:
        pull_requests = pull_requests.filter(base_branch=branch)

    if status_filter and status_filter in ['open', 'closed', 'merged']:
        pull_requests = pull_requests.filter(status=status_filter)

    serializer = PullRequestSerializer(pull_requests, many=True)

    return Response({
        'pull_requests': serializer.data,
        'count': pull_requests.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_pull_requests(request):
    serializer = PullRequestSyncSerializer(data=request.data)

    if serializer.is_valid():
        repository_id = serializer.validated_data['repository_id']
        status_filter = serializer.validated_data.get('status_filter', 'all')

        try:
            repository = Repository.objects.get(
                id=repository_id,
                owner=request.user
            )
        except Repository.DoesNotExist:
            return Response({'error': 'Repository not found'},
                            status=status.HTTP_404_NOT_FOUND)
        items, error = fetch_pull_requests(repository, status_filter)

        if error:
            return Response({'error': error},
                            status=status.HTTP_400_BAD_REQUEST)

        synced_count = 0

        for item in items:
            if repository.provider == 'github':
                merged_at = parse_datetime(item.get('merged_at')) if item.get('merged_at') else None
                closed_at = parse_datetime(item.get('closed_at')) if item.get('closed_at') else None
                github_created_at = parse_datetime(item.get('created_at')) if item.get('created_at') else None
                github_updated_at = parse_datetime(item.get('updated_at')) if item.get('updated_at') else None

                if item.get('merged_at'):
                    pr_status = 'merged'
                elif item.get('state') == 'closed':
                    pr_status = 'closed'
                else:
                    pr_status = 'open'

                defaults = {
                    'number': item['number'],
                    'title': item['title'],
                    'description': item.get('body', ''),
                    'status': pr_status,
                    'github_username': item['user']['login'],
                    'github_avatar': item['user']['avatar_url'],
                    'url': item['html_url'],
                    'base_branch': item['base']['ref'],
                    'head_branch': item['head']['ref'],
                    'additions': 0,
                    'deletions': 0,
                    'changed_files': 0,
                    'comments_count': item.get('comments', 0),
                    'review_comments_count': item.get('review_comments', 0),
                    'commits_count': item.get('commits', 0),
                    'is_draft': item.get('draft', False),
                    'merged_at': merged_at,
                    'closed_at': closed_at,
                    'github_created_at': github_created_at,
                    'github_updated_at': github_updated_at,
                }
            else:
                defaults = {
                    'number': item['iid'],
                    'title': item['title'],
                    'description': item.get('description', ''),
                    'status': item['state'],
                    'github_username': item['author_username'],
                    'github_avatar': item['author_avatar'],
                    'url': item['web_url'],
                    'base_branch': item['target_branch'],
                    'head_branch': item['source_branch'],
                    'additions': item.get('additions', 0),
                    'deletions': item.get('deletions', 0),
                    'changed_files': item.get('changed_files', 0),
                    'comments_count': item.get('comments_count', 0),
                    'review_comments_count': item.get('review_comments_count', 0),
                    'commits_count': item.get('commits_count', 0),
                    'is_draft': item.get('is_draft', False),
                    'merged_at': item.get('merged_at'),
                    'closed_at': item.get('closed_at'),
                    'github_created_at': item.get('created_at'),
                    'github_updated_at': item.get('updated_at'),
                }

            PullRequest.objects.update_or_create(
                repository=repository,
                github_id=item['id'],
                defaults=defaults
            )
            synced_count += 1

        return Response({
            'message': f'Successfully synced {synced_count} pull requests',
            'synced_count': synced_count
        })

    return Response({'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pull_request(request, pr_id):
    try:
        pull_request = PullRequest.objects.get(
            id=pr_id,
            repository__owner=request.user
        )
        serializer = PullRequestSerializer(pull_request)
        return Response({'pull_request': serializer.data})
    except PullRequest.DoesNotExist:
        return Response({'error': 'Pull request not found'},
                        status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_repository_pr_stats(request, repository_id):
    try:
        repository = Repository.objects.get(
            id=repository_id,
            owner=request.user
        )
        total = PullRequest.objects.filter(repository=repository).count()
        open_count = PullRequest.objects.filter(repository=repository, status='open').count()
        closed_count = PullRequest.objects.filter(repository=repository, status='closed').count()
        merged_count = PullRequest.objects.filter(repository=repository, status='merged').count()

        return Response({
            'repository': repository.full_name,
            'stats': {
                'total': total,
                'open': open_count,
                'closed': closed_count,
                'merged': merged_count,
            }
        })
    except Repository.DoesNotExist:
        return Response({'error': 'Repository not found'},
                        status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pull_request_files(request, pr_id):
    try:
        pr = PullRequest.objects.get(
            id=pr_id,
            repository__owner=request.user
        )
    except PullRequest.DoesNotExist:
        return Response({'error': 'Pull request not found'},
                        status=status.HTTP_404_NOT_FOUND)

    repository = pr.repository
    files, error = fetch_pull_request_files(repository, pr.number, repository.provider)

    if error:
        return Response({'error': error},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({'files': files})