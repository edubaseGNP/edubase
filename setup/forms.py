from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class SchoolConfigForm(forms.Form):
    school_name = forms.CharField(
        max_length=200,
        label=_('Název školy'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': _('např. Gymnázium Jana Nerudy'),
        }),
    )
    school_domain = forms.CharField(
        max_length=100,
        label=_('Doménové jméno'),
        help_text=_('Doména, na které bude systém dostupný, např. skola.cz'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'skola.cz',
        }),
    )
    google_client_id = forms.CharField(
        max_length=300,
        label=_('Google Client ID'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
            'placeholder': 'xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com',
        }),
    )
    google_client_secret = forms.CharField(
        max_length=300,
        label=_('Google Client Secret'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
            'placeholder': 'GOCSPX-...',
        }),
    )
    google_allowed_domain = forms.CharField(
        max_length=100,
        required=False,
        label=_('Omezit přihlášení na doménu'),
        help_text=_('Nepovinné. Pouze uživatelé s e-mailem @tato-domena.cz se mohou přihlásit.'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'skola.cz',
        }),
    )


class AdminAccountForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label=_('Jméno'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': _('Jan'),
        }),
    )
    last_name = forms.CharField(
        max_length=150,
        label=_('Příjmení'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': _('Novák'),
        }),
    )
    email = forms.EmailField(
        label=_('E-mail'),
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'admin@skola.cz',
        }),
    )
    password1 = forms.CharField(
        label=_('Heslo'),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        }),
    )
    password2 = forms.CharField(
        label=_('Heslo znovu'),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_('Uživatel s tímto e-mailem již existuje.'))
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', _('Hesla se neshodují.'))
        if p1:
            validate_password(p1)
        return cleaned
