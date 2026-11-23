from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from . import models


class ProfileInline(admin.StackedInline):
    model = models.Profile
    extra = 0
    can_delete = False


class LIATUserAdmin(UserAdmin):
    inlines = (ProfileInline,)


admin.site.unregister(User)
admin.site.register(User, LIATUserAdmin)


@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'account_type', 'unit')
    list_filter = ('role', 'account_type')
    search_fields = ('user__username',)


@admin.register(models.MaintenanceRequest)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'group', 'technician', 'reporter')
    list_filter = ('status', 'group', 'priority')
    search_fields = ('title', 'equipment__asset_tag', 'reporter__username')
    # Maintenance requests are submitted and managed only by the application workflow.
    # The Academy Administrator can inspect them here, but cannot create, edit, or
    # delete requests without bypassing the validated, audited services.
    readonly_fields = ('reporter', 'equipment', 'problem_type',
                       'status', 'group', 'technician', 'due_at', 'reported_unit_id',
                       'reported_unit_name', 'reported_location_id',
                       'reported_room_label', 'asset_tag_at_submission')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AuditRecordAdmin(admin.ModelAdmin):
    # Audit rows are not editable from the administrative interface.
    # Full database-level tamper protection is outside this local prototype.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (models.StatusHistory, models.AssignmentHistory, models.WorkLog, models.DueDateHistory):
    admin.site.register(model, AuditRecordAdmin)

for model in (
    models.AcademyUnit, models.Location, models.EquipmentCategory,
    models.ProblemType, models.Equipment, models.MaintenanceGroup,
    models.GroupMembership, models.CoordinatorScope, models.TechnicianCompetency,
):
    admin.site.register(model)
