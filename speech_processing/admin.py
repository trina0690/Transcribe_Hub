# your_app/admin.py

from django.contrib import admin
from .models import EmailOTP

@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'created_at', 'is_verified')
    list_filter = ('is_verified',)
    search_fields = ('email',)



