"""Workflow, permission, UI validation, history and reporting regression tests."""
from django.test import TestCase
from datetime import timedelta
from django.utils import timezone
from django.contrib import admin
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from .models import (
    AcademyUnit, Location, EquipmentCategory, ProblemType, Equipment,
    MaintenanceGroup, Profile, GroupMembership, CoordinatorScope,
    TechnicianCompetency, MaintenanceRequest as R, StatusHistory,
    AssignmentHistory, WorkLog, DueDateHistory,
)
from .services import perform_action, can_view, role


class WorkflowTests(TestCase):
    def setUp(self):
        self.unit = AcademyUnit.objects.create(name='IT')
        self.unit2 = AcademyUnit.objects.create(name='Teaching')
        self.loc = Location.objects.create(unit=self.unit, room='101')
        self.loc2 = Location.objects.create(unit=self.unit2, room='202')
        self.cat = EquipmentCategory.objects.create(name='PC')
        self.problem = ProblemType.objects.create(name='Hardware')
        self.asset = Equipment.objects.create(
            asset_tag='PC01', name='PC', category=self.cat, location=self.loc)
        self.group = MaintenanceGroup.objects.create(name='IT service')
        self.other_group = MaintenanceGroup.objects.create(name='Facilities')

        def make(name, user_role, account_type='employee'):
            user = User.objects.create_user(name, password='StrongDemo123!')
            Profile.objects.create(user=user, role=user_role, account_type=account_type, unit=self.unit)
            return user

        self.requester = make('employee', Profile.REQUESTER)
        self.other = make('other', Profile.REQUESTER)
        self.student = make('student', Profile.REQUESTER, 'student')
        self.legacy = make('legacy', Profile.EMPLOYEE)
        self.tech = make('tech', Profile.TECHNICIAN)
        self.tech2 = make('tech2', Profile.TECHNICIAN)
        self.coord = make('coord', Profile.COORDINATOR)
        self.outsider = make('outside', Profile.COORDINATOR)
        self.admin = make('admin', Profile.ADMIN)
        for tech in (self.tech, self.tech2):
            GroupMembership.objects.create(technician=tech, group=self.group)
            TechnicianCompetency.objects.create(
                technician=tech, category=self.cat, problem_type=self.problem)
        CoordinatorScope.objects.create(coordinator=self.coord, group=self.group)
        CoordinatorScope.objects.create(coordinator=self.outsider, group=self.other_group)
        self.req = R.objects.create(equipment=self.asset, reporter=self.requester,
                                    problem_type=self.problem, title='Won\'t start',
                                    description='Black screen')

    def login(self, user):
        self.client.force_login(user)

    def review_assign(self):
        perform_action(self.req.pk, self.coord, 'review', reason='Intake checked')
        perform_action(self.req.pk, self.coord, 'assign', reason='Qualified IT group',
                       group=self.group, technician=self.tech)

    def test_coordinator_can_set_modify_and_clear_due_date_with_audit(self):
        perform_action(self.req.pk, self.coord, 'review')
        initial = timezone.now() + timedelta(days=2)
        updated = timezone.now() + timedelta(days=5)
        perform_action(self.req.pk, self.coord, 'set_due', reason='Repair target', due_at=initial)
        perform_action(self.req.pk, self.coord, 'set_due', reason='Parts delayed', due_at=updated)
        perform_action(self.req.pk, self.coord, 'set_due', reason='No deadline needed', due_at=None)
        self.req.refresh_from_db()
        self.assertIsNone(self.req.due_at)
        rows = list(DueDateHistory.objects.filter(request=self.req).order_by('pk'))
        self.assertEqual(len(rows), 3)
        self.assertIsNone(rows[0].old_due_at)
        self.assertEqual(rows[0].new_due_at, initial)
        self.assertEqual(rows[1].old_due_at, initial)
        self.assertEqual(rows[1].new_due_at, updated)
        self.assertEqual(rows[2].old_due_at, updated)
        self.assertIsNone(rows[2].new_due_at)
        self.assertEqual([x.reason for x in rows], ['Repair target', 'Parts delayed', 'No deadline needed'])
        self.assertEqual(StatusHistory.objects.filter(request=self.req).count(), 1)

    def test_coordinator_due_date_form_and_post(self):
        perform_action(self.req.pk, self.coord, 'review')
        self.login(self.coord)
        detail = self.client.get(reverse('request_detail', args=[self.req.pk]))
        self.assertContains(detail, 'Set or update due date')
        self.assertContains(detail, 'id_due_at')
        future = timezone.localtime(timezone.now() + timedelta(days=2))
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'set_due', 'due_at': future.strftime('%Y-%m-%dT%H:%M'),
            'reason': 'Expected completion time',
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertIsNotNone(self.req.due_at)
        self.assertEqual(DueDateHistory.objects.filter(request=self.req).count(), 1)
        detail = self.client.get(reverse('request_detail', args=[self.req.pk]))
        self.assertContains(detail, 'Due date history')
        self.assertContains(detail, 'Expected completion time')
        self.assertEqual(self.req.status, R.UNDER_REVIEW)

    def test_due_date_updates_are_coordinator_only_and_group_scoped(self):
        perform_action(self.req.pk, self.coord, 'review')
        future = timezone.now() + timedelta(days=2)
        for actor in (self.admin, self.requester, self.tech):
            with self.assertRaises(PermissionDenied):
                perform_action(self.req.pk, actor, 'set_due', reason='Unauthorized', due_at=future)
        self.login(self.admin)
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'set_due', 'reason': 'Denied', 'due_at': '2027-04-01T12:00',
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn('due_at', admin.site._registry[R].get_readonly_fields(None))
        perform_action(self.req.pk, self.coord, 'assign', group=self.group,
                       technician=self.tech, reason='Assign specialist')
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.outsider, 'set_due', reason='Wrong group', due_at=future)
        self.assertEqual(DueDateHistory.objects.filter(request=self.req).count(), 0)
        self.req.refresh_from_db()
        self.assertIsNone(self.req.due_at)

    def test_due_date_rejects_invalid_status_missing_reason_past_or_no_change(self):
        future = timezone.now() + timedelta(days=3)
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.coord, 'set_due', reason='Too early', due_at=future)
        perform_action(self.req.pk, self.coord, 'review')
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'set_due', reason='', due_at=future)
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'set_due', reason='Past deadline',
                           due_at=timezone.now() - timedelta(days=1))
        perform_action(self.req.pk, self.coord, 'set_due', reason='Valid', due_at=future)
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'set_due', reason='No change', due_at=future)
        self.review_assign_after_review()
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.tech, 'complete', reason='Repaired')
        perform_action(self.req.pk, self.coord, 'close')
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.coord, 'set_due', reason='Closed', due_at=None)
        self.assertEqual(DueDateHistory.objects.filter(request=self.req).count(), 1)

    def review_assign_after_review(self):
        perform_action(self.req.pk, self.coord, 'assign', group=self.group,
                       technician=self.tech, reason='Qualified group')

    def test_due_date_overdue_count_excludes_final_states(self):
        self.review_assign()
        future = timezone.now() + timedelta(days=1)
        perform_action(self.req.pk, self.coord, 'set_due', reason='Repair by tomorrow', due_at=future)
        self.login(self.coord)
        self.assertEqual(self.client.get(reverse('reports')).context['overdue'], 0)
        R.objects.filter(pk=self.req.pk).update(due_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.client.get(reverse('reports')).context['overdue'], 1)
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.tech, 'complete', reason='Done')
        self.assertEqual(self.client.get(reverse('reports')).context['overdue'], 0)

    def test_administrator_can_view_and_report_but_has_no_workflow_actions(self):
        # Oversight remains visible, but action controls and direct POSTs are denied.
        self.assertTrue(can_view(self.admin, self.req))
        self.login(self.admin)
        detail = self.client.get(reverse('request_detail', args=[self.req.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertIsNone(detail.context['action_form'])
        self.assertNotContains(detail, 'Update maintenance work')
        self.assertEqual(self.client.get(reverse('reports')).status_code, 200)
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'review', 'reason': 'Attempt to bypass UI'
        })
        self.assertEqual(response.status_code, 403)
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.admin, 'review', reason='Direct call')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.SUBMITTED)
        self.assertFalse(StatusHistory.objects.filter(request=self.req).exists())

    def test_administrator_cannot_assign_return_close_or_reject(self):
        # Security checks must be enforced by services, not just hidden buttons.
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.admin, 'reject', reason='Not authorised')
        self.review_assign()
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.admin, 'assign', reason='Not authorised',
                           group=self.group, technician=self.tech2)
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.tech, 'complete', reason='Repaired')
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.admin, 'return', reason='Not authorised')
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.admin, 'close', reason='Not authorised')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.COMPLETED)
        self.assertEqual(self.req.technician, self.tech)
        self.assertEqual(StatusHistory.objects.filter(request=self.req).count(), 4)
        self.assertEqual(AssignmentHistory.objects.filter(request=self.req).count(), 1)
        # Responsible coordinator remains able to complete the workflow.
        perform_action(self.req.pk, self.coord, 'close', reason='Verified repair')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.CLOSED)

    def test_snapshot_survives_equipment_move_and_unit_rename(self):
        self.asset.location = self.loc2
        self.asset.save()
        self.unit.name = 'Renamed unit'
        self.unit.save()
        self.req.refresh_from_db()
        self.assertEqual(self.req.reported_unit_name, 'IT')
        self.assertEqual(self.req.reported_room_label, '101')
        self.assertEqual(self.req.reported_location_id, self.loc.id)
        self.assertEqual(self.req.asset_tag_at_submission, 'PC01')
        self.assertEqual(self.req.equipment.location_id, self.loc2.id)

    def test_snapshot_cannot_be_mutated_on_model_save(self):
        self.req.reported_room_label = 'NOT the original room'
        with self.assertRaises(ValidationError):
            self.req.save()

    def test_submitted_request_identity_cannot_be_changed_on_model_save(self):
        other_equipment = Equipment.objects.create(
            asset_tag='PC99', name='Replacement', category=self.cat, location=self.loc2)
        another_problem = ProblemType.objects.create(name='Software')
        for field, replacement in (
            ('reporter', self.other),
            ('equipment', other_equipment),
            ('problem_type', another_problem),
        ):
            current = R.objects.get(pk=self.req.pk)
            setattr(current, field, replacement)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                current.save()
        self.req.refresh_from_db()
        self.assertEqual(self.req.reporter, self.requester)
        self.assertEqual(self.req.equipment, self.asset)
        self.assertEqual(self.req.problem_type, self.problem)

    def test_request_identity_remains_immutable_after_assignment(self):
        self.review_assign()
        current = R.objects.get(pk=self.req.pk)
        current.reporter = self.other
        with self.assertRaises(ValidationError):
            current.save()
        current.refresh_from_db()
        self.assertEqual(current.status, R.ASSIGNED)
        self.assertEqual(current.reporter, self.requester)
        self.assertEqual(AssignmentHistory.objects.filter(request=current).count(), 1)

    def test_django_admin_request_pages_are_view_only(self):
        # Even a Django superuser cannot bypass audited request creation,
        # transitions, or historical identity via the Admin interface.
        superuser = User.objects.create_superuser(
            'reviewer', 'reviewer@example.invalid', 'LocalTest123!')
        self.client.force_login(superuser)
        model_admin = admin.site._registry[R]
        for field in ('reporter', 'equipment', 'problem_type', 'status',
                      'group', 'technician', 'due_at'):
            self.assertIn(field, model_admin.get_readonly_fields(None, self.req))
        change_url = reverse('admin:core_maintenancerequest_change', args=[self.req.pk])
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.post(change_url, {
            'reporter': self.other.pk,
            'equipment': self.asset.pk,
            'problem_type': self.problem.pk,
        }).status_code, 403)
        self.assertEqual(self.client.get(reverse(
            'admin:core_maintenancerequest_add')).status_code, 403)
        self.assertEqual(self.client.post(reverse(
            'admin:core_maintenancerequest_delete', args=[self.req.pk])).status_code, 403)
        self.req.refresh_from_db()
        self.assertEqual(self.req.reporter, self.requester)
        self.assertTrue(R.objects.filter(pk=self.req.pk).exists())

    def test_requester_student_and_legacy_employee_submit(self):
        self.assertEqual(role(self.legacy), Profile.REQUESTER)
        for person in (self.student, self.legacy):
            self.login(person)
            response = self.client.post(reverse('create_request'), {
                'equipment': self.asset.pk, 'problem_type': self.problem.pk,
                'title': 'Broken PC', 'description': 'Test fault', 'priority': 'high'
            })
            self.assertEqual(response.status_code, 302)
            self.assertTrue(R.objects.filter(reporter=person, title='Broken PC').exists())

    def test_dashboard_equipment_filter_and_dropdowns(self):
        another_asset = Equipment.objects.create(
            asset_tag='PC02', name='Other PC', category=self.cat, location=self.loc)
        other_request = R.objects.create(
            equipment=another_asset, reporter=self.requester,
            problem_type=self.problem, title='PC02 fault', description='Other issue',
            priority='high')
        self.login(self.requester)
        page = self.client.get(reverse('dashboard'), {'equipment': str(self.asset.pk)})
        self.assertEqual(list(page.context['requests']), [self.req])
        self.assertContains(page, 'id="equipment"')
        self.assertContains(page, 'PC01')
        self.assertContains(page, 'PC02')
        page = self.client.get(reverse('dashboard'), {'equipment': str(another_asset.pk)})
        self.assertEqual(list(page.context['requests']), [other_request])

    def test_dashboard_group_status_priority_combined(self):
        self.review_assign()
        other_request = R.objects.create(
            equipment=self.asset, reporter=self.requester,
            problem_type=self.problem, title='Second issue',
            description='Not reviewed yet', priority='high')
        self.login(self.coord)
        page = self.client.get(reverse('dashboard'), {
            'group': str(self.group.pk), 'status': R.ASSIGNED,
            'priority': 'medium', 'equipment': str(self.asset.pk),
        })
        self.assertEqual(list(page.context['requests']), [self.req])
        self.assertContains(page, 'IT service')
        page = self.client.get(reverse('dashboard'), {'group': str(self.group.pk), 'priority': 'high'})
        self.assertEqual(list(page.context['requests']), [])
        page = self.client.get(reverse('dashboard'), {'status': R.SUBMITTED, 'priority': 'high'})
        self.assertEqual(list(page.context['requests']), [other_request])

    def test_dashboard_submitted_date_range_inclusive(self):
        old_request = R.objects.create(
            equipment=self.asset, reporter=self.requester,
            problem_type=self.problem, title='Old fault', description='Earlier fault')
        R.objects.filter(pk=old_request.pk).update(created_at=timezone.now() - timedelta(days=10))
        self.req.refresh_from_db()
        old_request.refresh_from_db()
        today = timezone.localtime(self.req.created_at).date().isoformat()
        earlier = timezone.localtime(old_request.created_at).date().isoformat()
        self.login(self.requester)
        page = self.client.get(reverse('dashboard'), {'date_from': today, 'date_to': today})
        self.assertEqual(list(page.context['requests']), [self.req])
        self.assertContains(page, 'id="date_from"')
        self.assertContains(page, 'id="date_to"')
        page = self.client.get(reverse('dashboard'), {'date_to': earlier})
        self.assertEqual(list(page.context['requests']), [old_request])
        page = self.client.get(reverse('dashboard'), {'date_from': earlier, 'date_to': today})
        self.assertEqual({x.pk for x in page.context['requests']}, {self.req.pk, old_request.pk})

    def test_dashboard_filter_does_not_expose_other_requesters_equipment(self):
        another_asset = Equipment.objects.create(
            asset_tag='PRIVATE-PC', name='Private PC', category=self.cat, location=self.loc)
        private_request = R.objects.create(
            equipment=another_asset, reporter=self.other,
            problem_type=self.problem, title='Private work', description='Private details')
        self.login(self.requester)
        page = self.client.get(reverse('dashboard'))
        self.assertNotContains(page, 'PRIVATE-PC')
        self.assertNotContains(page, 'Private work')
        self.assertEqual([e.pk for e in page.context['equipment_choices']], [self.asset.pk])
        page = self.client.get(reverse('dashboard'), {
            'equipment': str(another_asset.pk), 'date_from': '2020-01-01',
        })
        self.assertEqual(list(page.context['requests']), [])
        self.assertNotContains(page, 'PRIVATE-PC')
        self.assertNotContains(page, 'Private work')
        self.assertEqual(private_request.reporter_id, self.other.pk)

    def test_other_requester_direct_url_and_dashboard_private(self):
        self.login(self.other)
        response = self.client.get(reverse('request_detail', args=[self.req.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Won\'t start')
        self.assertFalse(can_view(self.other, self.req))

    def test_requester_cannot_call_coordinator_action(self):
        self.login(self.requester)
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'review', 'reason': 'Try to review'
        })
        self.assertEqual(response.status_code, 403)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.SUBMITTED)

    def test_unassigned_requests_visible_to_both_intake_coordinators(self):
        self.assertTrue(can_view(self.coord, self.req))
        self.assertTrue(can_view(self.outsider, self.req))
        self.review_assign()
        self.assertFalse(can_view(self.outsider, self.req))
        self.assertTrue(can_view(self.coord, self.req))

    def test_out_of_scope_coordinator_cannot_reassign_group(self):
        self.review_assign()
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.outsider, 'assign', reason='Not my group',
                           group=self.other_group, technician=self.tech)
        self.assertEqual(AssignmentHistory.objects.filter(request=self.req).count(), 1)

    def test_group_member_and_competency_required(self):
        perform_action(self.req.pk, self.coord, 'review')
        TechnicianCompetency.objects.filter(technician=self.tech).update(active=False)
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'assign', reason='Test',
                           group=self.group, technician=self.tech)
        TechnicianCompetency.objects.filter(technician=self.tech).update(active=True)
        GroupMembership.objects.filter(technician=self.tech).update(active=False)
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'assign', reason='Test',
                           group=self.group, technician=self.tech)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.UNDER_REVIEW)
        self.assertEqual(AssignmentHistory.objects.filter(request=self.req).count(), 0)

    def test_technician_cannot_view_or_modify_unassigned_work(self):
        self.login(self.tech2)
        response = self.client.get(reverse('request_detail', args=[self.req.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'start', 'reason': 'Unauthorized'
        })
        self.assertEqual(response.status_code, 403)
        self.review_assign()
        self.login(self.tech2)
        self.assertEqual(self.client.get(reverse('request_detail', args=[self.req.pk])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.tech2, 'start')

    def test_completion_requires_resolution_note(self):
        self.review_assign()
        perform_action(self.req.pk, self.tech, 'start')
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.tech, 'complete', reason='  ')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.IN_PROGRESS)
        self.assertEqual(WorkLog.objects.filter(request=self.req).count(), 0)

    def test_reassignment_history_and_reset_to_assigned(self):
        self.review_assign()
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.coord, 'assign', group=self.group,
                       technician=self.tech2, reason='Technician unavailable')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.ASSIGNED)
        self.assertEqual(self.req.technician, self.tech2)
        events = list(AssignmentHistory.objects.filter(request=self.req).order_by('pk'))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].old_technician, self.tech)
        self.assertEqual(events[1].new_technician, self.tech2)
        self.assertEqual(events[1].reason, 'Technician unavailable')
        self.assertFalse(can_view(self.tech, self.req))
        self.assertTrue(can_view(self.tech2, self.req))

    def test_return_for_correction_by_same_technician(self):
        self.review_assign()
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.tech, 'complete', reason='Tested repair')
        perform_action(self.req.pk, self.coord, 'return', reason='More testing needed')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.IN_PROGRESS)
        self.assertEqual(self.req.technician, self.tech)
        self.assertEqual(WorkLog.objects.filter(request=self.req).count(), 1)
        perform_action(self.req.pk, self.tech, 'complete', reason='Final check passed')
        perform_action(self.req.pk, self.coord, 'close', reason='Accepted')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.CLOSED)
        self.assertEqual(StatusHistory.objects.filter(request=self.req).count(), 7)

    def test_reassignment_after_completion_resets_to_assigned(self):
        self.review_assign()
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.tech, 'complete', reason='Initial repair')
        perform_action(self.req.pk, self.coord, 'assign', reason='Different specialist required',
                       group=self.group, technician=self.tech2)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.ASSIGNED)
        self.assertEqual(self.req.technician_id, self.tech2.pk)

    def test_role_action_options_are_status_restricted(self):
        self.login(self.coord)
        response = self.client.get(reverse('request_detail', args=[self.req.pk]))
        self.assertContains(response, 'Review request')
        self.assertNotContains(response, 'Approve and close')
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'close', 'reason': 'Try illegal transition'
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.SUBMITTED)

    def test_validated_dropdown_rejects_ineligible_technician_id(self):
        perform_action(self.req.pk, self.coord, 'review')
        TechnicianCompetency.objects.filter(technician=self.tech2).update(active=False)
        self.login(self.coord)
        response = self.client.post(reverse('request_action', args=[self.req.pk]), {
            'action': 'assign', 'group': str(self.group.pk),
            'technician': str(self.tech2.pk), 'reason': 'Attempt invalid selection',
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.UNDER_REVIEW)
        self.assertEqual(AssignmentHistory.objects.filter(request=self.req).count(), 0)

    def test_workflow_direct_employee_cannot_assign(self):
        perform_action(self.req.pk, self.coord, 'review')
        with self.assertRaises(PermissionDenied):
            perform_action(self.req.pk, self.requester, 'assign', group=self.group,
                           technician=self.tech, reason='Denied')

    def test_reports_scope_and_counts(self):
        self.review_assign()
        self.login(self.coord)
        response = self.client.get(reverse('reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'IT service')
        self.assertContains(response, 'Active workload')
        self.login(self.requester)
        self.assertEqual(self.client.get(reverse('reports')).status_code, 403)
        self.login(self.outsider)
        response = self.client.get(reverse('reports'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'IT service')

    def test_closed_request_rejects_further_actions(self):
        self.review_assign()
        perform_action(self.req.pk, self.tech, 'start')
        perform_action(self.req.pk, self.tech, 'complete', reason='Done')
        perform_action(self.req.pk, self.coord, 'close')
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'assign', group=self.group,
                           technician=self.tech2, reason='Invalid reassignment')
        self.assertEqual(StatusHistory.objects.filter(request=self.req).count(), 5)

    def test_rejection_requires_reason_and_preserves_history(self):
        with self.assertRaises(ValidationError):
            perform_action(self.req.pk, self.coord, 'reject', reason='')
        perform_action(self.req.pk, self.coord, 'reject', reason='Duplicate ticket')
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, R.REJECTED)
        self.assertEqual(StatusHistory.objects.get(request=self.req).reason, 'Duplicate ticket')
