import io
import logging
import os
import zipfile

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, ListView

from core.audit import audit_log
from core.models import AuditLog

from .forms import MaterialUploadForm
from .models import Comment, Material, MaterialLike, SchoolYear, Subject, SubjectVIP, SubjectYear
from .utils import compress_image_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# School year & subject list
# ---------------------------------------------------------------------------

class SchoolYearListView(LoginRequiredMixin, ListView):
    model = SchoolYear
    template_name = 'materials/school_year_list.html'
    context_object_name = 'school_years'
    queryset = SchoolYear.objects.filter(is_active=True).prefetch_related('subjects')


class SubjectDetailView(LoginRequiredMixin, DetailView):
    model = SubjectYear
    template_name = 'materials/subject_detail.html'
    context_object_name = 'subject'

    def get_object(self, queryset=None):
        return get_object_or_404(
            SubjectYear.objects.select_related('subject', 'school_year').prefetch_related('teachers'),
            school_year__slug=self.kwargs['year_slug'],
            subject__slug=self.kwargs['subject_slug'],
        )

    def get_context_data(self, **kwargs):
        from .models import Tag
        from django.db.models import Count
        ctx = super().get_context_data(**kwargs)
        subject = self.object
        qs = (
            subject.materials
            .filter(is_published=True)
            .select_related('author', 'material_type')
            .prefetch_related('tags', 'likes')
            .annotate(like_count=Count('likes', distinct=True))
            .order_by('material_type__order', '-created_at')
        )
        active_tag = self.request.GET.get('tag', '').strip()
        if active_tag:
            qs = qs.filter(tags__slug=active_tag)
        ctx['materials'] = qs
        ctx['can_upload'] = self.request.user.can_upload_to(subject)
        # Tags present on published materials for this subject (for filter bar)
        ctx['all_tags'] = Tag.objects.filter(
            materials__subject=subject, materials__is_published=True
        ).distinct()
        ctx['active_tag'] = active_tag
        return ctx


# ---------------------------------------------------------------------------
# Material upload
# ---------------------------------------------------------------------------

class MaterialUploadView(LoginRequiredMixin, View):
    template_name = 'materials/upload.html'

    def _check_permission(self, request, subject):
        if not request.user.can_upload_to(subject):
            raise PermissionDenied

    def _icon_context(self):
        from .icons import MATERIAL_ICONS
        return {'material_icons': MATERIAL_ICONS}

    def get(self, request, year_slug=None, subject_slug=None):
        subject = self._get_subject(year_slug, subject_slug)
        if subject:
            self._check_permission(request, subject)
        form = MaterialUploadForm(user=request.user)
        if subject:
            form.fields['subject'].initial = subject
        ctx = {'form': form, 'subject': subject}
        ctx.update(self._icon_context())
        return render(request, self.template_name, ctx)

    def post(self, request, year_slug=None, subject_slug=None):
        subject = self._get_subject(year_slug, subject_slug)
        if subject:
            self._check_permission(request, subject)

        form = MaterialUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            material = form.save(commit=False)
            material.author = request.user

            # Compress image before saving
            if material.file and _is_image_ext(material.file.name):
                from django.conf import settings as _s
                compress_image_file(
                    material.file,
                    max_width=_s.IMAGE_COMPRESS_MAX_WIDTH,
                    quality=_s.IMAGE_COMPRESS_QUALITY,
                )

            material.save()
            form.save_m2m()

            # Explicit audit log entry WITH request (includes IP)
            source = 'odkaz' if material.external_url and not material.file else 'soubor'
            audit_log(
                request.user,
                AuditLog.Action.UPLOAD,
                material,
                description=f'Upload ({source}): {material.title}',
                request=request,
            )

            if material.file:
                messages.success(request, _('Materiál byl úspěšně nahrán. Probíhá extrakce textu…'))
            else:
                messages.success(request, _('Odkaz byl úspěšně přidán.'))
            return redirect('materials:subject_detail',
                            year_slug=material.subject.school_year.slug,
                            subject_slug=material.subject.slug)

        ctx = {'form': form, 'subject': subject}
        ctx.update(self._icon_context())
        return render(request, self.template_name, ctx)

    def _get_subject(self, year_slug, subject_slug):
        if year_slug and subject_slug:
            return get_object_or_404(
                SubjectYear,
                school_year__slug=year_slug,
                subject__slug=subject_slug,
            )
        return None


def _is_image_ext(filename: str) -> bool:
    import os
    _, ext = os.path.splitext(filename)
    return ext.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp')


# ---------------------------------------------------------------------------
# Material detail
# ---------------------------------------------------------------------------

