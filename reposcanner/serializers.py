from rest_framework import serializers
from .models import RepoScan, ScanIssue


class ScanIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanIssue
        fields = [
            'id',
            'title',
            'description',
            'severity',
            'category',
            'file_path',
            'line_number',
            'code_snippet',
            'suggestion',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
        ]


class RepoScanSerializer(serializers.ModelSerializer):
    issues = ScanIssueSerializer(many=True, read_only=True)
    repository_name = serializers.CharField(source='repository.name', read_only=True)
    repository_full_name = serializers.CharField(source='repository.full_name', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)

    class Meta:
        model = RepoScan
        fields = [
            'id',
            'repository_name',
            'repository_full_name',
            'triggered_by_username',
            'status',
            'branch',
            'total_files_scanned',
            'total_issues',
            'critical_count',
            'warning_count',
            'info_count',
            'security_count',
            'performance_count',
            'quality_count',
            'dependency_count',
            'ai_summary',
            'error_message',
            'issues',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'repository_name',
            'repository_full_name',
            'triggered_by_username',
            'status',
            'branch',
            'total_files_scanned',
            'total_issues',
            'critical_count',
            'warning_count',
            'info_count',
            'security_count',
            'performance_count',
            'quality_count',
            'dependency_count',
            'ai_summary',
            'error_message',
            'issues',
            'created_at',
            'updated_at',
        ]


class TriggerScanSerializer(serializers.Serializer):
    repository_id = serializers.IntegerField(required=True)
    branch = serializers.CharField(required=False, default='main')