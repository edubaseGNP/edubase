from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.views.generic import DetailView

User = get_user_model()


class UserProfileView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'

    def get_context_data(self, **kwargs):
        from materials.models import Material
        ctx = super().get_context_data(**kwargs)
        profile_user = self.object
        materials = (
            Material.objects.filter(author=profile_user, is_published=True)
            .select_related('subject__school_year', 'material_type')
            .prefetch_related('tags')
            .annotate(like_count=Count('likes', distinct=True))
            .order_by('-created_at')
        )
        totals = materials.aggregate(
            total_downloads=Sum('download_count'),
            total_likes=Sum('like_count'),
        )
        ctx['materials'] = materials
        ctx['total_downloads'] = totals['total_downloads'] or 0
        ctx['total_likes'] = totals['total_likes'] or 0
        ctx['is_own_profile'] = self.request.user == profile_user
        return ctx
