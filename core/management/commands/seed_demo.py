"""Idempotent fictional dataset for local demonstrations only."""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    AcademyUnit, Location, EquipmentCategory, ProblemType, Equipment,
    MaintenanceGroup, Profile, GroupMembership, CoordinatorScope, TechnicianCompetency,
)


class Command(BaseCommand):
    help = 'Create fictional LIAT users, two teams and assets for local-only development.'

    def handle(self, *args, **kwargs):
        unit, _ = AcademyUnit.objects.get_or_create(name='Computing Department')
        facilities_unit, _ = AcademyUnit.objects.get_or_create(name='Facilities Department')
        room, _ = Location.objects.get_or_create(
            building='LIAT Main Building', room='Lab 204', defaults={'unit': unit})
        cat, _ = EquipmentCategory.objects.get_or_create(name='Computer')
        prob, _ = ProblemType.objects.get_or_create(name='Hardware fault')
        Equipment.objects.get_or_create(asset_tag='LIAT-PC-001', defaults={
            'name': 'Laboratory PC', 'location': room, 'category': cat})
        it_group, _ = MaintenanceGroup.objects.get_or_create(name='IT Maintenance')
        facilities_group, _ = MaintenanceGroup.objects.get_or_create(name='Facilities Maintenance')

        users = [
            ('employee1', Profile.REQUESTER, 'employee'),
            ('employee2', Profile.REQUESTER, 'employee'),
            ('student1', Profile.REQUESTER, 'student'),
            ('technician1', Profile.TECHNICIAN, 'employee'),
            ('technician2', Profile.TECHNICIAN, 'employee'),
            ('coordinator1', Profile.COORDINATOR, 'employee'),
            ('coordinator2', Profile.COORDINATOR, 'employee'),
            ('admin1', Profile.ADMIN, 'employee'),
        ]
        for username, role, account_type in users:
            person, created = User.objects.get_or_create(username=username)
            # Never reset a password on an existing account.
            if created:
                person.set_password('DemoPass123!')
                person.save(update_fields=['password'])
            Profile.objects.update_or_create(
                user=person, defaults={'role': role, 'account_type': account_type, 'unit': unit})
            if role == Profile.ADMIN and (not person.is_staff or not person.is_superuser):
                person.is_staff = True
                person.is_superuser = True
                person.save(update_fields=['is_staff', 'is_superuser'])
            if role == Profile.TECHNICIAN:
                GroupMembership.objects.get_or_create(technician=person, group=it_group)
                TechnicianCompetency.objects.get_or_create(
                    technician=person, category=cat, problem_type=prob)
            if username == 'coordinator1':
                CoordinatorScope.objects.get_or_create(coordinator=person, group=it_group)
            if username == 'coordinator2':
                CoordinatorScope.objects.get_or_create(coordinator=person, group=facilities_group)
        self.stdout.write(self.style.SUCCESS(
            'Fictional local demo users: employee1, employee2, student1, technician1, '
            'technician2, coordinator1, coordinator2, admin1. '
            'New accounts: DemoPass123! (LOCAL ONLY). Existing passwords are not changed.'))
