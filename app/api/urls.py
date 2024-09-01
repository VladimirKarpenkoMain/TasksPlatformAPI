from django.urls import path, include
from . import views

urlpatterns = [
    path("auth/", include("users.urls")),
    path("profiles/", views.ProfilesListView.as_view(), name='profiles'),
    path("profiles/<uuid:profileId>/", views.ProfileRetrieveView.as_view(), name='profile-detail'),
    path("profiles/<uuid:profileId>/tasks/", views.TasksListView.as_view(), name='tasks'),
    path("tasks/<uuid:taskId>/", views.TaskRetrieveView.as_view(), name='task-detail'),
    path("tasks/<uuid:taskId>/submission/", views.SubmissionCreateUpdateRetrieveView.as_view(), name='submission-detail'),
    path("admin/", include("admin_api.urls")),
]


