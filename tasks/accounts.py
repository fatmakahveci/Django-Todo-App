from smtplib import SMTPException
from zoneinfo import available_timezones

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetView
from django.core import signing
from django.core.mail import EmailMessage
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from .models import UserPreferences


def preferences_for(user):
    return UserPreferences.objects.get_or_create(user=user, defaults={'timezone': settings.TIME_ZONE})[0]


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('Email address'))

    class Meta(UserCreationForm.Meta):
        fields = ['username', 'email']


class PreferencesForm(forms.ModelForm):
    email = forms.EmailField(label=_('Email address'), required=False)
    current_password = forms.CharField(label=_('Current password'), required=False, widget=forms.PasswordInput,
                                      help_text=_('Required only when changing your email address.'))
    timezone = forms.ChoiceField(label=_('Time zone'), choices=[(z, z) for z in sorted(available_timezones())])

    class Meta:
        model = UserPreferences
        fields = ['language', 'timezone', 'reminders', 'reminder_hour']
        labels = {'language': _('Language'), 'reminders': _('Email reminders'), 'reminder_hour': _('Reminder hour (local time)')}
        widgets = {'reminder_hour': forms.NumberInput(attrs={'min': 0, 'max': 23})}

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = user.email

    def clean(self):
        data = super().clean()
        changed = data.get('email', '') != self.user.email
        if changed and not self.user.check_password(data.get('current_password', '')):
            self.add_error('current_password', _('Enter your current password to change your email.'))
        if data.get('reminders') and (changed or not self.instance.email_is_verified or not self.user.email):
            self.add_error('reminders', _('Verify your email before enabling reminders.'))
        if data.get('reminder_hour') is not None and data['reminder_hour'] > 23:
            self.add_error('reminder_hour', _('Choose an hour between 0 and 23.'))
        return data

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data['email'] != self.user.email:
            self.user.email = self.cleaned_data['email']
            self.user.save(update_fields=['email'])
            profile.email_verified = False
            profile.verified_email = ''
            profile.reminders = False
        if commit:
            profile.save()
        return profile


class AccountSettings(LoginRequiredMixin, FormView):
    template_name = 'tasks/account_settings.html'
    form_class = PreferencesForm
    success_url = reverse_lazy('account-settings')

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'user': self.request.user, 'instance': preferences_for(self.request.user)}

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Preferences saved.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'profile': preferences_for(self.request.user), 'mail_enabled': settings.MAIL_ENABLED}


class SendVerification(LoginRequiredMixin, View):
    def post(self, request):
        if not settings.MAIL_ENABLED:
            messages.error(request, _('Email delivery is not configured yet.'))
        elif request.user.email:
            token = signing.dumps({'user': request.user.pk, 'email': request.user.email}, salt='email-verification')
            url = settings.PUBLIC_BASE_URL.rstrip('/') + reverse('verify-email', args=[token])
            try:
                EmailMessage(subject=str(_('Verify your Daymark email')), body=str(_('Confirm your email address:')) + '\n' + url,
                             from_email=settings.DEFAULT_FROM_EMAIL, to=[request.user.email]).send()
            except (OSError, SMTPException):
                messages.error(request, _('Email could not be delivered. Please try again later.'))
            else:
                messages.success(request, _('Verification email sent. The link expires in 24 hours.'))
        return redirect('account-settings')


class VerifyEmail(LoginRequiredMixin, View):
    # The email link leads to a confirmation page; only a CSRF-protected POST changes state.
    def get(self, request, token):
        from django.shortcuts import render
        return render(request, 'tasks/verify_email.html')

    def post(self, request, token):
        try:
            data = signing.loads(token, salt='email-verification', max_age=86400)
            valid = data['user'] == request.user.pk and data['email'] == request.user.email
        except (signing.BadSignature, KeyError):
            valid = False
        if valid:
            profile = preferences_for(request.user)
            profile.email_verified = True
            profile.verified_email = data['email']
            profile.save(update_fields=['email_verified', 'verified_email'])
            messages.success(request, _('Email verified.'))
        else:
            messages.error(request, _('This verification link is invalid or expired.'))
        return redirect('account-settings')


class AccountPasswordReset(PasswordResetView):
    template_name = 'tasks/password_reset_form.html'
    email_template_name = 'tasks/password_reset_email.txt'
    subject_template_name = 'tasks/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        from urllib.parse import urlsplit
        if not settings.MAIL_ENABLED:
            messages.error(self.request, _('Email delivery is not configured yet.'))
            return self.form_invalid(form)
        site = urlsplit(settings.PUBLIC_BASE_URL)
        self.extra_email_context = {'domain': site.netloc, 'protocol': site.scheme}
        return super().form_valid(form)
