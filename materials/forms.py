import os

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import Material, SubjectYear, Tag

# Supported upload extensions (file + MIME type checked in clean_file)
OFFICE_EXTS = {'.docx', '.pptx', '.xlsx', '.odt', '.ods', '.odp'}
IMAGE_EXTS  = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_EXTS = {'.pdf'} | IMAGE_EXTS | OFFICE_EXTS

EXT_LABELS = {
    '.pdf':  'PDF',
    '.jpg':  'JPG', '.jpeg': 'JPG', '.png': 'PNG', '.gif': 'GIF', '.webp': 'WEBP',
    '.docx': 'Word (.docx)',
    '.pptx': 'PowerPoint (.pptx)',
    '.xlsx': 'Excel (.xlsx)',
    '.odt':  'LibreOffice Writer (.odt)',
    '.ods':  'LibreOffice Calc (.ods)',
    '.odp':  'LibreOffice Impress (.odp)',
}


class MaterialUploadForm(forms.ModelForm):
    """Form for uploading a new material file or linking an external document."""

    class Meta:
        model = Material
        fields = [
            'title', 'subject', 'material_type',
            'icon', 'file', 'external_url',
            'description', 'tags',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': _('Název materiálu'),
                'class': 'form-input',
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': _('Volitelný popis materiálu'),
                'class': 'form-input',
            }),
            'tags': forms.CheckboxSelectMultiple(),
            'icon': forms.HiddenInput(),
            'external_url': forms.URLInput(attrs={
                'placeholder': 'https://docs.google.com/...',
                'class': 'form-input',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Restrict subject choices based on upload permission
        if user and not user.is_admin_role:
            if user.is_teacher:
                self.fields['subject'].queryset = SubjectYear.objects.filter(
                    teachers=user
                ).select_related('subject', 'school_year')
            else:
                vip_subject_ids = user.vip_subjects.values_list('subject_id', flat=True)
                self.fields['subject'].queryset = SubjectYear.objects.filter(
                    pk__in=vip_subject_ids
                ).select_related('subject', 'school_year')
        else:
            self.fields['subject'].queryset = SubjectYear.objects.select_related(
                'subject', 'school_year'
            )

        # Make file not required at form level – clean() enforces the either/or rule
        self.fields['file'].required = False

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            return file

        # Size check
        max_bytes = settings.MATERIAL_MAX_UPLOAD_MB * 1024 * 1024
        if file.size > max_bytes:
            raise forms.ValidationError(
                _('Soubor je příliš velký. Maximum je %(max)d MB.') % {
                    'max': settings.MATERIAL_MAX_UPLOAD_MB
                }
            )

        # Extension check
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTS:
            raise forms.ValidationError(
                _('Nepodporovaný formát. Povolené: PDF, JPG, PNG, WEBP, '
                  'DOCX, PPTX, XLSX, ODT, ODS, ODP.')
            )
        return file

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        external_url = cleaned_data.get('external_url', '').strip()

        # For new materials, require either a file or an external URL
        if not self.instance.pk:
            if not file and not external_url:
                raise forms.ValidationError(
                    _('Nahrajte soubor nebo zadejte odkaz na Google Docs / jiný zdroj.')
                )
        return cleaned_data
