from django.urls import path

from . import room_planner_views as views

urlpatterns = [
    path("projects/<int:project_pk>/room-planner/", views.room_planner, name="next-room-planner"),
    path("projects/<int:project_pk>/room-planner/save/", views.room_planner_save, name="next-room-planner-save"),
    path("projects/<int:project_pk>/room-planner/vision/", views.room_planner_vision, name="next-room-planner-vision"),
]
