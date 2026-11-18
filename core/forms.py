from django import forms
from django.contrib.auth.models import User
from .models import MaintenanceRequest, Equipment, MaintenanceGroup, Profile
from .services import allowed_actions, eligible_technicians, role, scope_groups


class RequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ['equipment', 'problem_type', 'title', 'description', 'priority']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = Equipment.objects.filter(active=True)


class ActionForm(forms.Form):
    action = forms.ChoiceField(choices=[], label='Action')
    group = forms.ModelChoiceField(queryset=MaintenanceGroup.objects.none(), required=False,
                                    label='Maintenance group')
    technician = forms.ModelChoiceField(queryset=User.objects.none(), required=False,
                                         label='Eligible technician')
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False,
                             help_text='Required for assignment, reassignment, rejection, completion and return.')

    def __init__(self, *args, user, item, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item
        self.fields['action'].choices = allowed_actions(user, item)
        if role(user) not in (Profile.COORDINATOR, Profile.ADMIN):
            return
        groups = MaintenanceGroup.objects.filter(pk__in=scope_groups(user)).order_by('name')
        self.fields['group'].queryset = groups
        # The union allows a group change without typed IDs; the workflow service
        # still checks the exact group/competence combination on every POST.
        self.fields['technician'].queryset = User.objects.filter(
            is_active=True,
            liat_profile__role=Profile.TECHNICIAN,
            maintenance_memberships__group__in=groups,
            maintenance_memberships__active=True,
            competencies__category=item.equipment.category,
            competencies__problem_type=item.problem_type,
            competencies__active=True,
        ).distinct().order_by('username')
        if not self.is_bound and item.group_id and groups.filter(pk=item.group_id).exists():
            self.initial.setdefault('group', item.group_id)
            if item.technician_id:
                self.initial.setdefault('technician', item.technician_id)

    def clean(self):
        data = super().clean()
        if data.get('action') == 'assign':
            if not data.get('group'):
                self.add_error('group', 'Choose a maintenance group.')
            if not data.get('technician'):
                self.add_error('technician', 'Choose an eligible technician.')
            if data.get('group') and data.get('technician'):
                group, technician = data['group'], data['technician']
                # This duplication is purposeful: immediate form feedback plus
                # authoritative validation again in the transaction service.
                if not eligible_technicians(group, self.item.equipment.category, self.item.problem_type).filter(pk=technician.pk).exists():
                    self.add_error('technician', 'This technician is not eligible for the selected group.')
        return data
