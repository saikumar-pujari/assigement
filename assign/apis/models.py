import uuid
from django.db import models


class Job(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    row_count_raw = models.IntegerField(null=True, blank=True)
    row_count_clean = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job({self.id}, {self.status})"


class Transaction(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='transactions')
    txn_id = models.CharField(max_length=50, db_index=True)
    date = models.DateField()
    merchant = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20)
    category = models.CharField(max_length=100, blank=True, default='')
    account_id = models.CharField(max_length=50)
    is_anomaly = models.BooleanField(default=False, db_index=True)
    anomaly_reason = models.TextField(blank=True, default='')
    llm_category = models.BooleanField(default=False)
    llm_raw_response = models.TextField(blank=True, default='')
    llm_failed = models.BooleanField(default=False)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.txn_id} - {self.merchant} - {self.amount}"


class JobSummary(models.Model):
    RISK_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='summary')
    total_spend_inr = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_spend_usd = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    top_merchants = models.JSONField(default=list)
    anomaly_count = models.IntegerField(default=0)
    narrative = models.TextField(blank=True, default='')
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')

    def __str__(self):
        return f"Summary for Job({self.job_id})"
