import os
import uuid
import random
import re
import csv
import json
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from .models import TranscriptionResult
from django.contrib.auth import login
from django.contrib.auth.models import User
from .models import EmailOTP
from .processor import (
    diarize_audio,
    transcribe_audio_groq,
    align_transcript_with_speakers,
    analyze_sentiment,
    generate_summary_and_mom,
    get_speaker_stats,
    get_audio_duration_and_size,
    count_speakers
)
from humanize import naturalsize

os.environ["HF_HUB_DISABLE_SYMLINKS"] = "true"


def index(request):
    return render(request, 'index.html')
def upload(request):
    if request.method == 'POST':
        print("🚀 POST request received at /upload")
        audio_file = request.FILES.get('audio_file')

        if not audio_file:
            print("⚠️ No file uploaded.")
            return render(request, 'upload.html', {'error': 'Please upload an audio file.'})

        print(f"📥 File received: {audio_file.name}")

        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads/'))
        filename = fs.save(f"{uuid.uuid4()}_{audio_file.name}", audio_file)
        audio_path = os.path.join(settings.MEDIA_ROOT, 'uploads', filename)
        print(f"🗂️ Saved file to: {audio_path}")

        try:
            print("🔍 Step 1: Diarization started")
            diar_segments = diarize_audio(audio_path)
            print(f"✅ Diarization done. Segments: {len(diar_segments)}")

            print("🔍 Step 2: Transcription started")
            transcript_data = transcribe_audio_groq(audio_path)
            print("🔍 Raw transcript data received:", transcript_data)
            if "error" in transcript_data:
                raise Exception(transcript_data["error"])
            print(f"✅ Transcription done. Length: {len(transcript_data.get('text', ''))} characters")

            print("🔍 Step 3: Alignment with speaker segments")
            aligned = align_transcript_with_speakers(diar_segments, transcript_data)
            print(f"✅ Alignment done. Aligned segments: {len(aligned)}")
            print("🔎 Type of aligned transcript:", type(aligned))  # Should be list

            print("🔍 Step 4: Sentiment Analysis")
            full_text = " ".join([seg["text"] for seg in aligned])
            sentiment_label, polarity, subjectivity = analyze_sentiment(full_text)
            print(f"✅ Sentiment: {sentiment_label}, Polarity: {polarity}, Subjectivity: {subjectivity}")

            print("🔍 Step 5: Summary and MoM generation")
            summary, mom = "N/A", "N/A"
            try:
                summary_response = generate_summary_and_mom(full_text)
                print("🔍 Summary Response:", summary_response)
                print("🔍 Type of summary_response:", type(summary_response))

                if isinstance(summary_response, dict):
                    summary = summary_response.get("summary", "N/A")
                    mom = summary_response.get("mom", "N/A")
                    print("🔍 MoM Extracted:", mom)
                    print("🔍 Type of mom before dump:", type(mom))
                    if isinstance(mom, dict):
                        mom = json.dumps(mom, indent=2)
                        print("✅ Converted MoM to JSON string")
                elif isinstance(summary_response, str):
                    summary = mom = summary_response
                    print("⚠️ Summary response was a plain string.")
            except Exception as e:
                print(f"⚠️ Summary generation failed: {e}")
                summary = mom = "Summary and MoM generation failed."

            print("✅ Summary and MoM handled")

            print("🔍 Step 6: Speaker Stats generation")
            speaker_stats_html = get_speaker_stats(aligned)
            print("✅ Speaker stats generated")

            filesize_str, duration, size_bytes = get_audio_duration_and_size(audio_path)
            speakers = count_speakers(aligned)
            print(f"📝 File: {filesize_str}, Duration: {duration:.2f} sec, Size: {size_bytes} bytes, Speakers: {speakers}")

            user_email = request.session.get('email')
            if not user_email:
                messages.error(request, "You must be logged in to upload files.")
                return redirect('login_email')

            transcription_result = TranscriptionResult.objects.create(
                user_email=user_email,
                uploaded_filename=audio_file.name,
                transcript=aligned,
                tagged_segments=aligned,
                summary=summary,
                mom=mom,
                sentiment_label=sentiment_label,
                polarity=polarity,
                subjectivity=subjectivity,
                speaker_stats_html=speaker_stats_html,
                filesize_str=filesize_str,
                filesize_bytes=size_bytes,
                duration=f"{duration:.2f} sec",
                speakers=speakers,
                audio_file=filename,
            )

            request.session['transcription_id'] = transcription_result.id
            request.session.modified = True

            print("✅ All steps completed. Redirecting to result page.")
            return redirect('transcription_result')

        except Exception as e:
            print(f"❌ Error during processing: {e}")
            return render(request, 'upload.html', {'error': f'Processing failed: {str(e)}'})

    print("📄 GET request — rendering upload.html")
    return render(request, 'upload.html')