class MaterialDetailView(LoginRequiredMixin, DetailView):
    model = Material
    template_name = 'materials/material_detail.html'
    context_object_name = 'material'
    queryset = Material.objects.select_related('subject__subject', 'subject__school_year', 'author', 'material_type')

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.is_published and not request.user.can_upload_to(obj.subject):
            raise PermissionDenied
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        material = self.object
        ctx['comments'] = material.comments.filter(is_visible=True).select_related('author')
        ctx['like_count'] = material.likes.count()
        ctx['user_liked'] = material.likes.filter(user=self.request.user).exists()
        ctx['versions'] = material.versions.order_by('-version') if not material.parent else []
        ctx['can_upload'] = self.request.user.can_upload_to(material.subject)
        ctx['material_abs_url'] = self.request.build_absolute_uri()
        return ctx


# ---------------------------------------------------------------------------
# Download (increments counter)
# ---------------------------------------------------------------------------

class MaterialDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        material = get_object_or_404(Material, pk=pk, is_published=True)
        if not material.file:
            raise PermissionDenied
        Material.objects.filter(pk=pk).update(download_count=models.F('download_count') + 1)
        audit_log(
            request.user, AuditLog.Action.DOWNLOAD, material,
            description=f'Staženo: {material.title}',
            request=request,
        )
        return redirect(material.file.url)


# ---------------------------------------------------------------------------
# Like / Unlike (AJAX-friendly)
# ---------------------------------------------------------------------------

class MaterialLikeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from django.http import JsonResponse
        material = get_object_or_404(Material, pk=pk, is_published=True)
        like, created = MaterialLike.objects.get_or_create(material=material, user=request.user)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        count = material.likes.count()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'liked': liked, 'count': count})
        return redirect('materials:material_detail', pk=pk)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class CommentAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        material = get_object_or_404(Material, pk=pk, is_published=True)
        text = request.POST.get('text', '').strip()
        if text:
            comment = Comment.objects.create(material=material, author=request.user, text=text)
            audit_log(
                request.user, AuditLog.Action.COMMENT_ADD, comment,
                description=f'Komentář k: {material.title}',
                request=request,
            )
        return redirect('materials:material_detail', pk=pk)


class CommentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        if request.user == comment.author or request.user.is_admin_role or request.user.is_staff:
            comment.is_visible = False
            comment.save(update_fields=['is_visible'])
            audit_log(
                request.user, AuditLog.Action.COMMENT_DELETE, comment,
                description=f'Skrytí komentáře u: {comment.material}',
                request=request,
                level='warning',
            )
        return redirect('materials:material_detail', pk=comment.material_id)


# ---------------------------------------------------------------------------
# Bulk upload
# ---------------------------------------------------------------------------

class BulkUploadView(LoginRequiredMixin, View):
    template_name = 'materials/bulk_upload.html'

    def get(self, request, year_slug, subject_slug):
        subject = get_object_or_404(SubjectYear, school_year__slug=year_slug, subject__slug=subject_slug)
        if not (request.user.is_teacher or request.user.is_admin_role):
            raise PermissionDenied
        from django.conf import settings as _s
        from .models import MaterialType
        return render(request, self.template_name, {
            'subject': subject,
            'material_types': MaterialType.objects.all(),
            'max_mb': getattr(_s, 'MATERIAL_MAX_UPLOAD_MB', 50),
        })

    def post(self, request, year_slug, subject_slug):
        subject = get_object_or_404(SubjectYear, school_year__slug=year_slug, subject__slug=subject_slug)
        if not (request.user.is_teacher or request.user.is_admin_role):
            raise PermissionDenied

        from django.conf import settings as _s
        from .models import MaterialType
        from .forms import MaterialUploadForm

        files = request.FILES.getlist('files')
        material_type_id = request.POST.get('material_type')
        if not files or not material_type_id:
            messages.error(request, _('Vyberte alespoň jeden soubor a typ materiálu.'))
            return redirect(request.path)

        material_type = get_object_or_404(MaterialType, pk=material_type_id)
        uploaded = 0
        for f in files:
            title = os.path.splitext(f.name)[0]
            m = Material(
                title=title,
                subject=subject,
                material_type=material_type,
                file=f,
                author=request.user,
            )
            if _is_image_ext(f.name):
                compress_image_file(f, max_width=_s.IMAGE_COMPRESS_MAX_WIDTH, quality=_s.IMAGE_COMPRESS_QUALITY)
            m.save()
            uploaded += 1

        messages.success(request, _('Nahráno %(n)d souborů.') % {'n': uploaded})
        return redirect('materials:subject_detail', year_slug=year_slug, subject_slug=subject_slug)


# ---------------------------------------------------------------------------
# Upload new version
# ---------------------------------------------------------------------------

