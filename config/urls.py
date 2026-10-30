"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path

from deduplication import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Main dashboard
    path("", views.dashboard, name="dashboard"),

    # Data ingestion
    path("upload/", views.upload_csv, name="upload_csv"),

    # Pipeline run history and details
    path("runs/", views.run_list, name="run_list"),
    path(
        "runs/<uuid:run_id>/",
        views.run_detail,
        name="run_detail",
    ),
    path(
        "runs/<uuid:run_id>/merge/",
        views.merge_run,
        name="merge_run",
    ),
    path(
        "runs/<uuid:run_id>/export/<str:kind>/",
        views.export_run,
        name="export_run",
    ),

    # Duplicate review workflow
    path(
        "reviews/",
        views.duplicate_reviews,
        name="duplicate_reviews",
    ),
    path(
        "reviews/<int:review_id>/decision/",
        views.decide_duplicate_review,
        name="decide_duplicate_review",
    ),

    # Published canonical records
    path(
        "merged/",
        views.merged_records,
        name="merged_records",
    ),
]
