from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("chat/", views.chat, name="chat"),
    path("chat/ask/", views.chat_ask, name="chat_ask"),
    path("chat/history/", views.chat_history, name="chat_history"),
    path("chat/new/", views.chat_new, name="chat_new"),
    path("chat/<int:session_id>/delete/", views.chat_delete, name="chat_delete"),
]
