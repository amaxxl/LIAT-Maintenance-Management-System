"""Role-scoped pages, business-action endpoint, and basic maintenance reports."""
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import MaintenanceRequest as R, MaintenanceGroup, Profile
from .forms import RequestForm, ActionForm
from .services import role, can_view, perform_action, visible_requests, allowed_actions, eligible_technicians, scope_groups


def request_list_for(user):
    return visible_requests(user).select_related('equipment', 'technician', 'group', 'reporter').order_by('-created_at')


def filtered_requests(request, queryset):
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    group = request.GET.get('group', '')
    search = request.GET.get('q', '').strip()[:100]
    if status in dict(R.STATUSES):
        queryset = queryset.filter(status=status)
    if priority in ('low', 'medium', 'high'):
        queryset = queryset.filter(priority=priority)
    if group.isdigit():
        queryset = queryset.filter(group_id=int(group))
    if search:
        queryset = queryset.filter(Q(title__icontains=search) |
                                   Q(equipment__asset_tag__icontains=search) |
                                   Q(description__icontains=search))
    overdue = request.GET.get('overdue', '')
    if overdue == '1':
        queryset = queryset.filter(due_at__lt=timezone.now()).exclude(
            status__in=[R.COMPLETED, R.CLOSED, R.REJECTED])
    return queryset


@login_required
def dashboard(request):
    user_role = role(request.user)
    qs = filtered_requests(request, request_list_for(request.user))
    if user_role == Profile.ADMIN:
        groups = MaintenanceGroup.objects.order_by('name')
    elif user_role == Profile.COORDINATOR:
        groups = MaintenanceGroup.objects.filter(pk__in=scope_groups(request.user)).order_by('name')
    else:
        groups = MaintenanceGroup.objects.none()
    return render(request, 'core/dashboard.html', {
        'requests': qs, 'role': user_role, 'statuses': R.STATUSES,
        'groups': groups, 'filters': request.GET,
        'priority_options': [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        'can_report': user_role == Profile.REQUESTER,
        'can_see_reports': user_role in (Profile.ADMIN, Profile.COORDINATOR),
    })


@login_required
def create_request(request):
    if role(request.user) != Profile.REQUESTER:
        raise PermissionDenied('Only student/employee requesters may report faults')
    form = RequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.reporter = request.user
        obj.save()
        messages.success(request, 'Fault submitted successfully. An intake coordinator will review it.')
        return redirect('request_detail', pk=obj.pk)
    return render(request, 'core/new.html', {'form': form})


def action_form_context(user, item, data=None):
    actions = allowed_actions(user, item)
    if not actions:
        return {'action_form': None, 'eligible_by_group': {}}
    form = ActionForm(data, user=user, item=item) if data is not None else ActionForm(user=user, item=item)
    eligible = {}
    if role(user) in (Profile.ADMIN, Profile.COORDINATOR):
        for group in form.fields['group'].queryset:
            eligible[str(group.pk)] = list(eligible_technicians(
                group, item.equipment.category, item.problem_type
            ).values_list('id', flat=True))
    return {'action_form': form, 'eligible_by_group': eligible}


@login_required
def request_detail(request, pk):
    obj = get_object_or_404(R.objects.select_related(
        'equipment__location__unit', 'group', 'technician', 'reporter', 'problem_type'
    ).prefetch_related('status_history__actor', 'assignment_history', 'work_logs__author'), pk=pk)
    if not can_view(request.user, obj):
        raise PermissionDenied('This request is not visible to your role')
    context = {'item': obj, 'role': role(request.user)}
    context.update(action_form_context(request.user, obj))
    return render(request, 'core/detail.html', context)


@login_required
def request_action(request, pk):
    if request.method != 'POST':
        raise PermissionDenied('POST required')
    obj = get_object_or_404(R, pk=pk)
    if not can_view(request.user, obj):
        raise PermissionDenied('This request is not visible to your role')
    if not allowed_actions(request.user, obj):
        raise PermissionDenied('No work actions allowed for this user')
    form = ActionForm(request.POST, user=request.user, item=obj)
    if not form.is_valid():
        for field, errors in form.errors.items():
            messages.error(request, f'{field}: {", ".join(errors)}')
        return redirect('request_detail', pk=pk)
    action = form.cleaned_data
    try:
        perform_action(
            pk, request.user, action['action'], action['reason'],
            action.get('group'), action.get('technician'),
        )
        messages.success(request, 'Maintenance request updated successfully.')
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    return redirect('request_detail', pk=pk)


@login_required
def reports(request):
    """All numbers are scoped to the viewer's authorised requests."""
    current_role = role(request.user)
    if current_role not in (Profile.COORDINATOR, Profile.ADMIN):
        raise PermissionDenied('Maintenance reports are limited to coordinators and administrators')
    qs = visible_requests(request.user)
    counts = {status: n for status, n in qs.values_list('status').annotate(n=Count('id'))}
    status_rows = [(label, counts.get(value, 0)) for value, label in R.STATUSES]
    overdue_count = qs.filter(due_at__lt=timezone.now()).exclude(
        status__in=[R.COMPLETED, R.CLOSED, R.REJECTED]).count()
    workload = list(qs.exclude(group__isnull=True).exclude(
        status__in=[R.CLOSED, R.REJECTED]
    ).values('group__name').annotate(total=Count('id')).order_by('group__name'))
    return render(request, 'core/reports.html', {
        'status_rows': status_rows, 'total': qs.count(), 'overdue': overdue_count,
        'completed': counts.get(R.COMPLETED, 0) + counts.get(R.CLOSED, 0),
        'workload': workload,
    })
