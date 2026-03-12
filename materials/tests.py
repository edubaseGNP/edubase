"""
Tests for materials app – download counter, likes, comments, bulk upload, versioning.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.models import SiteConfig
from .models import Comment, Material, MaterialLike, MaterialType, SchoolYear, Subject

User = get_user_model()


def _pdf():
    return SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake', content_type='application/pdf')


class MaterialFixtureMixin:
    """Create minimal DB objects shared across test cases."""

    @classmethod
    def setUpTestData(cls):
        SiteConfig.objects.update_or_create(pk=1, defaults={'setup_complete': True})
        cls.admin = User.objects.create_user(
            username='admin', email='admin@test.cz', password='pass',
            role=User.Role.ADMIN, is_staff=True,
        )
        cls.teacher = User.objects.create_user(
            username='teacher', email='teacher@test.cz', password='pass',
            role=User.Role.TEACHER,
        )
        cls.student = User.objects.create_user(
            username='student', email='student@test.cz', password='pass',
            role=User.Role.STUDENT,
        )
        cls.year = SchoolYear.objects.create(name='Prima A', slug='prima-a')
        cls.subject = Subject.objects.create(
            name='Matematika', slug='matematika', school_year=cls.year,
        )
        cls.subject.teachers.add(cls.teacher)
        cls.mtype, _ = MaterialType.objects.get_or_create(name='Podklady', slug='podklady')
        cls.material = Material.objects.create(
            title='Test material',
            subject=cls.subject,
            material_type=cls.mtype,
            file=_pdf(),
            author=cls.teacher,
        )


class DownloadCounterTest(MaterialFixtureMixin, TestCase):
    def test_download_increments_counter(self):
        c = Client()
        c.force_login(self.student)
        before = Material.objects.get(pk=self.material.pk).download_count
        r = c.get(reverse('materials:material_download', kwargs={'pk': self.material.pk}))
        self.assertIn(r.status_code, [301, 302])
        after = Material.objects.get(pk=self.material.pk).download_count
        self.assertEqual(after, before + 1)

    def test_download_requires_login(self):
        r = Client().get(reverse('materials:material_download', kwargs={'pk': self.material.pk}))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/', r['Location'])


class LikeTest(MaterialFixtureMixin, TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(self.student)
        self.url = reverse('materials:material_like', kwargs={'pk': self.material.pk})

    def test_like_creates_entry(self):
        self.c.post(self.url)
        self.assertTrue(MaterialLike.objects.filter(material=self.material, user=self.student).exists())

    def test_like_toggle_removes_entry(self):
        MaterialLike.objects.create(material=self.material, user=self.student)
        self.c.post(self.url)
        self.assertFalse(MaterialLike.objects.filter(material=self.material, user=self.student).exists())

    def test_double_like_unique_constraint(self):
        self.c.post(self.url)
        self.c.post(self.url)  # second = unlike
        self.assertEqual(MaterialLike.objects.filter(material=self.material, user=self.student).count(), 0)

    def test_like_requires_login(self):
        r = Client().post(self.url)
        self.assertEqual(r.status_code, 302)


class CommentTest(MaterialFixtureMixin, TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(self.student)
        self.add_url = reverse('materials:comment_add', kwargs={'pk': self.material.pk})

    def test_add_comment(self):
        self.c.post(self.add_url, {'text': 'Výborný materiál!'})
        self.assertTrue(Comment.objects.filter(material=self.material, text='Výborný materiál!').exists())

    def test_empty_comment_ignored(self):
        self.c.post(self.add_url, {'text': '   '})
        self.assertEqual(Comment.objects.filter(material=self.material).count(), 0)

    def test_author_can_delete_own_comment(self):
        comment = Comment.objects.create(material=self.material, author=self.student, text='X')
        del_url = reverse('materials:comment_delete', kwargs={'pk': comment.pk})
        self.c.post(del_url)
        comment.refresh_from_db()
        self.assertFalse(comment.is_visible)

    def test_other_student_cannot_delete_comment(self):
        other = User.objects.create_user(username='other', email='other@test.cz', password='pass')
        comment = Comment.objects.create(material=self.material, author=self.student, text='X')
        c2 = Client()
        c2.force_login(other)
        del_url = reverse('materials:comment_delete', kwargs={'pk': comment.pk})
        c2.post(del_url)
        comment.refresh_from_db()
        self.assertTrue(comment.is_visible)  # still visible

    def test_admin_can_delete_any_comment(self):
        comment = Comment.objects.create(material=self.material, author=self.student, text='X')
        c = Client()
        c.force_login(self.admin)
        del_url = reverse('materials:comment_delete', kwargs={'pk': comment.pk})
        c.post(del_url)
        comment.refresh_from_db()
        self.assertFalse(comment.is_visible)


class BulkUploadTest(MaterialFixtureMixin, TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(self.teacher)
        self.url = reverse('materials:bulk_upload',
                           kwargs={'year_slug': self.year.slug, 'subject_slug': self.subject.slug})

    def test_get_requires_upload_permission(self):
        c = Client()
        c.force_login(self.student)
        r = c.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_bulk_upload_creates_multiple_materials(self):
        before = Material.objects.filter(subject=self.subject).count()
        f1 = SimpleUploadedFile('file1.pdf', b'%PDF-1.4 a', content_type='application/pdf')
        f2 = SimpleUploadedFile('file2.pdf', b'%PDF-1.4 b', content_type='application/pdf')
        self.c.post(self.url, {'files': [f1, f2], 'material_type': self.mtype.pk})
        after = Material.objects.filter(subject=self.subject).count()
        self.assertEqual(after, before + 2)

    def test_bulk_upload_no_files_shows_error(self):
        r = self.c.post(self.url, {'material_type': self.mtype.pk}, follow=True)
        self.assertContains(r, 'Vyberte')


class VersioningTest(MaterialFixtureMixin, TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(self.teacher)
        self.url = reverse('materials:material_new_version', kwargs={'pk': self.material.pk})

    def test_new_version_creates_material(self):
        before = Material.objects.count()
        self.c.post(self.url, {'file': _pdf()})
        self.assertEqual(Material.objects.count(), before + 1)

    def test_new_version_increments_version_number(self):
        self.c.post(self.url, {'file': _pdf()})
        new = Material.objects.filter(parent=self.material).first()
        self.assertIsNotNone(new)
        self.assertEqual(new.version, 2)

    def test_new_version_hides_original(self):
        self.c.post(self.url, {'file': _pdf()})
        self.material.refresh_from_db()
        self.assertFalse(self.material.is_published)

    def test_student_cannot_upload_version(self):
        c = Client()
        c.force_login(self.student)
        r = c.post(self.url, {'file': _pdf()})
        self.assertEqual(r.status_code, 403)

    def test_version_chain(self):
        """v1 → v2 → v3."""
        self.c.post(self.url, {'file': _pdf()})
        v2 = Material.objects.get(parent=self.material)
        url_v2 = reverse('materials:material_new_version', kwargs={'pk': v2.pk})
        self.c.post(url_v2, {'file': _pdf()})
        v3 = Material.objects.filter(parent=v2).first()
        self.assertIsNotNone(v3)
        self.assertEqual(v3.version, 3)


class MaterialDetailContextTest(MaterialFixtureMixin, TestCase):
    def test_detail_contains_comments_and_likes(self):
        c = Client()
        c.force_login(self.student)
        Comment.objects.create(material=self.material, author=self.student, text='OK')
        MaterialLike.objects.create(material=self.material, user=self.student)
        r = c.get(reverse('materials:material_detail', kwargs={'pk': self.material.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['comments']), 1)
        self.assertEqual(r.context['like_count'], 1)
        self.assertTrue(r.context['user_liked'])
