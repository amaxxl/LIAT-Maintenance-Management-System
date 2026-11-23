"""Server-side authorisation and transactional maintenance workflow operations."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from django.db.models import Q
from django.contrib.auth.models import User

from .models import (
    MaintenanceRequest as R, StatusHistory, AssignmentHistory, WorkLog,
    Profile, CoordinatorScope, GroupMembership, TechnicianCompetency, MaintenanceGroup,
    DueDateHistory,
)


def role(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied('An active LIAT account is required')
    try:
        stored = user.liat_profile.role
    except Profile.DoesNotExist:
        raise PermissionDenied('No LIAT role assigned')
    # Backwards compatibility for accounts in a database created with Stage 2.
    return Profile.REQUESTER if stored == Profile.EMPLOYEE else stored


def scope_groups(user):
    """Group IDs a coordinator is authorised to administer."""
    # Administrator oversight is read-only; coordinator scopes never include admins.
    if role(user) == Profile.COORDINATOR:
        return CoordinatorScope.objects.filter(coordinator=user).values_list('group_id', flat=True)
    return MaintenanceGroup.objects.none().values_list('id', flat=True)


def visible_requests(user):
    """One shared intake queue: unassigned faults visible to all active coordinators.

    After triage, only coordinators scoped to the chosen group can view/action it.
    The academy administrator has read-only oversight of requests and reports;
    only scoped coordinators may perform maintenance workflow actions.
    """
    r = role(user)
    qs = R.objects.all()
    if r == Profile.ADMIN:
        return qs
    if r == Profile.REQUESTER:
        return qs.filter(reporter=user)
    if r == Profile.TECHNICIAN:
        return qs.filter(technician=user)
    if r == Profile.COORDINATOR:
        return qs.filter(Q(group_id__in=scope_groups(user)) | Q(
            group__isnull=True, status__in=[R.SUBMITTED, R.UNDER_REVIEW]
        ))
    return qs.none()


def can_view(user, request):
    return visible_requests(user).filter(pk=request.pk).exists()


def coordinator_allowed(user, group):
    r = role(user)
    return r == Profile.COORDINATOR and CoordinatorScope.objects.filter(
        coordinator=user, group=group
    ).exists()


def can_manage_request(user, request):
    """Prevents re-routing a different coordinator's already-owned request."""
    r = role(user)
    return r == Profile.COORDINATOR and (
        request.group_id is None or coordinator_allowed(user, request.group)
    )


def eligible_technicians(group, category, problem_type):
    """Candidates are active technicians in the group with matching active competence."""
    return User.objects.filter(
        is_active=True,
        liat_profile__role=Profile.TECHNICIAN,
        maintenance_memberships__group=group,
        maintenance_memberships__active=True,
        competencies__category=category,
        competencies__problem_type=problem_type,
        competencies__active=True,
    ).distinct().order_by('username')


def allowed_actions(user, request):
    r = role(user)
    if r == Profile.TECHNICIAN and request.technician_id == user.id:
        if request.status == R.ASSIGNED:
            return [('start', 'Start work')]
        if request.status == R.IN_PROGRESS:
            return [('complete', 'Complete work')]
    if r == Profile.COORDINATOR and can_manage_request(user, request):
        if request.status == R.SUBMITTED:
            return [('review', 'Review request'), ('reject', 'Reject request')]
        if request.status == R.UNDER_REVIEW:
            return [('assign', 'Assign technician'), ('set_due', 'Set or update due date'),
                    ('reject', 'Reject request')]
        if request.status in (R.ASSIGNED, R.IN_PROGRESS):
            return [('assign', 'Reassign technician'), ('set_due', 'Set or update due date')]
        if request.status == R.COMPLETED:
            return [('close', 'Approve and close'), ('return', 'Return for correction'),
                    ('assign', 'Reassign for correction'), ('set_due', 'Set or update due date')]
    return []


