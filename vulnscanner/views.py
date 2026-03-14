from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import VulnScan
from .serializers import TriggerVulnScanSerializer, VulnScanSerializer
from .services import scan_target_url

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_vuln_scan(request):
    serializer = TriggerVulnScanSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    target_url = serializer.validated_data['target_url']
    scan = VulnScan.objects.create(
        target_url=target_url,
        triggered_by=request.user,
        status='scanning'
    )

    try:
        result = scan_target_url(target_url)
        scan.status = 'completed'
        scan.result_summary = result['summary']
        scan.issues = result['issues']
        # optionally store raw headers
        scan.save()
    except Exception as e:
        scan.status = 'failed'
        scan.error_message = str(e)
        scan.save()
        return Response({
            'error': f'Scan failed: {e}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'message': 'Vulnerability scan completed',
        'scan': VulnScanSerializer(scan).data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_vuln_scans(request):
    scans = VulnScan.objects.filter(triggered_by=request.user).order_by('-created_at')
    serializer = VulnScanSerializer(scans, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vuln_scan(request, scan_id):
    try:
        scan = VulnScan.objects.get(id=scan_id, triggered_by=request.user)
    except VulnScan.DoesNotExist:
        return Response({'error': 'Scan not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = VulnScanSerializer(scan)
    return Response(serializer.data)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vuln_scan(request, scan_id):
    try:
        scan = VulnScan.objects.get(id=scan_id, triggered_by=request.user)
    except VulnScan.DoesNotExist:
        return Response({'error': 'Scan not found'}, status=status.HTTP_404_NOT_FOUND)
    scan.delete()
    return Response({'message': 'Scan deleted'}, status=status.HTTP_204_NO_CONTENT)