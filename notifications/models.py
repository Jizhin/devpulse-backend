from django.db import models
from accounts.models import User


class Notification(models.Model):
    TYPE_CHOICES = (
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
        ('success', 'Success'),
    )

    SOURCE_CHOICES = (
        ('review', 'AI Review'),
        ('scan', 'Repo Scan'),
        ('system', 'System'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=300)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='info'
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='system'
    )
    is_read = models.BooleanField(default=False)
    source_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.type} - {self.title}'