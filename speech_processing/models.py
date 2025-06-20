import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.email} - {'Verified' if self.is_verified else 'Pending'}"

from django.db import models

class TranscriptionResult(models.Model):
    user_email = models.EmailField()  # Add this line
    uploaded_filename = models.CharField(max_length=255)
    transcript = models.JSONField()  # or TextField, depending on your data
    summary = models.TextField()
    mom = models.TextField()
    sentiment_label = models.CharField(max_length=100)
    polarity = models.FloatField()
    subjectivity = models.FloatField()
    speaker_stats_html = models.TextField()
    
    tagged_segments = models.JSONField(null=True, blank=True)
    subjectivity = models.FloatField(null=True, blank=True)

    filesize_str = models.CharField(max_length=100)
    filesize_bytes = models.BigIntegerField()
    duration = models.CharField(max_length=50)
    speakers = models.IntegerField()
    audio_file = models.FileField(upload_to='uploads/')  # assuming this is correct

    # Optional: timestamp
    created_at = models.DateTimeField(auto_now_add=True)