"""
Tests for core app – notifications, profile page, teacher statistics, audit log,
homepage, subject preferences.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.models import AuditLog, Notification, SiteConfig
from materials.models import Material, MaterialType, SchoolYear, Subject, SubjectYear

User = get_user_model()


def _pdf():
    return SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake', content_type='application/pdf')


class CoreFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        SiteConfig.objects.update_or_create(pk=1, defaults={'setup_complete': True})
        cls.admin = User.objects.create_user(
            username='admin_c', email='admin_c@test.cz', password='pass',
            role=User.Role.ADMIN, is_staff=True,
        )
        cls.teacher = User.objects.create_user(
            username='teacher_c', email='teacher_c@test.cz', password='pass',
            role=User.Role.TEACHER,
        )
        cls.student = User.objects.create_user(
            username='student_c', email='student_c@test.cz', password='pass',
            role=User.Role.STUDENT,
        )
        cls.year = SchoolYear.objects.create(name='Sekunda B', slug='sekunda-b')
        cls.subject_def = Subject.objects.create(name='Fyzika', slug='fyzika')
        cls.subject = SubjectYear.objects.create(
            subject=cls.subject_def, school_year=cls.year,
        )
        cls.subject.teachers.add(cls.teacher)
        cls.mtype, _ = MaterialType.objects.get_or_create(name='Podklady', slug='podklady')
        cls.material = Material.objects.create(
            title='Gravitace',
            subject=cls.subject,
            material_type=cls.mtype,
            file=_pdf(),
            author=cls.teacher,
        )


# ---------------------------------------------------------------------------
# Notification tests
# ---------------------------------------------------------------------------

class NotificationModelTest(CoreFixtureMixin, TestCase):
    def test_create_notification(self):
        n = Notification.objects.create(
            recipient=self.student,
            verb='Nový materiál: Gravitace',
            target_url='/materialy/material/1/',
        )
        self.assertFalse(n.is_read)
        self.assertEqual(str(n), f'{self.student} – Nový materiál: Gravitace')

    def test_notification_marked_read_on_list(self):
        Notification.objects.create(recipient=self.student, verb='Test notifikace')
        c = Client()
        c.force_login(self.student)
        url = reverse('core:notifications')
        c.get(url)
        self.assertEqual(Notification.objects.filter(recipient=self.student, is_read=False).count(), 0)

    def test_unread_count_in_context(self):
        Notification.objects.create(recipient=self.student, verb='Notifikace 1')
        Notification.objects.create(recipient=self.student, verb='Notifikace 2')
        c = Client()
        c.force_login(self.student)
        r = c.get(reverse('core:homepage'))
        self.assertEqual(r.context.get('unread_notifications_count', 0), 2)

    def test_vip_grant_creates_notification(self):
        from materials.models import SubjectVIP
        SubjectVIP.objects.create(
            user=self.student,
            subject=self.subject,
            granted_by=self.teacher,
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.student).exists()
        )

    def test_notifications_requires_login(self):
        r = Client().get(reverse('core:notifications'))
        self.assertEqual(r.status_code, 302)


# ---------------------------------------------------------------------------
# Profile page tests
# ---------------------------------------------------------------------------

class ProfilePageTest(CoreFixtureMixin, TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(self.teacher)
        self.url = reverse('core:profile')

    def test_profile_page_loads(self):
        r = self.c.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('profile_user', r.context)

    def test_profile_shows_own_materials(self):
        r = self.c.get(self.url)
        self.assertEqual(r.context['total_uploads'], 1)

    def test_profile_edit_saves_name(self):
        self.c.post(self.url, {
            'first_name': 'Jana',
            'last_name': 'Nováková',
            'privacy_level': 'full_name',
            'enrollment_year': '',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, 'Jana')
        self.assertEqual(self.teacher.last_name, 'Nováková')

    def test_profile_edit_privacy_level(self):
        self.c.post(self.url, {
            'first_name': '',
            'last_name': '',
            'privacy_level': 'initials',
            'enrollment_year': '',
        })
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.privacy_level, 'initials')

    def test_profile_requires_login(self):
        r = Client().get(self.url)
        self.assertEqual(r.status_code, 302)


# ---------------------------------------------------------------------------
# Teacher statistics tests
# ---------------------------------------------------------------------------

class TeacherStatisticsTest(CoreFixtureMixin, TestCase):
    def test_teacher_sees_own_subject_stats(self):
        c = Client()
        c.force_login(self.teacher)
        r = c.get(reverse('core:statistics'))
        self.assertEqual(r.status_code, 200)
        stats = r.context['subject_stats']
        subject_names = [s['subject'].name for s in stats]
        self.assertIn('Fyzika', subject_names)

    def test_admin_sees_all_subjects(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse('core:statistics'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['is_admin_view'])

    def test_student_gets_403(self):
        c = Client()
        c.force_login(self.student)
        r = c.get(reverse('core:statistics'))
        self.assertEqual(r.status_code, 403)

    def test_statistics_requires_login(self):
        r = Client().get(reverse('core:statistics'))
        self.assertEqual(r.status_code, 302)

    def test_stats_contain_material_count(self):
        c = Client()
        c.force_login(self.teacher)
        r = c.get(reverse('core:statistics'))
        stat = next(s for s in r.context['subject_stats'] if s['subject'].name == 'Fyzika')
        self.assertEqual(stat['total_count'], 1)


# ---------------------------------------------------------------------------
# Audit log tests
# ---------------------------------------------------------------------------

class AuditLogTest(CoreFixtureMixin, TestCase):
    def test_audit_log_created_on_login(self):
        """audit_log() writes a LOGIN entry correctly."""
        from core.audit import audit_log
        before = AuditLog.objects.filter(action=AuditLog.Action.LOGIN).count()
        audit_log(self.student, AuditLog.Action.LOGIN, description='Přihlášení: test')
        after = AuditLog.objects.filter(action=AuditLog.Action.LOGIN).count()
        self.assertEqual(after, before + 1)

    def test_audit_log_level_default_info(self):
        from core.audit import audit_log
        audit_log(self.student, AuditLog.Action.DOWNLOAD, description='Test')
        entry = AuditLog.objects.filter(action=AuditLog.Action.DOWNLOAD).last()
        self.assertEqual(entry.level, AuditLog.Level.INFO)

    def test_audit_log_warning_level(self):
        from core.audit import audit_log
        audit_log(self.admin, AuditLog.Action.DELETE, description='Smazáno', level='warning')
        entry = AuditLog.objects.filter(action=AuditLog.Action.DELETE).last()
        self.assertEqual(entry.level, AuditLog.Level.WARNING)


# ---------------------------------------------------------------------------
# User model helpers
# ---------------------------------------------------------------------------

class UserModelTest(CoreFixtureMixin, TestCase):
    def test_display_name_full(self):
        self.student.first_name = 'Petr'
        self.student.last_name = 'Novák'
        self.student.privacy_level = 'full_name'
        self.assertEqual(self.student.get_display_name(), 'Petr Novák')

    def test_display_name_initials(self):
        self.student.first_name = 'Petr'
        self.student.last_name = 'Novák'
        self.student.privacy_level = 'initials'
        self.assertEqual(self.student.get_display_name(), 'P.N.')

    def test_display_name_anonymous(self):
        self.student.privacy_level = 'anonymous'
        self.student.enrollment_year = 2022
        name = self.student.get_display_name()
        self.assertIn('2022', name)

    def test_can_upload_teacher(self):
        self.assertTrue(self.teacher.can_upload_to(self.subject))

    def test_can_upload_student_without_vip(self):
        self.assertFalse(self.student.can_upload_to(self.subject))

    def test_can_upload_student_with_vip(self):
        from materials.models import SubjectVIP
        SubjectVIP.objects.create(
            user=self.student, subject=self.subject, granted_by=self.teacher,
        )
        self.assertTrue(self.student.can_upload_to(self.subject))
