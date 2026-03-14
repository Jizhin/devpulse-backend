from rest_framework import serializers
from .models import VulnScan

class TriggerVulnScanSerializer(serializers.Serializer):
    target_url = serializers.URLField()

class VulnScanSerializer(serializers.ModelSerializer):
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)
    class Meta:
        model = VulnScan
        fields = '__all__'