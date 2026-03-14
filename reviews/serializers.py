from rest_framework import serializers
from .models import CodeReview, ReviewIssue


class ReviewIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewIssue
        fields = [
            'id',
            'title',
            'description',
            'severity',
            'category',
            'file_name',
            'line_number',
            'code_snippet',
            'suggestion',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
        ]


class CodeReviewSerializer(serializers.ModelSerializer):
    issues = ReviewIssueSerializer(many=True, read_only=True)
    pull_request_number = serializers.IntegerField(source='pull_request.number', read_only=True)
    pull_request_title = serializers.CharField(source='pull_request.title', read_only=True)
    repository_full_name = serializers.CharField(source='repository.full_name', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)

    class Meta:
        model = CodeReview
        fields = [
            'id',
            'pull_request_number',
            'pull_request_title',
            'repository_full_name',
            'triggered_by_username',
            'status',
            'total_issues',
            'critical_count',
            'warning_count',
            'info_count',
            'ai_summary',
            'error_message',
            'issues',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'pull_request_number',
            'pull_request_title',
            'repository_full_name',
            'triggered_by_username',
            'status',
            'total_issues',
            'critical_count',
            'warning_count',
            'info_count',
            'ai_summary',
            'error_message',
            'issues',
            'created_at',
            'updated_at',
        ]


class TriggerReviewSerializer(serializers.Serializer):
    pull_request_id = serializers.IntegerField(required=True)