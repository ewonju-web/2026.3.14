from django.urls import path
from . import views
from chat import views as chat_views

urlpatterns = [
    path('', views.index, name='index'),
    path('equipment/<int:pk>/', views.equipment_detail, name='equipment_detail'),
    path('equipment/create/', views.equipment_create, name='equipment_create'),
    path('new/', views.equipment_create, name='equipment_create_legacy'),
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/create/', views.job_create, name='job_create'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
    path('parts/', views.part_list, name='part_list'),
    path('parts/create/', views.part_create, name='part_create'),
    path('parts/<int:pk>/', views.part_detail, name='part_detail'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('mypage/', views.my_page, name='my_page'),
    path('equipment/<int:pk>/edit/', views.equipment_edit, name='equipment_edit'),
    path('equipment/<int:pk>/delete/', views.equipment_delete, name='equipment_delete'),
    path('equipment/<int:pk>/chat/', chat_views.equipment_chat_start, name='equipment_chat_start'),
    path('equipment/<int:pk>/favorite/', views.toggle_equipment_favorite, name='toggle_equipment_favorite'),
    path('parts/<int:pk>/favorite/', views.toggle_part_favorite, name='toggle_part_favorite'),
    path('jobs/<int:pk>/chat/', chat_views.job_chat_start, name='job_chat_start'),
    path('jobs/<int:pk>/edit/', views.job_edit, name='job_edit'),
    path('jobs/<int:pk>/delete/', views.job_delete, name='job_delete'),
    path('parts/<int:pk>/edit/', views.part_edit, name='part_edit'),
    path('parts/<int:pk>/delete/', views.part_delete, name='part_delete'),
    path('info/', views.excavator_info, name='excavator_info'),
    path('parts-as/', views.parts_as, name='parts_as'),
]
