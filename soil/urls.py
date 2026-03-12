from django.urls import path
from . import views
from chat.views import soil_chat_start

urlpatterns = [
    path('', views.soil_list, name='soil_list'),
    path('create/', views.soil_create, name='soil_create'),
    path('<int:pk>/', views.soil_detail, name='soil_detail'),
    path('<int:pk>/edit/', views.soil_edit, name='soil_edit'),
    path('<int:pk>/delete/', views.soil_delete, name='soil_delete'),
    path('<int:pk>/chat/', soil_chat_start, name='soil_chat_start'),
]
