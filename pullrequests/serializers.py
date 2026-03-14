from rest_framework import serializers
from .models import PullRequest


class PullRequestSerializer(serializers.ModelSerializer):
    repository_name = serializers.CharField(source='repository.name', read_only=True)
    repository_full_name = serializers.CharField(source='repository.full_name', read_only=True)

    class Meta:
        model = PullRequest
        fields = [
            'id',
            'repository_name',
            'repository_full_name',
            'github_id',
            'number',
            'title',
            'description',
            'status',
            'github_username',
            'github_avatar',
            'url',
            'base_branch',
            'head_branch',
            'additions',
            'deletions',
            'changed_files',
            'comments_count',
            'review_comments_count',
            'commits_count',
            'is_draft',
            'merged_at',
            'closed_at',
            'github_created_at',
            'github_updated_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'repository_name',
            'repository_full_name',
            'github_id',
            'number',
            'title',
            'description',
            'status',
            'github_username',
            'github_avatar',
            'url',
            'base_branch',
            'head_branch',
            'additions',
            'deletions',
            'changed_files',
            'comments_count',
            'review_comments_count',
            'commits_count',
            'is_draft',
            'merged_at',
            'closed_at',
            'github_created_at',
            'github_updated_at',
            'created_at',
            'updated_at',
        ]


class PullRequestSyncSerializer(serializers.Serializer):
    repository_id = serializers.IntegerField(required=True)
    status_filter = serializers.ChoiceField(
        choices=['open', 'closed', 'all'],
        default='all',
        required=False
    )