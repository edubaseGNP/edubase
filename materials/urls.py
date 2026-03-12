from django.urls import path

from . import views
from .search import MaterialSearchView, SearchClickView

app_name = 'materials'

urlpatterns = [
    # Full-text search
    path('hledat/', MaterialSearchView.as_view(), name='search'),
    path('hledat/klik/', SearchClickView.as_view(), name='search_click'),

    # School years
    path('', views.SchoolYearListView.as_view(), name='school_year_list'),

    # Generic upload (subject chosen in form)
    path('nahrat/', views.MaterialUploadView.as_view(), name='upload_generic'),

    # Material detail, delete, download, like, comments, version
    # (must come before slug catch-alls to avoid <slug>/<slug>/ matching 'material/<pk>/')
    path('material/<int:pk>/', views.MaterialDetailView.as_view(), name='material_detail'),
    path('material/<int:pk>/smazat/', views.MaterialDeleteView.as_view(), name='material_delete'),
    path('material/<int:pk>/stahnout/', views.MaterialDownloadView.as_view(), name='material_download'),
    path('material/<int:pk>/like/', views.MaterialLikeView.as_view(), name='material_like'),
    path('material/<int:pk>/komentar/', views.CommentAddView.as_view(), name='comment_add'),
    path('material/<int:pk>/nova-verze/', views.MaterialNewVersionView.as_view(), name='material_new_version'),
    path('komentar/<int:pk>/smazat/', views.CommentDeleteView.as_view(), name='comment_delete'),

    # VIP management
    path('predmet/<int:subject_pk>/vip/udelit/', views.VIPGrantView.as_view(), name='vip_grant'),
    path('vip/<int:pk>/odebrat/', views.VIPRevokeView.as_view(), name='vip_revoke'),

    # Slug-based routes (catch-all — must come last)
    path('<slug:year_slug>/<slug:subject_slug>/nahrat/',
         views.MaterialUploadView.as_view(), name='upload'),
    path('<slug:year_slug>/<slug:subject_slug>/hromadne/',
         views.BulkUploadView.as_view(), name='bulk_upload'),
    path('<slug:year_slug>/<slug:subject_slug>/stahnout-zip/',
         views.SubjectZipDownloadView.as_view(), name='subject_zip'),
    path('<slug:year_slug>/<slug:subject_slug>/',
         views.SubjectDetailView.as_view(), name='subject_detail'),
]
