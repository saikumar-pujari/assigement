from django.contrib import admin
from .models import (Job, Transaction, JobSummary)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id', 'filename', 'status', 'row_count_raw', 'row_count_clean', 'created_at']
    list_filter = ['status']
    readonly_fields = ['id', 'created_at', 'completed_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['txn_id', 'merchant', 'amount', 'currency', 'status', 'category', 'is_anomaly']
    list_filter = ['is_anomaly', 'currency', 'status', 'llm_failed']
    search_fields = ['txn_id', 'merchant', 'account_id']


@admin.register(JobSummary)
class JobSummaryAdmin(admin.ModelAdmin):
    list_display = ['job', 'total_spend_inr', 'total_spend_usd', 'anomaly_count', 'risk_level']
    list_filter = ['risk_level']
