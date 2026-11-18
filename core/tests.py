"""Workflow, permission, UI validation, history and reporting regression tests."""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from .models import (
    AcademyUnit, Location, EquipmentCategory, ProblemType, Equipment,
    MaintenanceGroup, Profile, GroupMembership, CoordinatorScope,
    TechnicianCompetency, MaintenanceRequest as R, StatusHistory,
    AssignmentHistory, WorkLog,
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
