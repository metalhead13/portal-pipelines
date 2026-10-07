from django.contrib import admin

from .models import Pipeline, PipelineRun


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("name", "engine", "dag_id", "active", "created_at")
    list_filter = ("engine", "active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline", "status", "requested_by", "created_at")
    list_filter = ("status", "pipeline")
    readonly_fields = ("id", "pipeline", "requested_by", "status", "original_filename", "remote_run_id", "metrics", "error_message", "created_at", "started_at", "finished_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
