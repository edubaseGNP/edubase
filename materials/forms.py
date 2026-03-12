import os

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import Material, Subject, Tag


class MaterialUploadForm(forms.ModelForm):
    """Form for uploading a new material file."""

    class Meta:
        model = Material
        fields = ['title', 'subject', 'material_type', 'file', 'description', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': _('Název materiálu')}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Volitelný popis')}),
            'tags': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Restrict subject choices to subjects where the user can upload
        if user and not user.is_admin_role:
            if user.is_teacher:
                self.fields['subject'].queryset = Subject.objects.filter(
                    teachers=user
                ).select_related('school_year')
            else:
                # VIP student – only subjects where VIP was granted
                vip_subject_ids = user.vip_subjects.values_list('subject_id', flat=True)
                self.fields['subject'].queryset = Subject.objects.filter(
                    pk__in=vip_subject_ids
                ).select_related('school_year')

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            return file

        # Size validation
        max_bytes = settings.MATERIAL_MAX_UPLOAD_MB * 1024 * 1024
        if file.size > max_bytes:
            raise forms.ValidationError(
                _('Soubor je příliš velký. Maximální povolená velikost je %(max)d MB.')
                % {'max': settings.MATERIAL_MAX_UPLOAD_MB}
            )

        # Type validation by extension
        ext = os.path.splitext(file.name)[1].lower()
        allowed_exts = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp'}
        if ext not in allowed_exts:
            raise forms.ValidationError(
                _('Nepodporovaný formát souboru. Povolené: PDF, JPG, PNG, GIF, WEBP.')
            )

        return file
