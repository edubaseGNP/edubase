"""
Tests for materials app – download counter, likes, comments, bulk upload, versioning,
search (deduplication, hit_count, excerpt), SubjectZip.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.models import SiteConfig
from .models import Comment, Material, MaterialLike, MaterialType, SchoolYear, SearchLog, Subject, SubjectYear

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
        cls.subject_def = Subject.objects.create(
            name='Matematika', slug='matematika',
        )
        cls.subject = SubjectYear.objects.create(
            subject=cls.subject_def, school_year=cls.year,
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


class SearchTest(MaterialFixtureMixin, TestCase):
    """Tests for MaterialSearchView: logging, deduplication, hit_count, excerpt."""

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.student)
        self.url = reverse('materials:search')
        # Give the material some OCR text
        Material.objects.filter(pk=self.material.pk).update(
            title='Kvadratické rovnice',
            description='Cvičení na kvadratické rovnice',
            extracted_text='kvadratické kvadratické rovnice jsou základem algebry',
            ocr_processed=True,
        )
        self.material.refresh_from_db()

    def test_search_returns_result(self):
        r = self.c.get(self.url, {'q': 'kvadratické'})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.context['object_list']), 0)

    def test_search_logs_query(self):
        before = SearchLog.objects.count()
        self.c.get(self.url, {'q': 'rovnice'})
        self.assertEqual(SearchLog.objects.count(), before + 1)
        log = SearchLog.objects.order_by('-timestamp').first()
        self.assertEqual(log.query, 'rovnice')
        self.assertGreater(log.results_count, 0)

    def test_search_deduplication_within_cooldown(self):
        """Same query from same user within 5 min should not create duplicate log."""
        self.c.get(self.url, {'q': 'algebra'})
        count_after_first = SearchLog.objects.filter(query__iexact='algebra').count()
        self.c.get(self.url, {'q': 'algebra'})
        count_after_second = SearchLog.objects.filter(query__iexact='algebra').count()
        self.assertEqual(count_after_first, count_after_second)

    def test_search_logs_duration_ms(self):
        self.c.get(self.url, {'q': 'rovnice'})
        log = SearchLog.objects.filter(query='rovnice').order_by('-timestamp').first()
        self.assertIsNotNone(log.duration_ms)
        self.assertGreaterEqual(log.duration_ms, 0)

    def test_hit_count_annotated(self):
        r = self.c.get(self.url, {'q': 'kvadratické'})
        results = list(r.context['object_list'])
        self.assertTrue(any(getattr(m, 'hit_count', 0) >= 2 for m in results))

    def test_excerpt_contains_mark(self):
        r = self.c.get(self.url, {'q': 'kvadratické'})
        results = list(r.context['object_list'])
        excerpts = [str(getattr(m, 'excerpt', '')) for m in results]
        self.assertTrue(any('<mark' in e for e in excerpts))

    def test_short_query_returns_no_results(self):
        r = self.c.get(self.url, {'q': 'x'})
        self.assertEqual(len(r.context['object_list']), 0)

    def test_trending_shown_when_no_query(self):
        # Seed some search logs
        SearchLog.objects.create(query='fyzika', user=self.student, results_count=3)
        r = self.c.get(self.url)
        self.assertIn('trending_searches', r.context)

    def test_search_requires_login(self):
        r = Client().get(self.url, {'q': 'test'})
        self.assertEqual(r.status_code, 302)


class ReadingTimeTest(MaterialFixtureMixin, TestCase):
    def test_reading_time_none_when_no_text(self):
        self.material.extracted_text = ''
        self.assertIsNone(self.material.reading_time)

    def test_reading_time_minimum_one_minute(self):
        self.material.extracted_text = 'slovo ' * 10  # 10 words
        self.assertEqual(self.material.reading_time, 1)

    def test_reading_time_calculation(self):
        self.material.extracted_text = 'slovo ' * 400  # 400 words → 2 min
        self.assertEqual(self.material.reading_time, 2)


class SubjectZipTest(MaterialFixtureMixin, TestCase):
    def test_zip_download_returns_zip(self):
        c = Client()
        c.force_login(self.student)
        url = reverse('materials:subject_zip',
                      kwargs={'year_slug': self.year.slug, 'subject_slug': self.subject.slug})
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/zip')

    def test_zip_requires_login(self):
        url = reverse('materials:subject_zip',
                      kwargs={'year_slug': self.year.slug, 'subject_slug': self.subject.slug})
        r = Client().get(url)
        self.assertEqual(r.status_code, 302)
