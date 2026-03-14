from django.db import models
from django.conf import settings

class VulnScan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    target_url = models.URLField()
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_summary = models.JSONField(default=dict)   # overall summary (e.g., risk counts)
    issues = models.JSONField(default=list)           # list of findings
    raw_response_headers = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.target_url} - {self.created_at}"