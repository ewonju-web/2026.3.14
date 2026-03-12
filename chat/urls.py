from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_room_list, name='chat_room_list'),
    path('<int:room_id>/', views.chat_room_detail, name='chat_room_detail'),
    path('setlang/', views.set_language, name='set_language'),
]
