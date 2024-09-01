from django.conf import settings
from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from admin_api.permissions import IsAdmin

if settings.DEBUG:
    schema_view = TemplateView.as_view(
        template_name='swagger.html',
        extra_context={'schema_url': 'openapi-schema'},
    )
else:
    class AdminOnlySchemaView(TemplateView):
        template_name = 'swagger.html'
        extra_context = {'schema_url': 'openapi-schema'}
        permissions = (IsAdmin,)

    schema_view = AdminOnlySchemaView.as_view()

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r'^api/v1/(?P<lang>en|ru)/', include('api.urls')),
    path('docs/', schema_view, name='docs'),
]

if settings.DEBUG:
    urlpatterns = [
        *urlpatterns,
    ] + debug_toolbar_urls()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)



