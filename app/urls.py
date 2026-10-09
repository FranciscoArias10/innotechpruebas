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
    RepresentativeStudentScheduleView,
    RepresentativeStudentSummaryView,
)
from app.student_views import (
    StudentSummaryView,
    StudentSubjectsView,
    StudentGradesView,
    StudentSubjectGradesDetailView,
    StudentAttendanceView,
    StudentScheduleView,
    StudentHomeView,
    StudentPlanningView,
    StudentClassmatesView,
    StudentResourceOpenView,
)

urlpatterns = [
    # Dispositivos, version, preferencias y feedback
    path('device/register/', DeviceRegisterView.as_view(), name='movil-device-register'),
    path('app/version/', AppVersionView.as_view(), name='movil-app-version'),
    path('notifications/preferences/', NotificationPreferencesView.as_view(), name='movil-notification-preferences'),
    path('feedback/', FeedbackView.as_view(), name='movil-feedback'),

    # Endpoints del estudiante (Fase 1)
    path('student/home/', StudentHomeView.as_view(), name='movil-student-home'),
    path('student/summary/', StudentSummaryView.as_view(), name='movil-student-summary'),
    path('student/subjects/', StudentSubjectsView.as_view(), name='movil-student-subjects'),
    path('student/grades/', StudentGradesView.as_view(), name='movil-student-grades'),
    path('student/subjects/<int:materia_asignada_id>/grades/', StudentSubjectGradesDetailView.as_view(), name='movil-student-subject-grades-detail'),
    path('student/attendance/', StudentAttendanceView.as_view(), name='movil-student-attendance'),
    path('student/attendance/report/', StudentAttendanceView.as_view(), name='movil-student-attendance-report'),
    path('student/schedule/', StudentScheduleView.as_view(), name='movil-student-schedule'),
    path('student/subjects/<int:materia_asignada_id>/planning/', StudentPlanningView.as_view(), name='movil-student-subject-planning'),
    path('student/subjects/<int:materia_asignada_id>/classmates/', StudentClassmatesView.as_view(), name='movil-student-subject-classmates'),
    path('student/subjects/<int:materia_asignada_id>/resource-open/', StudentResourceOpenView.as_view(), name='movil-student-resource-open'),
    # Alias sin sufijo movil o con compatibilidad
    path('student/resources/open/', StudentResourceOpenView.as_view(), name='movil-student-resource-open-global'),


    # Endpoints del representante
    path('representative/students/<int:student_id>/grades/', RepresentativeStudentGradesView.as_view(), name='movil-representative-student-grades'),
    path('representative/students/<int:student_id>/attendance/', RepresentativeStudentAttendanceView.as_view(), name='movil-representative-student-attendance'),
    path('representative/students/<int:student_id>/schedule/', RepresentativeStudentScheduleView.as_view(), name='movil-representative-student-schedule'),
    path('representative/students/<int:student_id>/summary/', RepresentativeStudentSummaryView.as_view(), name='movil-representative-student-summary'),
]