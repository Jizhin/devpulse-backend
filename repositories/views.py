from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
import requests
from .models import Repository
from .serializers import RepositorySerializer, AddRepositorySerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_repositories(request):
    repositories = Repository.objects.filter(owner=request.user)
    serializer = RepositorySerializer(repositories, many=True)
    return Response({
        'repositories': serializer.data,
        'count': repositories.count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_repository(request):
    serializer = AddRepositorySerializer(data=request.data)
    if serializer.is_valid():
        validated_data = serializer.validated_data
        repo_data = validated_data.get('repo_data', {})   # normalized data
        if Repository.objects.filter(
            owner=request.user,
            full_name=validated_data['full_name']
        ).exists():
            return Response({
                'error': 'Repository already connected'
            }, status=status.HTTP_400_BAD_REQUEST)

        repository = Repository.objects.create(
            owner=request.user,
            name=repo_data.get('name', ''),
            full_name=repo_data.get('full_name', ''),
            description=repo_data.get('description', ''),
            url=repo_data.get('html_url', ''),
            clone_url=repo_data.get('clone_url', ''),
            provider=validated_data['provider'],
            access_token=validated_data['access_token'],
            status='active',
            is_private=repo_data.get('private', False),
            default_branch=repo_data.get('default_branch', 'main'),
            stars_count=repo_data.get('stargazers_count', 0),
            forks_count=repo_data.get('forks_count', 0),
            open_issues_count=repo_data.get('open_issues_count', 0),
            language=repo_data.get('language', ''),
            last_synced_at=timezone.now()
        )

        return Response({
            'message': 'Repository connected successfully',
            'repository': RepositorySerializer(repository).data
        }, status=status.HTTP_201_CREATED)

    return Response({
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_repository(request, repo_id):
    try:
        repository = Repository.objects.get(
            id=repo_id,
            owner=request.user
        )
        serializer = RepositorySerializer(repository)
        return Response({
            'repository': serializer.data
        }, status=status.HTTP_200_OK)
    except Repository.DoesNotExist:
        return Response({
            'error': 'Repository not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_repository(request, repo_id):
    try:
        repository = Repository.objects.get(
            id=repo_id,
            owner=request.user
        )
        repo_name = repository.full_name
        repository.delete()
        return Response({
            'message': f'Repository {repo_name} disconnected successfully'
        }, status=status.HTTP_200_OK)
    except Repository.DoesNotExist:
        return Response({
            'error': 'Repository not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_repository(request, repo_id):
    try:
        repository = Repository.objects.get(
            id=repo_id,
            owner=request.user
        )

        repository.status = 'syncing'
        repository.save()
        if repository.provider == 'github':
            url = f'https://api.github.com/repos/{repository.full_name}'
            headers = {
                'Authorization': f'token {repository.access_token}',
                'Accept': 'application/vnd.github.v3+json',
            }
        elif repository.provider == 'gitlab':
            encoded_path = repository.full_name.replace('/', '%2F')
            url = f'https://gitlab.com/api/v4/projects/{encoded_path}'
            headers = {'Authorization': f'Bearer {repository.access_token}'}
        else:
            return Response({'error': 'Unsupported provider'}, status=400)

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            raw_data = response.json()
            if repository.provider == 'github':
                repo_data = raw_data
            else:
                repo_data = {
                    'name': raw_data.get('name'),
                    'description': raw_data.get('description'),
                    'stargazers_count': raw_data.get('star_count', 0),
                    'forks_count': raw_data.get('forks_count', 0),
                    'open_issues_count': raw_data.get('open_issues_count', 0),
                    'language': raw_data.get('language'),
                    'default_branch': raw_data.get('default_branch', 'main'),
                }

            repository.name = repo_data.get('name', repository.name)
            repository.description = repo_data.get('description', repository.description)
            repository.stars_count = repo_data.get('stargazers_count', repository.stars_count)
            repository.forks_count = repo_data.get('forks_count', repository.forks_count)
            repository.open_issues_count = repo_data.get('open_issues_count', repository.open_issues_count)
            repository.language = repo_data.get('language', repository.language)
            repository.default_branch = repo_data.get('default_branch', repository.default_branch)
            repository.status = 'active'
            repository.last_synced_at = timezone.now()
            repository.save()

            return Response({
                'message': 'Repository synced successfully',
                'repository': RepositorySerializer(repository).data
            }, status=status.HTTP_200_OK)
        else:
            repository.status = 'error'
            repository.save()
            return Response({
                'error': f'Failed to sync repository from {repository.provider}'
            }, status=status.HTTP_400_BAD_REQUEST)

    except Repository.DoesNotExist:
        return Response({'error': 'Repository not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_repository_branches(request, repo_id):
    try:
        repository = Repository.objects.get(id=repo_id, owner=request.user)

        if repository.provider == 'github':
            url = f'https://api.github.com/repos/{repository.full_name}/branches'
            headers = {
                'Authorization': f'token {repository.access_token}',
                'Accept': 'application/vnd.github.v3+json',
            }
        elif repository.provider == 'gitlab':
            encoded_path = repository.full_name.replace('/', '%2F')
            url = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/branches'
            headers = {'Authorization': f'Bearer {repository.access_token}'}
        else:
            return Response({'error': 'Unsupported provider'}, status=400)

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            return Response({'error': 'Failed to fetch branches'}, status=400)

        if repository.provider == 'github':
            branches = [b['name'] for b in response.json()]
        else:
            branches = [b['name'] for b in response.json()]

        return Response({
            'repository': repository.full_name,
            'branches': branches
        })

    except Repository.DoesNotExist:
        return Response({'error': 'Repository not found'}, status=404)