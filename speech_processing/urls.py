from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from speech_processing.views import login_email_view

urlpatterns = [
    path('', views.index, name='index'),
    path('login-email/', views.login_email_view, name='login_email'),
    path('upload/', views.upload, name='upload'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('transcription-result/', views.transcription_result, name='transcription_result'),
    # ✅ Add these download routes:
    path('dashboard/', views.dashboard, name='dashboard'),
    path('download/<str:file_format>/', views.download_transcript, name='download_transcript'),
    path('download-results/', views.download_results, name='download_results'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
