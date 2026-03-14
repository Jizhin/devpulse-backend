from django.db import models
from accounts.models import User


class Repository(models.Model):
    PROVIDER_CHOICES = (
        ('github', 'GitHub'),
        ('gitlab', 'GitLab'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('syncing', 'Syncing'),
        ('error', 'Error'),
        ('inactive', 'Inactive'),
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='repositories'
    )
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    url = models.URLField()
    clone_url = models.URLField(blank=True, null=True)
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='github'
    )
    access_token = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    is_private = models.BooleanField(default=False)
    default_branch = models.CharField(max_length=100, default='main')
    stars_count = models.IntegerField(default=0)
    forks_count = models.IntegerField(default=0)
    open_issues_count = models.IntegerField(default=0)
    language = models.CharField(max_length=100, blank=True, null=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'repositories'
        verbose_name = 'Repository'
        verbose_name_plural = 'Repositories'
        ordering = ['-created_at']
        unique_together = ['owner', 'full_name']

    def __str__(self):
        return f'{self.full_name} ({self.provider})'