from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
class AcademyUnit(models.Model):
 name=models.CharField(max_length=120,unique=True)
 def __str__(self):return self.name
class Location(models.Model):
 unit=models.ForeignKey(AcademyUnit,on_delete=models.PROTECT)
 building=models.CharField(max_length=80,default='LIAT Main Building')
 room=models.CharField(max_length=80)
 class Meta: unique_together=[('building','room')]
 def __str__(self):return f'{self.building} / {self.room} ({self.unit.name})'
class EquipmentCategory(models.Model):
 name=models.CharField(max_length=100,unique=True)
 def __str__(self):return self.name
class ProblemType(models.Model):
 name=models.CharField(max_length=100,unique=True)
 def __str__(self):return self.name
class Equipment(models.Model):
 asset_tag=models.CharField(max_length=50,unique=True)
 name=models.CharField(max_length=130)
 category=models.ForeignKey(EquipmentCategory,on_delete=models.PROTECT)
 location=models.ForeignKey(Location,on_delete=models.PROTECT)
 active=models.BooleanField(default=True)
 def __str__(self):return f'{self.asset_tag} — {self.name}'
 # Physical unit is derived from location.unit; do not duplicate Equipment.unit_id.
class MaintenanceGroup(models.Model):
 name=models.CharField(max_length=100,unique=True)
 def __str__(self):return self.name
class Profile(models.Model):
 REQUESTER='requester'; EMPLOYEE='employee'; TECHNICIAN='technician'; COORDINATOR='coordinator'; ADMIN='admin'
 ROLE_CHOICES=[(REQUESTER,'Requester'),(EMPLOYEE,'Requester (legacy)'),(TECHNICIAN,'Technician'),(COORDINATOR,'Coordinator'),(ADMIN,'Administrator')]
 ACCOUNT_TYPES=[('student','Student'),('employee','Employee')]
 user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='liat_profile')
 role=models.CharField(max_length=15,choices=ROLE_CHOICES,default=REQUESTER)
 account_type=models.CharField(max_length=12,choices=ACCOUNT_TYPES,default='employee',help_text='Student or employee; does not change the requester permissions')
 unit=models.ForeignKey(AcademyUnit,on_delete=models.PROTECT,null=True,blank=True)
 def __str__(self):return f'{self.user.username} ({self.role})'
class GroupMembership(models.Model):
 technician=models.ForeignKey(User,on_delete=models.CASCADE,related_name='maintenance_memberships')
 group=models.ForeignKey(MaintenanceGroup,on_delete=models.PROTECT)
 active=models.BooleanField(default=True)
 class Meta: unique_together=[('technician','group')]
class CoordinatorScope(models.Model):
 coordinator=models.ForeignKey(User,on_delete=models.CASCADE,related_name='coordinator_scopes')
 group=models.ForeignKey(MaintenanceGroup,on_delete=models.PROTECT)
 class Meta: unique_together=[('coordinator','group')]
class TechnicianCompetency(models.Model):
 technician=models.ForeignKey(User,on_delete=models.CASCADE,related_name='competencies')
 category=models.ForeignKey(EquipmentCategory,on_delete=models.PROTECT)
 problem_type=models.ForeignKey(ProblemType,on_delete=models.PROTECT)
 active=models.BooleanField(default=True)
 class Meta: unique_together=[('technician','category','problem_type')]
class MaintenanceRequest(models.Model):
 SUBMITTED='submitted'; UNDER_REVIEW='under_review'; ASSIGNED='assigned'; IN_PROGRESS='in_progress'; COMPLETED='completed'; CLOSED='closed'; REJECTED='rejected'
 STATUSES=[(x,x.replace('_',' ').title()) for x in [SUBMITTED,UNDER_REVIEW,ASSIGNED,IN_PROGRESS,COMPLETED,CLOSED,REJECTED]]
 equipment=models.ForeignKey(Equipment,on_delete=models.PROTECT)
 reporter=models.ForeignKey(User,on_delete=models.PROTECT,related_name='reported_requests')
 problem_type=models.ForeignKey(ProblemType,on_delete=models.PROTECT)
 title=models.CharField(max_length=150)
 description=models.TextField()
 priority=models.CharField(max_length=10,choices=[('low','Low'),('medium','Medium'),('high','High')],default='medium')
 status=models.CharField(max_length=20,choices=STATUSES,default=SUBMITTED)
 group=models.ForeignKey(MaintenanceGroup,on_delete=models.PROTECT,null=True,blank=True)
 technician=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name='assigned_requests')
 due_at=models.DateTimeField(null=True,blank=True)
 # Immutable fields populated on submission; foreign keys alone cannot preserve renamed labels.
 reported_unit_id=models.PositiveBigIntegerField(editable=False)
 reported_unit_name=models.CharField(max_length=120,editable=False)
 reported_location_id=models.PositiveBigIntegerField(editable=False)
 reported_room_label=models.CharField(max_length=80,editable=False)
 asset_tag_at_submission=models.CharField(max_length=50,editable=False)
 created_at=models.DateTimeField(auto_now_add=True)
 updated_at=models.DateTimeField(auto_now=True)
 def save(self,*args,**kwargs):
  if not self.pk:
   loc=self.equipment.location
   self.reported_location_id=loc.pk
   self.reported_room_label=loc.room
   self.reported_unit_id=loc.unit_id
   self.reported_unit_name=loc.unit.name
   self.asset_tag_at_submission=self.equipment.asset_tag
  else:
   old=type(self).objects.get(pk=self.pk)
   for field in ('reported_location_id','reported_room_label','reported_unit_id','reported_unit_name','asset_tag_at_submission'):
    if getattr(self,field)!=getattr(old,field):raise ValidationError('Historical submission snapshot cannot be changed')
  super().save(*args,**kwargs)
 def __str__(self):return f'#{self.pk}: {self.title}'
class DueDateHistory(models.Model):
    """Append-only application audit of coordinator deadline changes."""
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE,
                                related_name='due_date_history')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    old_due_at = models.DateTimeField(null=True, blank=True)
    new_due_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class StatusHistory(models.Model):
 request=models.ForeignKey(MaintenanceRequest,on_delete=models.CASCADE,related_name='status_history')
 actor=models.ForeignKey(User,on_delete=models.PROTECT)
 old_status=models.CharField(max_length=20)
 new_status=models.CharField(max_length=20)
 reason=models.TextField(blank=True)
 created_at=models.DateTimeField(auto_now_add=True)
class AssignmentHistory(models.Model):
 request=models.ForeignKey(MaintenanceRequest,on_delete=models.CASCADE,related_name='assignment_history')
 actor=models.ForeignKey(User,on_delete=models.PROTECT)
 old_technician=models.ForeignKey(User,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
 new_technician=models.ForeignKey(User,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
 old_group=models.ForeignKey(MaintenanceGroup,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
 new_group=models.ForeignKey(MaintenanceGroup,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
 reason=models.TextField()
 created_at=models.DateTimeField(auto_now_add=True)
class WorkLog(models.Model):
 request=models.ForeignKey(MaintenanceRequest,on_delete=models.CASCADE,related_name='work_logs')
 author=models.ForeignKey(User,on_delete=models.PROTECT)
 note=models.TextField()
 created_at=models.DateTimeField(auto_now_add=True)
