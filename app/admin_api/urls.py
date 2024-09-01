from django.urls import path
from admin_api import views
from djoser.views import UserViewSet


urlpatterns = [
    path("users/", views.AdminUsersListView.as_view(), name='admin-users'),
    path("users/set-password/", views.AdminUserViewSet.as_view({'post': 'set_password'}), name='admin-user-set-password'),
    path("users/set-profile/", views.AdminUserViewSet.as_view({'post': 'set_profile'}), name='admin-user-set-profile'),
    path("users/create-user/", UserViewSet.as_view({'post': 'create'}), name='admin-user-create'),
    path("users/logs/", views.AdminUserActionLogListView.as_view(), name='admin-users-logs'),
    path("profiles/", views.AdminProfileListCreateView.as_view(), name='admin-profiles'),
    path("profiles/<uuid:profileId>/", views.AdminRetrieveUpdateDestroyProfileView.as_view(), name='admin-profile-detail'),
    path("tasks/", views.AdminTaskListCreateView.as_view(), name='admin-tasks'),
    path("tasks/<uuid:taskId>/", views.AdminRetrieveUpdateDestroyTaskView.as_view(), name='admin-task-detail'),
    path("submissions/", views.AdminSubmissionsListView.as_view(), name='admin-submissions'),
    path("submissions/<uuid:submissionId>/", views.AdminRetrieveUpdateDestroySubmissionView.as_view(), name='admin-submission-detail'),
]