@transaction.atomic
def perform_action(pk, actor, action, reason='', group=None, technician=None, due_at=None):
    """Enforce each permitted transition and write its history atomically."""
    request = R.objects.select_for_update().select_related(
        'equipment__category', 'problem_type', 'group'
    ).get(pk=pk)
    actor_role = role(actor)
    old = request.status
    reason = (reason or '').strip()

    if action == 'set_due':
        if old not in (R.UNDER_REVIEW, R.ASSIGNED, R.IN_PROGRESS, R.COMPLETED):
            raise PermissionDenied('Due dates cannot be changed in this request status')
        if actor_role != Profile.COORDINATOR or not can_manage_request(actor, request):
            raise PermissionDenied('Only a responsible maintenance coordinator can change due dates')
        if not reason:
            raise ValidationError('Explain why the due date is being changed')
        if due_at is not None:
            if not isinstance(due_at, datetime) or timezone.is_naive(due_at):
                raise ValidationError('Supply a valid timezone-aware due date')
            if due_at <= timezone.now():
                raise ValidationError('The due date must be in the future')
        if request.due_at == due_at:
            raise ValidationError('Choose a different due date or clear the existing date')
        old_due_at = request.due_at
        request.due_at = due_at
        request.save()
        DueDateHistory.objects.create(
            request=request, actor=actor, old_due_at=old_due_at,
            new_due_at=due_at, reason=reason,
        )
        # A deadline edit does not change the request's lifecycle state.
        return request

    if action == 'review':
        if old != R.SUBMITTED or not can_manage_request(actor, request):
            raise PermissionDenied('Not authorised to review this request')
        request.status = R.UNDER_REVIEW

    elif action == 'assign':
        if old not in (R.UNDER_REVIEW, R.ASSIGNED, R.IN_PROGRESS, R.COMPLETED):
            raise ValidationError('The request cannot be assigned in this status')
        if not can_manage_request(actor, request):
            raise PermissionDenied('You cannot reassign work owned by another group')
        if not group or not technician:
            raise ValidationError('Select a maintenance group and technician')
        if not coordinator_allowed(actor, group):
            raise PermissionDenied('Coordinator not authorised for the selected group')
        if not eligible_technicians(group, request.equipment.category, request.problem_type).filter(pk=technician.pk).exists():
            raise ValidationError('Technician is not active/eligible for this maintenance group, equipment category and problem type')
        if request.group_id == group.pk and request.technician_id == technician.pk:
            raise ValidationError('The selected technician is already assigned')
        if not reason:
            raise ValidationError('An assignment or reassignment reason is required')
        AssignmentHistory.objects.create(
            request=request, actor=actor,
            old_group=request.group, new_group=group,
            old_technician=request.technician, new_technician=technician,
            reason=reason,
        )
        request.group = group
        request.technician = technician
        # Reassignment always resets to Assigned, including previously completed work.
        request.status = R.ASSIGNED

    elif action == 'start':
        if actor_role != Profile.TECHNICIAN or request.technician_id != actor.id or old != R.ASSIGNED:
            raise PermissionDenied('Only the assigned technician can start this request')
        request.status = R.IN_PROGRESS

    elif action == 'complete':
        if actor_role != Profile.TECHNICIAN or request.technician_id != actor.id or old != R.IN_PROGRESS:
            raise PermissionDenied('Only the assigned technician can complete in-progress work')
        if not reason:
            raise ValidationError('A resolution note is required before completion')
        WorkLog.objects.create(request=request, author=actor, note=reason)
        request.status = R.COMPLETED

    elif action == 'close':
        if old != R.COMPLETED or not request.group or not coordinator_allowed(actor, request.group):
            raise PermissionDenied('Only the responsible coordinator can approve completed work')
        request.status = R.CLOSED

    elif action == 'return':
        if old != R.COMPLETED or not request.group or not coordinator_allowed(actor, request.group):
            raise PermissionDenied('Only the responsible coordinator can return completed work')
        if not reason:
            raise ValidationError('Explain why the work needs further correction')
        request.status = R.IN_PROGRESS   # Same technician continues.

    elif action == 'reject':
        if old not in (R.SUBMITTED, R.UNDER_REVIEW) or not can_manage_request(actor, request):
            raise PermissionDenied('Only an intake coordinator may reject an unassigned request')
        if not reason:
            raise ValidationError('A rejection reason is required')
        request.status = R.REJECTED
    else:
        raise ValidationError('Unknown action')

    request.save()
    StatusHistory.objects.create(
        request=request, actor=actor, old_status=old,
        new_status=request.status, reason=reason,
    )
    return request
