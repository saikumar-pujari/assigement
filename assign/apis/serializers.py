from django.db.models import Sum, Count
from rest_framework import serializers
from .models import (Job, Transaction, JobSummary)


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            'id', 'filename', 'status', 'row_count_raw', 'row_count_clean',
            'created_at', 'completed_at', 'error_message',
        ]
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'txn_id', 'date', 'merchant', 'amount', 'currency', 'status',
            'category', 'account_id', 'is_anomaly', 'anomaly_reason',
            'llm_category', 'llm_failed',
        ]


class JobSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobSummary
        fields = [
            'total_spend_inr', 'total_spend_usd', 'top_merchants',
            'anomaly_count', 'narrative', 'risk_level',
        ]


class JobResultsSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)
    anomalies = serializers.SerializerMethodField()
    category_breakdown = serializers.SerializerMethodField()
    summary = JobSummarySerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'filename', 'status', 'row_count_raw', 'row_count_clean',
            'created_at', 'completed_at', 'transactions', 'anomalies',
            'category_breakdown', 'summary',
        ]

    def get_anomalies(self, obj):
        qs = obj.transactions.filter(is_anomaly=True)
        return TransactionSerializer(qs, many=True).data

    def get_category_breakdown(self, obj):
        return list(
            obj.transactions
               .values('category')
               .annotate(count=Count('id'), total_amount=Sum('amount'))
               .order_by('-total_amount')
        )