def transcription_result(request):
    transcription_id = request.GET.get('id') or request.session.get('transcription_id')
    if not transcription_id:
        messages.error(request, "No transcription selected.")
        return redirect('dashboard')

    try:
        transcription_result = TranscriptionResult.objects.get(id=transcription_id)
    except TranscriptionResult.DoesNotExist:
        messages.error(request, "Transcription not found.")
        return redirect('dashboard')

    # ✅ Convert mom JSON string back to dict
    try:
        mom_data = json.loads(transcription_result.mom) if transcription_result.mom else {}
    except json.JSONDecodeError:
        mom_data = {}
        # Load tagged_segments


    return render(request, 'transcription_result.html', {
        'audio_url': transcription_result.audio_file.url if transcription_result.audio_file else '',
        'transcript': transcription_result.transcript,
        'summary': transcription_result.summary,
        'mom': mom_data,  # 👈 FIXED
        'sentiment_label': transcription_result.sentiment_label,
        'polarity': transcription_result.polarity,
        'subjectivity': transcription_result.subjectivity,
        'speaker_stats_html': transcription_result.speaker_stats_html,
        'filename': transcription_result.uploaded_filename,
        'filesize': transcription_result.filesize_str,
        'duration': transcription_result.duration,
        'speakers': transcription_result.speakers,
    })

# # # ------------------ File Export Functions ------------------

