import os

from django import forms
from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import Material, SubjectYear, Tag


# ---------------------------------------------------------------------------
# Icon picker widget (used by upload form + admin)
# ---------------------------------------------------------------------------

class IconPickerWidget(forms.Widget):
    """Renders an emoji icon picker with category tabs."""

    def render(self, name, value, attrs=None, renderer=None):
        from .icons import MATERIAL_ICONS
        final_attrs = self.build_attrs(self.attrs or {}, attrs or {})
        wid = final_attrs.get('id', f'id_{name}')
        current = value or '📄'

        tabs_html = ''
        grids_html = ''
        for idx, (cat_name, icons) in enumerate(MATERIAL_ICONS.items()):
            tab_style = (
                'background:#fff;font-weight:600;color:#7c3aed;'
                if idx == 0 else 'color:#6b7280;'
            )
            tabs_html += (
                f'<button type="button" id="iptab_{wid}_{idx}" '
                f'onclick="ipShowCat(\'{wid}\',{idx})" '
                f'style="flex-shrink:0;font-size:.75rem;padding:6px 12px;'
                f'border-radius:6px 6px 0 0;border:none;cursor:pointer;'
                f'white-space:nowrap;transition:all .1s;{tab_style}">'
                f'{cat_name}</button>'
            )
            display = 'flex' if idx == 0 else 'none'
            icon_btns = ''.join(
                f'<button type="button" data-icon="{icon}" '
                f'onclick="ipSelect(\'{wid}\',this.dataset.icon)" '
                f'title="{icon}" '
                f'style="font-size:1.25rem;min-width:2.25rem;height:2.25rem;padding:0 4px;'
                f'display:inline-flex;align-items:center;justify-content:center;'
                f'border-radius:6px;border:none;background:none;cursor:pointer">'
                f'{icon}</button>'
                for icon in icons
            )
            grids_html += (
                f'<div id="ipcat_{wid}_{idx}" '
                f'style="display:{display};flex-wrap:wrap;gap:4px">'
                f'{icon_btns}</div>'
            )

        # Global JS injected once per page
        js = (
            '<script>if(!window.ipShowCat){'
            'window.ipToggle=function(w){var p=document.getElementById("ippanel_"+w);'
            'p.style.display=p.style.display==="none"?"block":"none";'
            'if(p.style.display!=="none")ipShowCat(w,0);};'
            'window.ipShowCat=function(w,idx){var i=0,c,t;'
            'while((c=document.getElementById("ipcat_"+w+"_"+i))!==null){'
            'c.style.display=i===idx?"flex":"none";'
            't=document.getElementById("iptab_"+w+"_"+i);'
            'if(t){t.style.background=i===idx?"#fff":"";'
            't.style.fontWeight=i===idx?"600":"";'
            't.style.color=i===idx?"#7c3aed":"#6b7280";}i++;}};'
            'window.ipSelect=function(w,e){'
            'document.getElementById(w).value=e;'
            'document.getElementById("ipdisp_"+w).textContent=e;'
            'document.getElementById("ippanel_"+w).style.display="none";};'
            '}</script>'
        )

        html = (
            f'<input type="hidden" name="{name}" id="{wid}" value="{current}">\n'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">\n'
            f'  <button type="button" onclick="ipToggle(\'{wid}\')" '
            f'    style="font-size:2rem;width:3.5rem;height:3.5rem;display:flex;'
            f'    align-items:center;justify-content:center;border:2px dashed #d1d5db;'
            f'    border-radius:12px;background:#f9fafb;cursor:pointer;padding:0">\n'
            f'    <span id="ipdisp_{wid}">{current}</span>\n'
            f'  </button>\n'
            f'  <span style="font-size:.875rem;color:#6b7280">Kliknutím změnit ikonu</span>\n'
            f'</div>\n'
            f'<div id="ippanel_{wid}" style="display:none;border:1px solid #e5e7eb;'
            f'border-radius:12px;background:white;box-shadow:0 4px 16px rgba(0,0,0,.1)">\n'
            f'  <div style="display:flex;flex-wrap:wrap;border-bottom:1px solid #e5e7eb;'
            f'  background:#f9fafb;padding:12px 12px 4px;gap:6px;'
            f'  border-radius:12px 12px 0 0">\n'
            f'    {tabs_html}\n'
            f'  </div>\n'
            f'  <div style="padding:12px;max-height:200px;overflow-y:auto">\n'
            f'    {grids_html}\n'
            f'  </div>\n'
            f'</div>\n'
            f'{js}\n'
        )
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        return data.get(name)

# Supported upload extensions (file + MIME type checked in clean_file)
OFFICE_EXTS = {'.docx', '.pptx', '.xlsx', '.odt', '.ods', '.odp'}
IMAGE_EXTS  = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_EXTS = {'.pdf'} | IMAGE_EXTS | OFFICE_EXTS

# Magic bytes (file signatures) for each extension – (offset, bytes) pairs, ALL must match.
_MAGIC: dict[str, list[tuple[int, bytes]]] = {
    '.pdf':  [(0, b'%PDF')],
    '.jpg':  [(0, b'\xff\xd8\xff')],
    '.jpeg': [(0, b'\xff\xd8\xff')],
    '.png':  [(0, b'\x89PNG\r\n\x1a\n')],
    '.gif':  [(0, b'GIF8')],
    '.webp': [(0, b'RIFF'), (8, b'WEBP')],
    # Office + ODF – all ZIP-based
    '.docx': [(0, b'PK\x03\x04')],
    '.pptx': [(0, b'PK\x03\x04')],
    '.xlsx': [(0, b'PK\x03\x04')],
    '.odt':  [(0, b'PK\x03\x04')],
    '.ods':  [(0, b'PK\x03\x04')],
    '.odp':  [(0, b'PK\x03\x04')],
}


def _verify_magic_bytes(file, ext: str) -> bool:
    """Return True if the uploaded file's header matches the expected magic bytes."""
    checks = _MAGIC.get(ext.lower(), [])
    if not checks:
        return True
    try:
        file.seek(0)
        header = file.read(16)
        file.seek(0)
        return all(header[offset:offset + len(sig)] == sig for offset, sig in checks)
    except Exception:
        return False

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

        # Size check – prefer SiteConfig (editable in admin), fallback to settings
        try:
            from core.models import SiteConfig
            max_mb = SiteConfig.get().max_upload_mb
        except Exception:
            max_mb = settings.MATERIAL_MAX_UPLOAD_MB
        max_bytes = max_mb * 1024 * 1024
        if file.size > max_bytes:
            raise forms.ValidationError(
                _('Soubor je příliš velký. Maximum je %(max)d MB.') % {'max': max_mb}
            )

        # Extension check
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTS:
            raise forms.ValidationError(
                _('Nepodporovaný formát. Povolené: PDF, JPG, PNG, WEBP, '
                  'DOCX, PPTX, XLSX, ODT, ODS, ODP.')
            )

        # Magic bytes check – catches files with renamed extension
        if not _verify_magic_bytes(file, ext):
            raise forms.ValidationError(
                _('Soubor neodpovídá deklarovanému formátu (neplatná hlavička souboru).')
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
