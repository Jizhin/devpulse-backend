from django.db import models
from accounts.models import User
from repositories.models import Repository


class RepoScan(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='scans'
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='triggered_scans'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    branch = models.CharField(max_length=100, default='main')
    total_files_scanned = models.IntegerField(default=0)
    total_issues = models.IntegerField(default=0)
    critical_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    info_count = models.IntegerField(default=0)
    security_count = models.IntegerField(default=0)
    performance_count = models.IntegerField(default=0)
    quality_count = models.IntegerField(default=0)
    dependency_count = models.IntegerField(default=0)
    ai_summary = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'repo_scans'
        verbose_name = 'Repo Scan'
        verbose_name_plural = 'Repo Scans'
        ordering = ['-created_at']

    def __str__(self):
        return f'Scan for {self.repository.full_name} - {self.status}'


class ScanIssue(models.Model):
    SEVERITY_CHOICES = (
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    )

    CATEGORY_CHOICES = (
        ('security', 'Security'),
        ('performance', 'Performance'),
        ('quality', 'Quality'),
        ('dependency', 'Dependency'),
        ('style', 'Style'),
        ('logic', 'Logic'),
    )

    scan = models.ForeignKey(
        RepoScan,
        on_delete=models.CASCADE,
        related_name='issues'
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='info'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='quality'
    )
    file_path = models.CharField(max_length=500, blank=True, null=True)
    line_number = models.IntegerField(blank=True, null=True)
    code_snippet = models.TextField(blank=True, null=True)
    suggestion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scan_issues'
        verbose_name = 'Scan Issue'
        verbose_name_plural = 'Scan Issues'
        ordering = ['severity', 'category']

    def __str__(self):
        return f'{self.severity} - {self.title}'