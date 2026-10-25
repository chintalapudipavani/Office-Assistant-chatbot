from django.urls import path

from . import views

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path("upload/", views.document_upload, name="document_upload"),
    path("rebuild/", views.document_rebuild, name="document_rebuild"),
    path("<int:pk>/delete/", views.document_delete, name="document_delete"),
]