class MaterialNewVersionView(LoginRequiredMixin, View):
    template_name = 'materials/upload_version.html'

    def get(self, request, pk):
        original = get_object_or_404(Material, pk=pk)
        if not request.user.can_upload_to(original.subject):
            raise PermissionDenied
        return render(request, self.template_name, {'original': original})

    def post(self, request, pk):
        original = get_object_or_404(Material, pk=pk)
        if not request.user.can_upload_to(original.subject):
            raise PermissionDenied

        from django.conf import settings as _s
        f = request.FILES.get('file')
        if not f:
            messages.error(request, _('Vyberte soubor.'))
            return redirect(request.path)

        # Determine new version number
        latest_version = Material.objects.filter(
            models.Q(pk=original.pk) | models.Q(parent=original)
        ).aggregate(max_v=models.Max('version'))['max_v'] or 1

        new_version = Material(
            title=original.title,
            subject=original.subject,
            material_type=original.material_type,
            description=original.description,
            file=f,
            author=request.user,
            parent=original,
            version=latest_version + 1,
        )
        if _is_image_ext(f.name):
            compress_image_file(f, max_width=_s.IMAGE_COMPRESS_MAX_WIDTH, quality=_s.IMAGE_COMPRESS_QUALITY)
        new_version.save()

        # Unpublish the old version
        Material.objects.filter(pk=original.pk).update(is_published=False)

        messages.success(request, _('Nová verze byla nahrána.'))
        return redirect('materials:material_detail', pk=new_version.pk)


# ---------------------------------------------------------------------------
# Material delete
# ---------------------------------------------------------------------------

class MaterialDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        material = get_object_or_404(Material, pk=pk)

        if not (request.user == material.author or request.user.can_upload_to(material.subject)):
            raise PermissionDenied

        title = material.title
        subject = material.subject
        material.delete()

        audit_log(
            request.user,
            AuditLog.Action.DELETE,
            description=f'Smazáno: {title}',
            request=request,
        )
        messages.success(request, _('Materiál byl smazán.'))
        return redirect('materials:subject_detail',
                        year_slug=subject.school_year.slug,
                        subject_slug=subject.slug)


# ---------------------------------------------------------------------------
# VIP management (Teacher / Admin only)
# ---------------------------------------------------------------------------

class VIPGrantView(LoginRequiredMixin, View):
    """Grant VIP rights to a student for a subject."""

    def post(self, request, subject_pk):
        subject = get_object_or_404(SubjectYear, pk=subject_pk)

        if not (request.user.is_teacher or request.user.is_admin_role):
            raise PermissionDenied

        # Teachers may only grant for their own subjects
        if request.user.is_teacher and not subject.teachers.filter(pk=request.user.pk).exists():
            raise PermissionDenied

        student_id = request.POST.get('student_id')
        if not student_id:
            messages.error(request, _('Nebyl vybrán žádný student.'))
            return redirect(request.META.get('HTTP_REFERER', '/'))

        from django.contrib.auth import get_user_model
        User = get_user_model()
        student = get_object_or_404(User, pk=student_id, role='student')

        _, created = SubjectVIP.objects.get_or_create(
            user=student,
            subject=subject,
            defaults={'granted_by': request.user},
        )

        if created:
            audit_log(request.user, AuditLog.Action.VIP_GRANT, subject,
                      description=f'VIP uděleno: {student} → {subject}', request=request)
            messages.success(request, _('VIP oprávnění bylo uděleno.'))
        else:
            messages.info(request, _('Student již VIP oprávnění má.'))

        return redirect(request.META.get('HTTP_REFERER', '/'))


class VIPRevokeView(LoginRequiredMixin, View):
    """Revoke VIP rights."""

    def post(self, request, pk):
        vip = get_object_or_404(SubjectVIP, pk=pk)
        subject = vip.subject

        if not (request.user.is_teacher or request.user.is_admin_role):
            raise PermissionDenied
        if request.user.is_teacher and not subject.teachers.filter(pk=request.user.pk).exists():
            raise PermissionDenied

        description = f'VIP odebráno: {vip.user} → {subject}'
        vip.delete()

        audit_log(request.user, AuditLog.Action.VIP_REVOKE, subject,
                  description=description, request=request)
        messages.success(request, _('VIP oprávnění bylo odebráno.'))
        return redirect(request.META.get('HTTP_REFERER', '/'))


# ---------------------------------------------------------------------------
# Subject ZIP download
# ---------------------------------------------------------------------------

class SubjectZipDownloadView(LoginRequiredMixin, View):
    """Download all published materials of a subject as a single ZIP file."""

    def get(self, request, year_slug, subject_slug):
        subject = get_object_or_404(
            SubjectYear,
            subject__slug=subject_slug,
            school_year__slug=year_slug,
        )
        materials = (
            Material.objects.filter(subject=subject, is_published=True)
            .exclude(file='')
            .order_by('material_type__order', 'created_at')
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for mat in materials:
                if not mat.file:
                    continue
                try:
                    ext = os.path.splitext(mat.file.name)[1]
                    safe_name = f'{mat.pk}_{slugify(mat.title)}{ext}'
                    with mat.file.open('rb') as f:
                        zf.writestr(safe_name, f.read())
                except Exception:
                    logger.exception('ZIP: could not add material %d', mat.pk)

        buf.seek(0)
        filename = f'{slugify(subject.name)}.zip'
        response = HttpResponse(buf.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
