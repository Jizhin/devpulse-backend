from django.db import models
from accounts.models import User
from repositories.models import Repository
from pullrequests.models import PullRequest


class CodeReview(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    pull_request = models.ForeignKey(
        PullRequest,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='triggered_reviews'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    total_issues = models.IntegerField(default=0)
    critical_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    info_count = models.IntegerField(default=0)
    ai_summary = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'code_reviews'
        verbose_name = 'Code Review'
        verbose_name_plural = 'Code Reviews'
        ordering = ['-created_at']

    def __str__(self):
        return f'Review for PR #{self.pull_request.number} - {self.status}'


class ReviewIssue(models.Model):
    SEVERITY_CHOICES = (
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    )

    CATEGORY_CHOICES = (
        ('security', 'Security'),
        ('performance', 'Performance'),
        ('logic', 'Logic'),
        ('style', 'Style'),
        ('testing', 'Testing'),
        ('documentation', 'Documentation'),
    )

    review = models.ForeignKey(
        CodeReview,
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
        default='style'
    )
    file_name = models.CharField(max_length=500, blank=True, null=True)
    line_number = models.IntegerField(blank=True, null=True)
    code_snippet = models.TextField(blank=True, null=True)
    suggestion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_issues'
        verbose_name = 'Review Issue'
        verbose_name_plural = 'Review Issues'
        ordering = ['-severity', 'category']

    def __str__(self):
        return f'{self.severity} - {self.title}'