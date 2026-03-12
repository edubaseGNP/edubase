from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('setup/', include('setup.urls', namespace='setup')),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('materialy/', include('materials.urls', namespace='materials')),
    path('uzivatele/', include('users.urls', namespace='users')),
    path('', include('core.urls', namespace='core')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('__reload__/', include('django_browser_reload.urls'))]
