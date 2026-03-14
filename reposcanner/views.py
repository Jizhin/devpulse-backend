from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import RepoScan, ScanIssue
from .serializers import RepoScanSerializer, TriggerScanSerializer
from .scan_service import scan_repository_with_gemini
from repositories.models import Repository
from notifications.models import Notification
from .github_service import fetch_repo_issues

def fetch_issues_for_repo(repository):
    """Fetch issues using the appropriate provider service."""
    if repository.provider == 'github':
        from .github_service import fetch_repo_issues
    elif repository.provider == 'gitlab':
        from .gitlab_service import fetch_repo_issues
    else:
        return None, f'Unsupported provider: {repository.provider}'
    return fetch_repo_issues(repository)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_scan(request):
    serializer = TriggerScanSerializer(data=request.data)
    if serializer.is_valid():
        repository_id = serializer.validated_data['repository_id']
        branch = serializer.validated_data.get('branch', 'main')

        try:
            repository = Repository.objects.get(
                id=repository_id,
                owner=request.user
            )
        except Repository.DoesNotExist:
            return Response({
                'error': 'Repository not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Block if a completed scan already exists for this repo
        existing_scan = RepoScan.objects.filter(
            repository=repository,
            status='completed'
        ).first()

        if existing_scan:
            return Response({
                'error': 'This repository has already been scanned. Use re-scan to update the existing scan.',
                'scan_id': existing_scan.id
            }, status=status.HTTP_400_BAD_REQUEST)

        scan = RepoScan.objects.create(
            repository=repository,
            triggered_by=request.user,
            status='scanning',
            branch=branch
        )

        # ----- AI scan (Gemini) -----
        scan_result, error = scan_repository_with_gemini(repository, branch)

        if error:
            scan.status = 'failed'
            scan.error_message = error
            scan.save()
            return Response({
                'error': f'Scan failed: {error}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        issues = scan_result.get('issues', [])
        critical_count = 0
        warning_count = 0
        info_count = 0
        security_count = 0
        performance_count = 0
        quality_count = 0
        dependency_count = 0
        github_issues_count = 0   # new counter for GitHub issues

        # Process AI issues
        for issue_data in issues:
            severity = issue_data.get('severity', 'info')
            category = issue_data.get('category', 'quality')

            if severity == 'critical':
                critical_count += 1
            elif severity == 'warning':
                warning_count += 1
            else:
                info_count += 1

            if category == 'security':
                security_count += 1
            elif category == 'performance':
                performance_count += 1
            elif category == 'dependency':
                dependency_count += 1
            else:
                quality_count += 1

            ScanIssue.objects.create(
                scan=scan,
                title=issue_data.get('title', ''),
                description=issue_data.get('description', ''),
                severity=severity,
                category=category,
                file_path=issue_data.get('file_path'),
                line_number=issue_data.get('line_number'),
                code_snippet=issue_data.get('code_snippet'),
                suggestion=issue_data.get('suggestion', ''),
            )

        # ----- Fetch GitHub issues -----
        github_issues, gh_error = fetch_repo_issues(repository)
        if not gh_error and github_issues:
            for gh_issue in github_issues:
                # Convert GitHub issue to a ScanIssue
                ScanIssue.objects.create(
                    scan=scan,
                    title=gh_issue['title'],
                    description=gh_issue.get('body') or '',   # ensure no None
                    severity='info',           # treat as informational
                    category='github',          # new category
                    file_path=None,
                    line_number=None,
                    code_snippet=None,
                    suggestion='',              # no automatic suggestion
                )
                github_issues_count += 1

        # Update scan totals
        total_issues = len(issues) + github_issues_count

        scan.status = 'completed'
        scan.total_files_scanned = scan_result.get('total_files_scanned', 0)
        scan.total_issues = total_issues
        scan.critical_count = critical_count
        scan.warning_count = warning_count
        scan.info_count = info_count + github_issues_count   # GitHub issues add to info count
        scan.security_count = security_count
        scan.performance_count = performance_count
        scan.quality_count = quality_count
        scan.dependency_count = dependency_count
        # Optionally add a dedicated field if you add it to the model:
        # scan.github_issues_count = github_issues_count
        scan.ai_summary = scan_result.get('summary', '')
        scan.save()

        # ----- Notifications (based only on AI issues) -----
        if security_count > 0:
            Notification.objects.create(
                user=request.user,
                title=f'Security vulnerabilities found in {repository.name}',
                message=f'Repo scan found {security_count} security issue(s) and {critical_count} critical issue(s) across {scan.total_files_scanned} files in "{repository.full_name}".',
                type='critical',
                source='scan',
                source_id=scan.id
            )
        elif critical_count > 0:
            Notification.objects.create(
                user=request.user,
                title=f'Critical issues found in {repository.name}',
                message=f'Repo scan found {critical_count} critical issue(s) across {scan.total_files_scanned} files in "{repository.full_name}".',
                type='critical',
                source='scan',
                source_id=scan.id
            )
        else:
            Notification.objects.create(
                user=request.user,
                title=f'Scan completed for {repository.name}',
                message=f'Repo scan completed successfully — {total_issues} issue(s) found across {scan.total_files_scanned} files.',
                type='success',
                source='scan',
                source_id=scan.id
            )

        return Response({
            'message': 'Repository scan completed successfully',
            'scan': RepoScanSerializer(scan).data
        }, status=status.HTTP_201_CREATED)

    return Response({
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_scans(request):
    repository_id = request.query_params.get('repository_id')

    scans = RepoScan.objects.filter(
        repository__owner=request.user
    )

    if repository_id:
        scans = scans.filter(repository_id=repository_id)

    serializer = RepoScanSerializer(scans, many=True)

    # Return IDs of repos that already have a completed scan
    scanned_repo_ids = list(
        RepoScan.objects.filter(
            repository__owner=request.user,
            status='completed'
        ).values_list('repository_id', flat=True).distinct()
    )

    return Response({
        'scans': serializer.data,
        'count': scans.count(),
        'scanned_repo_ids': scanned_repo_ids,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scan(request, scan_id):
    try:
        scan = RepoScan.objects.get(
            id=scan_id,
            repository__owner=request.user
        )
        serializer = RepoScanSerializer(scan)
        return Response({
            'scan': serializer.data
        }, status=status.HTTP_200_OK)
    except RepoScan.DoesNotExist:
        return Response({
            'error': 'Scan not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scan(request, scan_id):
    try:
        scan = RepoScan.objects.get(
            id=scan_id,
            repository__owner=request.user
        )
        scan.delete()
        return Response({
            'message': 'Scan deleted successfully'
        }, status=status.HTTP_200_OK)
    except RepoScan.DoesNotExist:
        return Response({
            'error': 'Scan not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scan_stats(request):
    repository_id = request.query_params.get('repository_id')

    scans = RepoScan.objects.filter(
        repository__owner=request.user,
        status='completed'
    )

    if repository_id:
        scans = scans.filter(repository_id=repository_id)

    total_scans = scans.count()
    total_issues = sum(s.total_issues for s in scans)
    total_critical = sum(s.critical_count for s in scans)
    total_security = sum(s.security_count for s in scans)
    total_performance = sum(s.performance_count for s in scans)

    return Response({
        'stats': {
            'total_scans': total_scans,
            'total_issues': total_issues,
            'critical': total_critical,
            'security': total_security,
            'performance': total_performance,
        }
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def re_scan(request, scan_id):
    """
    Re-runs the full scan (Gemini AI + GitHub issues) on an already-scanned repo.
    Deletes old issues and updates the existing scan record in place.
    Does NOT create a new RepoScan entry.
    """
    try:
        scan = RepoScan.objects.get(
            id=scan_id,
            repository__owner=request.user
        )
    except RepoScan.DoesNotExist:
        return Response({
            'error': 'Scan not found'
        }, status=status.HTTP_404_NOT_FOUND)

    repository = scan.repository
    branch = scan.branch or 'main'

    # Mark as scanning and clear old data
    scan.status = 'scanning'
    scan.error_message = None
    scan.save()

    # Delete old issues
    scan.issues.all().delete()

    # Re-run AI scan
    scan_result, error = scan_repository_with_gemini(repository, branch)

    if error:
        scan.status = 'failed'
        scan.error_message = error
        scan.save()
        return Response({
            'error': f'Scan failed: {error}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    issues = scan_result.get('issues', [])
    critical_count = 0
    warning_count = 0
    info_count = 0
    security_count = 0
    performance_count = 0
    quality_count = 0
    dependency_count = 0
    github_issues_count = 0

    for issue_data in issues:
        severity = issue_data.get('severity', 'info')
        category = issue_data.get('category', 'quality')

        if severity == 'critical':
            critical_count += 1
        elif severity == 'warning':
            warning_count += 1
        else:
            info_count += 1

        if category == 'security':
            security_count += 1
        elif category == 'performance':
            performance_count += 1
        elif category == 'dependency':
            dependency_count += 1
        else:
            quality_count += 1

        ScanIssue.objects.create(
            scan=scan,
            title=issue_data.get('title', ''),
            description=issue_data.get('description', ''),
            severity=severity,
            category=category,
            file_path=issue_data.get('file_path'),
            line_number=issue_data.get('line_number'),
            code_snippet=issue_data.get('code_snippet'),
            suggestion=issue_data.get('suggestion', ''),
        )

    # Re-fetch GitHub issues
    github_issues, gh_error = fetch_repo_issues(repository)
    if not gh_error and github_issues:
        for gh_issue in github_issues:
            ScanIssue.objects.create(
                scan=scan,
                title=gh_issue['title'],
                description=gh_issue.get('body') or '',
                severity='info',
                category='github',
                file_path=None,
                line_number=None,
                code_snippet=None,
                suggestion='',
            )
            github_issues_count += 1

    total_issues = len(issues) + github_issues_count

    scan.status = 'completed'
    scan.total_files_scanned = scan_result.get('total_files_scanned', 0)
    scan.total_issues = total_issues
    scan.critical_count = critical_count
    scan.warning_count = warning_count
    scan.info_count = info_count + github_issues_count
    scan.security_count = security_count
    scan.performance_count = performance_count
    scan.quality_count = quality_count
    scan.dependency_count = dependency_count
    scan.ai_summary = scan_result.get('summary', '')
    scan.save()

    # Notification
    if security_count > 0:
        Notification.objects.create(
            user=request.user,
            title=f'Re-scan: Security issues in {repository.name}',
            message=f'Re-scan found {security_count} security issue(s) and {critical_count} critical issue(s) in "{repository.full_name}".',
            type='critical',
            source='scan',
            source_id=scan.id
        )
    elif critical_count > 0:
        Notification.objects.create(
            user=request.user,
            title=f'Re-scan: Critical issues in {repository.name}',
            message=f'Re-scan found {critical_count} critical issue(s) in "{repository.full_name}".',
            type='critical',
            source='scan',
            source_id=scan.id
        )
    else:
        Notification.objects.create(
            user=request.user,
            title=f'Re-scan completed for {repository.name}',
            message=f'Re-scan completed — {total_issues} issue(s) found across {scan.total_files_scanned} files.',
            type='success',
            source='scan',
            source_id=scan.id
        )

    return Response({
        'message': 'Re-scan completed successfully',
        'scan': RepoScanSerializer(scan).data
    }, status=status.HTTP_200_OK)