def generate_txt(transcript, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        for entry in transcript:
            f.write(f"{entry['speaker']}: {entry['text']}\n")


def generate_csv(transcript, file_path):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Speaker', 'Text'])
        for entry in transcript:
            writer.writerow([entry['speaker'], entry['text']])


def generate_srt(transcript, file_path):
    def seconds_to_srt_time(seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},000"

    with open(file_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(transcript):
            start = i * 5
            end = start + 4
            f.write(f"{i+1}\n")
            f.write(f"{seconds_to_srt_time(start)} --> {seconds_to_srt_time(end)}\n")
            f.write(f"{entry['speaker']}: {entry['text']}\n\n")


def download_transcript(request, file_format):
    transcript = request.session.get('transcript')
    if not transcript:
        messages.error(request, "No transcript available for download.")
        return redirect('upload')

    filename = f"transcript.{file_format}"
    file_path = os.path.join(settings.MEDIA_ROOT, 'temp', filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    try:
        if file_format == 'txt':
            generate_txt(transcript, file_path)
            content_type = 'text/plain'
        elif file_format == 'csv':
            generate_csv(transcript, file_path)
            content_type = 'text/csv'
        elif file_format == 'srt':
            generate_srt(transcript, file_path)
            content_type = 'application/x-subrip'
        else:
            messages.error(request, "Invalid file format requested.")
            return redirect('upload')

        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def download_results(request):
    # Debugging: print session keys
    print("Session Keys:", list(request.session.keys()))

    # Retrieve session data
    summary = request.session.get('summary')
    sentiment_label = request.session.get('sentiment_label')
    polarity = request.session.get('polarity')
    subjectivity = request.session.get('subjectivity')
    speaker_stats_html = request.session.get('speaker_stats_html')

    # Check if required data exists
    if not summary or not speaker_stats_html:
        messages.error(request, "No analysis results available for download.")
        return redirect('upload')

    # Clean speaker stats (remove HTML tags)
    speaker_stats_text = re.sub('<[^<]+?>', '', speaker_stats_html)

    # File path setup
    filename = "analysis_results.txt"
    file_path = os.path.join(settings.MEDIA_ROOT, 'temp', filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write content to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("Summary:\n")
        f.write(summary + "\n\n")
        f.write(f"Sentiment: {sentiment_label}\n")
        f.write(f"Polarity: {polarity}\n")
        f.write(f"Subjectivity: {subjectivity}\n\n")
        f.write("Speaker Statistics:\n")
        f.write(speaker_stats_text)

    # Read file and return as downloadable response
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Clean up (delete file after sending)
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Warning: Could not delete temp file: {e}")

    return response

# # # ------------------ Email OTP Login ------------------
def login_email_view(request):
    if request.method == 'POST' or request.GET.get('resend'):
        email = request.POST.get('email') if request.method == 'POST' else request.session.get('email')

        if not email:
            messages.error(request, "Email field cannot be empty.")
            return redirect('login_email')

        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.christuniversity\.in$'
        if not re.match(pattern, email):
            messages.error(request, "Use your academic email ID (e.g., name@dept.christuniversity.in).")
            return redirect('login_email')

        # Generate and store OTP
        otp = str(random.randint(100000, 999999))
        EmailOTP.objects.filter(email=email).delete()
        EmailOTP.objects.create(email=email, otp=otp)

        request.session['email'] = email
        request.session['failed_attempts'] = 0

        # Debug print
        print(f"Generated OTP for {email}: {otp}")

        try:
            send_mail(
                'Your OTP for TranscribeHub Login',
                f'Your OTP is: {otp}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            messages.error(request, f"Error sending OTP: {str(e)}")
            return redirect('login_email')

        messages.success(request, "OTP sent successfully. Check your email.")
        return redirect('verify_otp')

    return render(request, 'login_email.html')

def verify_otp_view(request):
    if request.method == 'POST':
        entered_otp = str(request.POST.get('otp', '')).strip()  # Ensure string and remove whitespace
        email = request.session.get('email')
        failed_attempts = request.session.get('failed_attempts', 0)

        if not email:
            messages.error(request, "Session expired. Please log in again.")
            return redirect('login_email')

        otp_record = EmailOTP.objects.filter(email=email, is_verified=False).last()

        # Debug prints
        print(f"Entered OTP: {entered_otp}")
        print(f"Stored OTP: {getattr(otp_record, 'otp', None)}")

        if not otp_record:
            messages.error(request, "No valid OTP found. Please request a new one.")
            return redirect('login_email')

        if (timezone.now() - otp_record.created_at).total_seconds() > 300:
            otp_record.delete()
            messages.error(request, "OTP expired. Please request a new one.")
            return redirect('login_email')

        if failed_attempts >= 3:
            messages.error(request, "Too many failed attempts. Try again later.")
            return redirect('login_email')

        # Critical OTP verification check
        if entered_otp == str(otp_record.otp):
            # Mark OTP as verified
            otp_record.is_verified = True
            otp_record.save()

            # Get or create user
            user, created = User.objects.get_or_create(
                username=email,
                defaults={'email': email}
            )
            login(request, user)

            # Cleanup OTP records
            EmailOTP.objects.filter(email=email).delete()

            # Clear failed attempts
            if 'failed_attempts' in request.session:
                del request.session['failed_attempts']

            messages.success(request, "OTP verified successfully.")
            
            # Redirect based on new/existing user
            if created:
                print("New user created - redirecting to upload")
                return redirect('upload')
            else:
                print("Existing user - redirecting to dashboard")
                return redirect('dashboard')
        else:
            # Handle incorrect OTP
            request.session['failed_attempts'] = failed_attempts + 1
            messages.error(request, f"Invalid OTP. Attempt {failed_attempts + 1}/3.")
            print(f"Failed OTP attempt {failed_attempts + 1} for {email}")
            return redirect('verify_otp')

    return render(request, 'verify_otp.html')

def resend_otp(request):
    if request.method == 'POST':
        email = request.session.get('email')
        if email:
            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp

            send_mail(
                'Your new OTP',
                f'Your OTP is {otp}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'User not logged in'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    print("✅ Dashboard view accessed")
    print("User:", request.user)
    print("Is Authenticated:", request.user.is_authenticated)

    user_email = request.user.email
    transcriptions = TranscriptionResult.objects.filter(user_email=user_email).order_by('-created_at')

# Calculate stats
    total_files = transcriptions.count()
    downloads = total_files  # if downloads not tracked separately
    success_rate = 100 if total_files > 0 else 0
    this_month = transcriptions.filter(
        created_at__month=timezone.now().month,
        created_at__year=timezone.now().year
    ).count()

    context = {
        'transcriptions': transcriptions,
        'total_files': total_files,
        'downloads': downloads,
        'success_rate': success_rate,
        'this_month': this_month
    }

    return render(request, 'dashboard.html', context)




