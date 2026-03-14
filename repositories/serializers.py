from rest_framework import serializers
from .models import Repository
import requests


class RepositorySerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    owner_email = serializers.CharField(source='owner.email', read_only=True)

    class Meta:
        model = Repository
        fields = [
            'id',
            'owner_username',
            'owner_email',
            'name',
            'full_name',
            'description',
            'url',
            'clone_url',
            'provider',
            'status',
            'is_private',
            'default_branch',
            'stars_count',
            'forks_count',
            'open_issues_count',
            'language',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'name',
            'full_name',
            'description',
            'url',
            'clone_url',
            'status',
            'is_private',
            'default_branch',
            'stars_count',
            'forks_count',
            'open_issues_count',
            'language',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]


class AddRepositorySerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=Repository.PROVIDER_CHOICES, default='github')
    full_name = serializers.CharField(max_length=255)
    access_token = serializers.CharField(max_length=500, write_only=True)

    def validate(self, data):
        provider = data.get('provider')
        full_name = data.get('full_name')
        token = data.get('access_token')

        if provider == 'github':
            api_url = f'https://api.github.com/repos/{full_name}'
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json',
            }
        elif provider == 'gitlab':
            encoded_path = full_name.replace('/', '%2F')
            api_url = f'https://gitlab.com/api/v4/projects/{encoded_path}'
            headers = {'Authorization': f'Bearer {token}'}
        else:
            raise serializers.ValidationError("Unsupported provider")

        response = requests.get(api_url, headers=headers)

        if response.status_code != 200:
            raise serializers.ValidationError(
                f"Failed to fetch repository from {provider}. Check your token and repository name."
            )

        repo_data = response.json()

        normalized = self._normalize_repo_data(provider, repo_data)
        data['repo_data'] = normalized
        return data

    def _normalize_repo_data(self, provider, raw):
        """Convert provider-specific API response to a common format."""
        if provider == 'github':
            return {
                'name': raw.get('name'),
                'full_name': raw.get('full_name'),
                'description': raw.get('description'),
                'html_url': raw.get('html_url'),
                'clone_url': raw.get('clone_url'),
                'private': raw.get('private', False),
                'default_branch': raw.get('default_branch', 'main'),
                'stargazers_count': raw.get('stargazers_count', 0),
                'forks_count': raw.get('forks_count', 0),
                'open_issues_count': raw.get('open_issues_count', 0),
                'language': raw.get('language'),
            }
        elif provider == 'gitlab':
            return {
                'name': raw.get('name'),
                'full_name': raw.get('path_with_namespace'),
                'description': raw.get('description'),
                'html_url': raw.get('web_url'),
                'clone_url': raw.get('http_url_to_repo'),
                'private': raw.get('visibility') == 'private',
                'default_branch': raw.get('default_branch', 'main'),
                'stargazers_count': raw.get('star_count', 0),
                'forks_count': raw.get('forks_count', 0),
                'open_issues_count': raw.get('open_issues_count', 0),
                'language': raw.get('language'),
            }
        return {}