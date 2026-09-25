from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from tasks.models import UserPreferences, ReminderDelivery, Task


class Command(BaseCommand):
    help = 'Preview due-task reminders; add --send to deliver to verified, opted-in accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true')

    def handle(self, *args, **options):
        if options['send'] and not settings.MAIL_ENABLED:
            raise CommandError('Email delivery is disabled.')
        count = 0
        for profile in UserPreferences.objects.filter(reminders=True, email_verified=True, user__is_active=True).select_related('user').iterator():
            if not profile.email_is_verified:
                continue
            now = timezone.localtime(timezone.now(), ZoneInfo(profile.timezone))
            if now.hour < profile.reminder_hour:
                continue
            due = Task.objects.filter(user=profile.user, deleted_at__isnull=True, complete=False, due_date__lte=now.date()).count()
            if not due or ReminderDelivery.objects.filter(user=profile.user, day=now.date()).exists():
                continue
            count += 1
            if not options['send']:
                continue
            # A unique daily claim prevents concurrent scheduler runs from sending twice.
            try:
                with transaction.atomic():
                    claim = ReminderDelivery.objects.create(user=profile.user, day=now.date())
            except IntegrityError:
                continue
            try:
                with translation.override(profile.language):
                    body = _('You have %(count)s tasks due today or overdue.') % {'count': due}
                    body += '\n' + settings.PUBLIC_BASE_URL.rstrip('/') + '/?status=open'
                    body += '\n\n' + _('You can disable these reminders in Account settings.')
                    delivered = EmailMessage(subject=_('Your Daymark reminder'), body=body,
                        from_email=settings.DEFAULT_FROM_EMAIL, to=[profile.user.email]).send()
                if delivered != 1:
                    raise RuntimeError('Delivery was not accepted.')
            except Exception:
                # Keep a failed/uncertain claim to avoid duplicate emails after SMTP timeouts.
                # Operators can inspect claim counts and explicitly retry after investigating.
                raise CommandError('Reminder delivery failed; daily claim retained to prevent duplicates.') from None
            claim.sent_at = timezone.now()
            claim.save(update_fields=['sent_at'])
        self.stdout.write(f'{count} eligible daily reminders; mode={"send" if options["send"] else "preview"}.')
