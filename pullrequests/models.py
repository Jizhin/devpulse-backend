from django.db import models
from accounts.models import User
from repositories.models import Repository


class PullRequest(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('merged', 'Merged'),
    )

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='pull_requests'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pull_requests'
    )
    github_id = models.IntegerField()
    number = models.IntegerField()
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )
    github_username = models.CharField(max_length=100, blank=True, null=True)
    github_avatar = models.URLField(blank=True, null=True)
    url = models.URLField()
    base_branch = models.CharField(max_length=100, default='main')
    head_branch = models.CharField(max_length=100, blank=True, null=True)
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    changed_files = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    review_comments_count = models.IntegerField(default=0)
    commits_count = models.IntegerField(default=0)
    is_draft = models.BooleanField(default=False)
    merged_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    github_created_at = models.DateTimeField(blank=True, null=True)
    github_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pull_requests'
        verbose_name = 'Pull Request'
        verbose_name_plural = 'Pull Requests'
        ordering = ['-github_created_at']
        unique_together = ['repository', 'github_id']

    def __str__(self):
        return f'PR #{self.number} - {self.title}'