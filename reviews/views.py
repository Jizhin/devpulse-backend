from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CodeReview, ReviewIssue
from .serializers import CodeReviewSerializer, TriggerReviewSerializer
from .ai_service import analyze_code_with_gemini
from pullrequests.models import PullRequest
from repositories.models import Repository
from notifications.models import Notification
from .provider_utils import fetch_pull_request


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_review(request):
    serializer = TriggerReviewSerializer(data=request.data)
    if serializer.is_valid():
        pull_request_id = serializer.validated_data['pull_request_id']

        try:
            pull_request = PullRequest.objects.get(
                id=pull_request_id,
                repository__owner=request.user
            )
        except PullRequest.DoesNotExist:
            return Response({
                'error': 'Pull request not found'
            }, status=status.HTTP_404_NOT_FOUND)

        existing_review = CodeReview.objects.filter(
            pull_request=pull_request,
            status='completed'
        ).first()

        if existing_review:
            return Response({
                'error': 'This PR has already been reviewed. Use re-review to update the existing review.',
                'review_id': existing_review.id
            }, status=status.HTTP_400_BAD_REQUEST)

        review = CodeReview.objects.create(
            pull_request=pull_request,
            repository=pull_request.repository,
            triggered_by=request.user,
            status='processing'
        )

        ai_result, error = analyze_code_with_gemini(
            pull_request,
            pull_request.repository
        )

        if error:
            review.status = 'failed'
            review.error_message = error
            review.save()
            return Response({
                'error': f'AI review failed: {error}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        issues = ai_result.get('issues', [])
        critical_count = 0
        warning_count = 0
        info_count = 0

        for issue_data in issues:
            severity = issue_data.get('severity', 'info')
            if severity == 'critical':
                critical_count += 1
            elif severity == 'warning':
                warning_count += 1
            else:
                info_count += 1

            ReviewIssue.objects.create(
                review=review,
                title=issue_data.get('title', ''),
                description=issue_data.get('description', ''),
                severity=severity,
                category=issue_data.get('category', 'style'),
                file_name=issue_data.get('file_name'),
                line_number=issue_data.get('line_number'),
                code_snippet=issue_data.get('code_snippet'),
                suggestion=issue_data.get('suggestion', ''),
            )

        review.status = 'completed'
        review.total_issues = len(issues)
        review.critical_count = critical_count
        review.warning_count = warning_count
        review.info_count = info_count
        review.ai_summary = ai_result.get('summary', '')
        review.save()

        if critical_count > 0:
            Notification.objects.create(
                user=request.user,
                title=f'Critical issues found in PR #{pull_request.number}',
                message=f'AI review found {critical_count} critical issue(s) and {warning_count} warning(s) in "{pull_request.title}" — immediate attention required.',
                type='critical',
                source='review',
                source_id=review.id
            )
        elif warning_count > 0:
            Notification.objects.create(
                user=request.user,
                title=f'Warnings found in PR #{pull_request.number}',
                message=f'AI review found {warning_count} warning(s) in "{pull_request.title}".',
                type='warning',
                source='review',
                source_id=review.id
            )
        else:
            Notification.objects.create(
                user=request.user,
                title=f'PR #{pull_request.number} looks clean',
                message=f'AI review completed for "{pull_request.title}" — no critical issues found.',
                type='success',
                source='review',
                source_id=review.id
            )

        return Response({
            'message': 'AI review completed successfully',
            'review': CodeReviewSerializer(review).data
        }, status=status.HTTP_201_CREATED)

    return Response({
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_reviews(request):
    repository_id = request.query_params.get('repository_id')
    pull_request_id = request.query_params.get('pull_request_id')

    reviews = CodeReview.objects.filter(
        repository__owner=request.user
    )

    if repository_id:
        reviews = reviews.filter(repository_id=repository_id)

    if pull_request_id:
        reviews = reviews.filter(pull_request_id=pull_request_id)

    serializer = CodeReviewSerializer(reviews, many=True)

    # Return IDs of PRs that already have a completed review
    reviewed_pr_ids = list(
        CodeReview.objects.filter(
            repository__owner=request.user,
            status='completed'
        ).values_list('pull_request_id', flat=True).distinct()
    )

    return Response({
        'reviews': serializer.data,
        'count': reviews.count(),
        'reviewed_pr_ids': reviewed_pr_ids,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_review(request, review_id):
    try:
        review = CodeReview.objects.get(
            id=review_id,
            repository__owner=request.user
        )
        serializer = CodeReviewSerializer(review)
        return Response({
            'review': serializer.data
        }, status=status.HTTP_200_OK)
    except CodeReview.DoesNotExist:
        return Response({
            'error': 'Review not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_review(request, review_id):
    try:
        review = CodeReview.objects.get(
            id=review_id,
            repository__owner=request.user
        )
        review.delete()
        return Response({
            'message': 'Review deleted successfully'
        }, status=status.HTTP_200_OK)
    except CodeReview.DoesNotExist:
        return Response({
            'error': 'Review not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_review_stats(request):
    repository_id = request.query_params.get('repository_id')

    reviews = CodeReview.objects.filter(
        repository__owner=request.user,
        status='completed'
    )

    if repository_id:
        reviews = reviews.filter(repository_id=repository_id)

    total_reviews = reviews.count()
    total_issues = sum(r.total_issues for r in reviews)
    total_critical = sum(r.critical_count for r in reviews)
    total_warning = sum(r.warning_count for r in reviews)
    total_info = sum(r.info_count for r in reviews)

    return Response({
        'stats': {
            'total_reviews': total_reviews,
            'total_issues': total_issues,
            'critical': total_critical,
            'warning': total_warning,
            'info': total_info,
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def re_review(request, review_id):
    """
    Re-runs AI analysis on an already-reviewed PR.
    Deletes old issues and updates the existing review record in place.
    Does NOT create a new CodeReview entry.
    """
    try:
        review = CodeReview.objects.get(
            id=review_id,
            repository__owner=request.user
        )
    except CodeReview.DoesNotExist:
        return Response({
            'error': 'Review not found'
        }, status=status.HTTP_404_NOT_FOUND)

    pull_request = review.pull_request
    repository = review.repository
    review.status = 'processing'
    review.error_message = None
    review.save()
    review.issues.all().delete()

    # Refresh PR data from provider using the dispatcher
    pr_data, error = fetch_pull_request(repository, pull_request.number)
    if not error and pr_data:
        if repository.provider == 'github':
            pull_request.title = pr_data.get('title', pull_request.title)
            pull_request.description = pr_data.get('body') or ''
            if pr_data.get('merged'):
                pull_request.status = 'merged'
            elif pr_data.get('state') == 'closed':
                pull_request.status = 'closed'
            else:
                pull_request.status = 'open'
        elif repository.provider == 'gitlab':
            pull_request.title = pr_data.get('title', pull_request.title)
            pull_request.description = pr_data.get('description') or ''
            state = pr_data.get('state')
            if state == 'merged':
                pull_request.status = 'merged'
            elif state == 'closed':
                pull_request.status = 'closed'
            else:
                pull_request.status = 'open'
        pull_request.save()

    # Re-run AI
    ai_result, error = analyze_code_with_gemini(pull_request, repository)

    if error:
        review.status = 'failed'
        review.error_message = error
        review.save()
        return Response({
            'error': f'AI review failed: {error}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    issues = ai_result.get('issues', [])
    critical_count = 0
    warning_count = 0
    info_count = 0

    for issue_data in issues:
        severity = issue_data.get('severity', 'info')
        if severity == 'critical':
            critical_count += 1
        elif severity == 'warning':
            warning_count += 1
        else:
            info_count += 1

        ReviewIssue.objects.create(
            review=review,
            title=issue_data.get('title', ''),
            description=issue_data.get('description', ''),
            severity=severity,
            category=issue_data.get('category', 'style'),
            file_name=issue_data.get('file_name'),
            line_number=issue_data.get('line_number'),
            code_snippet=issue_data.get('code_snippet'),
            suggestion=issue_data.get('suggestion', ''),
        )

    review.status = 'completed'
    review.total_issues = len(issues)
    review.critical_count = critical_count
    review.warning_count = warning_count
    review.info_count = info_count
    review.ai_summary = ai_result.get('summary', '')
    review.save()

    # Notification
    if critical_count > 0:
        Notification.objects.create(
            user=request.user,
            title=f'Re-review: Critical issues in PR #{pull_request.number}',
            message=f'Re-review found {critical_count} critical issue(s) in "{pull_request.title}".',
            type='critical',
            source='review',
            source_id=review.id
        )
    elif warning_count > 0:
        Notification.objects.create(
            user=request.user,
            title=f'Re-review: Warnings in PR #{pull_request.number}',
            message=f'Re-review found {warning_count} warning(s) in "{pull_request.title}".',
            type='warning',
            source='review',
            source_id=review.id
        )
    else:
        Notification.objects.create(
            user=request.user,
            title=f'Re-review: PR #{pull_request.number} looks clean',
            message=f'Re-review completed for "{pull_request.title}" — no critical issues found.',
            type='success',
            source='review',
            source_id=review.id
        )

    return Response({
        'message': 'Re-review completed successfully',
        'review': CodeReviewSerializer(review).data
    }, status=status.HTTP_200_OK)