# -*- coding: utf-8 -*-
"""
Rutas de la app. ESTO SI VIAJA a sige-ube.

Solo rutas relativas: el prefijo (/api/v1.0.0/movil/) lo pone quien incluye
este archivo. Aqui lo pone proyecto/urls.py; alla, api/v1_0_0/urls.py.
"""
from django.urls import path

from app.views import (
    DeviceRegisterView,
    AppVersionView,
    NotificationPreferencesView,
    FeedbackView,
    RepresentativeStudentGradesView,
    RepresentativeStudentAttendanceView,
)

urlpatterns = [
    path('device/register/', DeviceRegisterView.as_view(), name='movil-device-register'),
    path('app/version/', AppVersionView.as_view(), name='movil-app-version'),
    path('notifications/preferences/', NotificationPreferencesView.as_view(), name='movil-notification-preferences'),
    path('feedback/', FeedbackView.as_view(), name='movil-feedback'),
    path('representative/students/<int:student_id>/grades/', RepresentativeStudentGradesView.as_view(), name='movil-representative-student-grades'),
    path('representative/students/<int:student_id>/attendance/', RepresentativeStudentAttendanceView.as_view(), name='movil-representative-student-attendance'),
]

